"""Filesystem path helpers robust against Windows long paths.

On modern Windows (and Python 3.6+) long paths are already handled via the
long-path prefix (\\\\?\\), provided the process manifest allows it. These helpers
normalize, enable long-path mode, resolve symlinks, and defend against path-length /
path-traversal issues.
"""

import os
import sys

# Enable long-path prefix support on Windows (Python 3.6+).
# This allows os.path to handle paths > 260 characters.
if sys.platform.startswith("win"):
    try:
        os.path.enable_long_path_prefix()
    except AttributeError:
        # Python < 3.6 or unavailable; we'll prepend \\?\ manually.
        pass


def _long_path(path: str) -> str:
    """Prepend Windows \\\\?\\ prefix if path is absolute and on Windows.

    The \\\\?\\ prefix bypasses the 260-character MAX_PATH limitation.
    If the path already has the prefix, it is returned unchanged.
    On non-Windows, returned unchanged.
    """
    if sys.platform.startswith("win"):
        # Already has \\?\ prefix or \\?\UNC\
        if path.startswith("\\\\?\\"):
            return path
        # Absolute path? prepend the prefix
        if os.path.isabs(path):
            if path.startswith("\\\\"):
                # UNC path: \\server\share -> \\?\UNC\server\share
                return f"\\\\?\\UNC\\{path[2:]}"
            return f"\\\\?\\{path}"
    return path


def normalize(path: str, resolve_symlinks: bool = True) -> str:
    """Return an absolute, consistently-formed, symlink-resolved path.

    On Windows, the result is long-path-aware (\\\\?\\ prefixed if > 260 chars possible).
    """
    path_expanded = os.path.abspath(os.path.expanduser(os.path.expandvars(path)))
    if resolve_symlinks:
        try:
            path_expanded = os.path.realpath(path_expanded)
        except OSError:
            pass
    return _long_path(path_expanded)


def is_within(root: str, child: str) -> bool:
    """Return True if `child` is located inside `root` (both absolute).

    Uses normalized (long-path-aware) paths for comparison.
    """
    root_norm = normalize(root).rstrip("\\/") + os.sep
    child_norm = normalize(child)
    return child_norm.startswith(root_norm)


def make_dest_path(src_root: str, dest_root: str, src_path: str) -> str:
    """Map an absolute source path to its destination equivalent.

    Result is long-path-aware.
    """
    rel = os.path.relpath(src_path, src_root)
    return _long_path(os.path.join(dest_root, rel))


def rel_to_root(root: str, path: str) -> str:
    """Return path relative to root, using forward slashes for stability.

    Result is long-path-aware.
    """
    return os.path.relpath(path, root).replace(os.sep, "/")


def safe_join(base: str, *parts: str) -> str:
    """Join path parts safely, guarding against traversal outside `base`.

    Result is long-path-aware.
    """
    joined = os.path.join(base, *parts)
    if not is_within(base, joined):
        raise ValueError(f"Path escapes base: {joined}")
    return _long_path(joined)
