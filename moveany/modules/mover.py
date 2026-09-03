"""Move engine: non-destructive copy, separate delete, empty-dir cleanup.

Guarantees:
  - copy_missing NEVER deletes anything from the source.
  - Every copied file is verified (size + hash) before being marked "ready".
  - delete_phase only deletes files that are byte-identical on the
    destination, and re-verifies each one just before deleting.
"""

import os

from moveany.modules.files import copy_file, files_identical, remove_dir_if_empty
from moveany.modules.safety import safe_delete_file
from moveany.modules.paths import normalize


def _item_for(rel):
    return rel.split("/", 1)[0] if "/" in rel else rel


def copy_missing(compare_result, src_root, dest_root, reporter):
    """Copy files that are missing on dest or differ in content.

    `compare_result` comes from modules.verify.compare():
        missing_on_dest, different, identical

    Returns (ready_relpaths, summary). Never deletes from source.
    """
    src_root = normalize(src_root)
    dest_root = normalize(dest_root)

    to_copy = sorted(set(compare_result["missing_on_dest"]) |
                     set(compare_result["different"]))
    ready = list(compare_result["identical"])
    summary = {
        "needed_copy": len(to_copy),
        "already_identical": len(compare_result["identical"]),
        "copied": 0,
        "missing_source": 0,
        "errors": 0,
        "errors_details": [],
    }

    reporter.session("=== COPY PHASE (non-destructive) ===")
    reporter.session(
        f"Scan found: already_identical={summary['already_identical']}, "
        f"to_copy={summary['needed_copy']}"
    )

    total = len(to_copy)
    last_item = None
    for idx, rel in enumerate(to_copy, 1):
        item = _item_for(rel)
        if item != last_item:
            reporter.session(f">>> copying top-level item: {item}")
            last_item = item

        src = os.path.join(src_root, *rel.split("/"))
        dst = os.path.join(dest_root, *rel.split("/"))

        if not os.path.isfile(src):
            reporter.error(f"source file missing (nothing copied): {rel}")
            summary["missing_source"] += 1
            summary["errors"] += 1
            summary["errors_details"].append((rel, "source file missing"))
            continue

        try:
            copy_file(src, dst)
            summary["copied"] += 1
            reporter.copied(rel)
            if files_identical(src, dst):
                ready.append(rel)
            else:
                reporter.error(f"VERIFY FAILED after copy (source kept): {rel}")
                summary["errors"] += 1
                summary["errors_details"].append((rel, "verify failed after copy"))
        except OSError as ex:
            reporter.error(f"copy failed (source kept): {rel}: {ex}")
            summary["errors"] += 1
            summary["errors_details"].append((rel, str(ex)))

        if idx % 250 == 0 or idx == total:
            reporter.session(
                f"progress {idx}/{total} to-copy, "
                f"copied={summary['copied']} errors={summary['errors']} "
                f"current={item}"
            )

    reporter.session("=== COPY PHASE COMPLETE ===")
    return ready, summary


def delete_phase(ready, src_root, dest_root, reporter):
    """Delete source files in `ready`, re-verifying each just before delete.

    Returns (deleted, errors)."""
    deleted = 0
    errors = 0
    src_root = normalize(src_root)
    dest_root = normalize(dest_root)
    reporter.session(f"=== DELETE PHASE ({len(ready)} files ready) ===")

    for rel in ready:
        try:
            src = os.path.join(src_root, *rel.split("/"))
            dst = os.path.join(dest_root, *rel.split("/"))
            if not os.path.isfile(src):
                reporter.error(f"source already gone (skipping): {rel}")
                continue
            if not os.path.isfile(dst):
                reporter.error(f"dest missing at delete-check (KEEPING src): {rel}")
                errors += 1
                continue
            if files_identical(src, dst):
                safe_delete_file(src)
                deleted += 1
                reporter.moved(rel)
            else:
                reporter.error(f"RE-CHECK MISMATCH at deletion (KEEPING src): {rel}")
                errors += 1
        except OSError as ex:
            reporter.error(f"delete error (source kept): {rel}: {ex}")
            errors += 1

    reporter.session("=== DELETE PHASE COMPLETE ===")
    return deleted, errors


def remove_empty_dirs(src_root, exclude_dirs, reporter):
    """Remove now-empty directories under src_root (deepest first)."""
    removed = 0
    remaining = 0
    src_root = normalize(src_root)
    for dirpath, dirnames, filenames in os.walk(src_root, topdown=False):
        dirnames[:] = [d for d in dirnames if d not in exclude_dirs]
        if any(filenames):
            continue
        if remove_dir_if_empty(dirpath):
            removed += 1
            reporter.session(f"removed empty dir: {dirpath}")
        else:
            remaining += 1
    return removed, remaining
