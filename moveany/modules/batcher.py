"""Batch the source tree into manageable per-project units.

Rather than one monolithic scan, the source is split into batches (one per
project/repository directory) and each batch is processed independently. This
gives bounded memory and clear per-batch progress.

Splitting rules:
  - Descend through single-child directory chains (pass-through).
  - A git repo root that contains >= 2 child git repos is an "umbrella": process
    each child repo as its own batch, plus one "scaffold" batch for the
    umbrella's own .git and loose files (via skip_subdirs) so nothing is lost.
  - Otherwise a directory is one batch.
"""

from typing import Dict, Any, List, Set, Sequence, Union
import os

from moveany.modules.paths import normalize, rel_to_root


def _has_files(root: str, exclude_dirs: Union[Set[str], Sequence[str]]) -> bool:
    """True if root contains at least one file anywhere under it (excluding
    excluded dirs)."""
    exclude_set = set(exclude_dirs)
    try:
        for _dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in exclude_set]
            if filenames:
                return True
    except OSError:
        return False
    return False


def _children_with_files(root: str, exclude_dirs: Union[Set[str], Sequence[str]]) -> List[str]:
    """Immediate subdirectories of root that contain files. Sorted abs paths."""
    result = []
    exclude_set = set(exclude_dirs)
    try:
        for entry in os.scandir(root):
            if not entry.is_dir(follow_symlinks=False):
                continue
            if entry.name in exclude_set:
                continue
            if _has_files(entry.path, exclude_set):
                result.append(entry.path)
    except OSError:
        pass
    return sorted(result)


def _is_git_repo_dir(path: str) -> bool:
    return os.path.isdir(os.path.join(path, ".git"))


def _git_child_count(children: Sequence[str]) -> int:
    return sum(1 for c in children if _is_git_repo_dir(c))


def _count_files(root: str, exclude_dirs: Union[Set[str], Sequence[str]]) -> int:
    n = 0
    exclude_set = set(exclude_dirs)
    try:
        for _dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in exclude_set]
            n += len(filenames)
    except OSError:
        pass
    return n


def _count_own_files(root: str, exclude_dirs: Union[Set[str], Sequence[str]]) -> int:
    """Count files directly inside `root` (non-recursive), ignoring excluded
    directory names and any files inside subdirectories."""
    n = 0
    exclude_set = set(exclude_dirs)
    try:
        for entry in os.scandir(root):
            if entry.name in exclude_set:
                continue
            if entry.is_file(follow_symlinks=False):
                n += 1
    except OSError:
        pass
    return n


def split_batches(
    src_root: str,
    dest_root: str,
    exclude_dirs: Union[Set[str], Sequence[str]],
    max_depth: int = 6,
) -> List[Dict[str, Any]]:
    """Split directory tree into batches with deterministic ordering."""
    src_root = normalize(src_root)
    dest_root = normalize(dest_root)
    exclude_set = set(exclude_dirs)
    batches: List[Dict[str, Any]] = []

    def descend(srcdir: str, depth: int) -> None:
        rel = rel_to_root(src_root, srcdir)
        children = _children_with_files(srcdir, exclude_set)
        git_children = _git_child_count(children)
        is_git = _is_git_repo_dir(srcdir)

        if is_git and depth < max_depth:
            if git_children >= 2:
                child_names = sorted([
                    os.path.basename(c) for c in children
                    if _is_git_repo_dir(c)
                ])
                for child in children:
                    if _is_git_repo_dir(child):
                        descend(child, depth + 1)
                batches.append({
                    "name": rel,
                    "src": srcdir,
                    "dst": os.path.join(dest_root, rel),
                    "files": _count_files(srcdir, exclude_set),
                    "scaffold": True,
                    "skip_subdirs": child_names,
                })
                return
            batches.append({
                "name": rel,
                "src": srcdir,
                "dst": os.path.join(dest_root, rel),
                "files": _count_files(srcdir, exclude_set),
            })
            return

        if not children:
            batches.append({
                "name": rel or "<root>",
                "src": srcdir,
                "dst": os.path.join(dest_root, rel),
                "files": _count_files(srcdir, exclude_set),
            })
            return

        if depth >= max_depth:
            batches.append({
                "name": rel or "<root>",
                "src": srcdir,
                "dst": os.path.join(dest_root, rel),
                "files": _count_files(srcdir, exclude_set),
            })
            return

        if len(children) == 1:
            # Only pass through a single child if this directory has no loose
            # files of its own; otherwise treat it as its own batch so loose
            # files (e.g. app.js alongside a sub/) are never dropped.
            if _count_own_files(srcdir, exclude_set) == 0:
                descend(children[0], depth + 1)
            else:
                batches.append({
                    "name": rel or "<root>",
                    "src": srcdir,
                    "dst": os.path.join(dest_root, rel),
                    "files": _count_files(srcdir, exclude_set),
                })
            return

        for child in children:
            descend(child, depth + 1)

    descend(src_root, 0)
    # Sort deterministically by batch name
    batches.sort(key=lambda b: (b["name"], b.get("scaffold", False)))
    return batches
