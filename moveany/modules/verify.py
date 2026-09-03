"""Content verification / comparison between two trees.

Compares EVERY file (size + full-content hash) between source and destination,
excluding the configured exclude-dir names. Non-destructive.

Writes findings to dedicated log files via the Reporter:
  identical.log - verified byte-identical on both sides
  missing.log   - present on source but absent on destination
  different.log - present on both but content differs
  extra.log     - present on destination only
"""

import os

from moveany.modules.files import files_identical


def _rel_of(root, full):
    return full[len(root.rstrip("\\/")) + 1:].replace("\\", "/")


def scan_tree(root, exclude_dirs, reporter=None, label="", skip_top_dirs=None,
              progress_every=1000):
    """Yield (relpath, abs_path) for every file under root.

    Prunes directories named in `exclude_dirs`. If `skip_top_dirs` is given,
    those immediate sub-directories of root are also pruned. Logs batch
    progress when a Reporter is provided.
    """
    root = os.path.abspath(root)
    skip_top_dirs = set(skip_top_dirs or [])
    count = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in exclude_dirs]
        if os.path.abspath(dirpath) == root and skip_top_dirs:
            dirnames[:] = [d for d in dirnames if d not in skip_top_dirs]
        for f in filenames:
            full = os.path.join(dirpath, f)
            rel = _rel_of(root, full)
            count += 1
            yield rel, full
            if reporter is not None and count % progress_every == 0:
                reporter.session(f"[scan {label}] {count} files enumerated...")


def compare(src_root, dest_root, exclude_dirs, reporter, skip_top_dirs=None):
    """Compare source and destination contents. Returns a dict with keys:
      missing_on_dest, different, extra_on_dest, identical,
      src_total, dst_total.
    """
    src_root = os.path.abspath(src_root)
    dest_root = os.path.abspath(dest_root)

    reporter.session("=== SCAN PHASE (enumeration) ===")
    reporter.session("Scanning source tree...")
    src_items = list(scan_tree(src_root, exclude_dirs, reporter, label="src",
                               skip_top_dirs=skip_top_dirs))
    reporter.session("Scanning destination tree...")
    dst_items = list(scan_tree(dest_root, exclude_dirs, reporter, label="dst",
                               skip_top_dirs=skip_top_dirs))
    reporter.session(
        f"[scan] enumerated source files={len(src_items)} "
        f"dest files={len(dst_items)}"
    )

    src_map = dict(src_items)
    dst_map = dict(dst_items)

    missing_on_dest = []
    different = []
    identical = []
    extra_on_dest = []

    reporter.session("=== SCAN PHASE (content comparison) ===")
    total_compare = len(src_items)
    checked = 0
    for rel, src_p in src_items:
        dst_p = dst_map.get(rel)
        if dst_p is None:
            missing_on_dest.append(rel)
            reporter.missing(rel)
        elif files_identical(src_p, dst_p):
            identical.append(rel)
            reporter.identical(rel)
        else:
            different.append(rel)
            reporter.different(rel)
        checked += 1
        if checked % 500 == 0:
            reporter.session(
                f"[compare] progress {checked}/{total_compare} "
                f"identical={len(identical)} missing={len(missing_on_dest)} "
                f"different={len(different)}"
            )

    reporter.session("[scan] checking files present only on destination...")
    for rel in dst_map:
        if rel not in src_map:
            extra_on_dest.append(rel)
            reporter.write("extra.log", rel)

    return {
        "missing_on_dest": missing_on_dest,
        "different": different,
        "extra_on_dest": extra_on_dest,
        "identical": identical,
        "src_total": len(src_items),
        "dst_total": len(dst_items),
    }


def report_compare(result, reporter, label="compare"):
    """Write a summary comparison report. Returns number of damaged files."""
    missing = result["missing_on_dest"]
    different = result["different"]

    reporter.info(
        f"[{label}] source files={result['src_total']} "
        f"dest files={result['dst_total']} "
        f"identical={len(result['identical'])} "
        f"missing_on_dest={len(missing)} different={len(different)} "
        f"extra_on_dest={len(result['extra_on_dest'])}"
    )
    if missing:
        reporter.error(f"[{label}] MISSING ON DEST count={len(missing)}")
    if different:
        reporter.error(f"[{label}] CONTENT DIFFERENT count={len(different)}")

    if not missing and not different:
        reporter.info(f"[{label}] VERDICT: all source files verified identical "
                      "on destination. Safe to delete source.")
    else:
        reporter.error(
            f"[{label}] VERDICT: {len(missing) + len(different)} source files "
            "need attention. Do NOT delete source. Use repair."
        )
    return len(missing) + len(different)
