"""Repair damaged files after a move by re-copying them from source to dest.

Operates in small, logged steps. For any relative path that is missing on the
destination or differs in content, re-copies from the source (if it still
exists) and re-verifies. Non-destructive to the source.
"""

import os

from moveany.modules.files import copy_file, files_identical


def _item_for(rel):
    return rel.split("/", 1)[0] if "/" in rel else rel


def repair_missing(result, src_root, dest_root, reporter):
    """Re-copy files that are missing or different on dest from source.

    Returns (recovered, unrecoverable). Files whose source no longer exists,
    or that fail verification after copy, are reported as unrecoverable."""
    recovered = []
    unrecoverable = []

    rels = set(result["missing_on_dest"]) | set(result["different"])
    reporter.info(f"=== REPAIR PHASE: {len(rels)} items to repair ===")

    for rel in sorted(rels):
        src = os.path.join(src_root, *rel.split("/"))
        dst = os.path.join(dest_root, *rel.split("/"))
        if not os.path.isfile(src):
            reporter.error(f"UNRECOVERABLE (source gone): {rel}")
            unrecoverable.append(rel)
            continue
        try:
            copy_file(src, dst)
            if files_identical(src, dst):
                recovered.append(rel)
            else:
                reporter.error(f"REPAIR VERIFY FAILED: {rel}")
                unrecoverable.append(rel)
        except OSError as ex:
            reporter.error(f"REPAIR FAILED: {rel}: {ex}")
            unrecoverable.append(rel)

    reporter.info(
        f"=== REPAIR COMPLETE: recovered={len(recovered)} "
        f"unrecoverable={len(unrecoverable)} ==="
    )
    return recovered, unrecoverable, rels
