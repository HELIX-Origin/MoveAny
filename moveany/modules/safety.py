"""Safety helper functions for MoveAny"""

import os
from moveany.cfg.defaults import DEFAULT_SAFE_DELETE_STAGING
from moveany.modules.files import copy_file, files_identical, file_hash


def verify_file_size(path: str, expected_size: int = None) -> bool:
    """Check file existence and optionally verify size matches expected_size."""
    try:
        size = os.path.getsize(path)
        if expected_size is not None:
            return size == expected_size
        return True
    except OSError:
        return False


def get_sha256(path: str, chunk: int = 1 << 20) -> str:
    """Calculate SHA-256 hash digest of a file using streaming chunks."""
    return file_hash(path, chunk=chunk)


def _ensure_staging_dir() -> str:
    """Create the staging directory if it does not exist and return its path."""
    stag_path = os.path.abspath(DEFAULT_SAFE_DELETE_STAGING)
    os.makedirs(stag_path, exist_ok=True)
    return stag_path


def _stage_path_for(src_path: str) -> str:
    """Return the absolute staging path for a given source file.

    Handles cases where src_path is on a different drive than the current
    working directory by falling back to using only the filename.
    """
    stag_dir = _ensure_staging_dir()
    try:
        rel = os.path.relpath(src_path, start=os.getcwd())
    except ValueError:
        # Different drive letters (e.g., C: vs D:), cannot compute relative path
        rel = os.path.basename(src_path)
    else:
        if rel.startswith(".."):  # outside cwd, also fallback to basename
            rel = os.path.basename(src_path)
    return os.path.join(stag_dir, rel)


def safe_delete_file(path: str) -> None:
    """Safely delete a file by first copying it to a staging area.

    Steps:
    1. Verify source file existence and compute hash for validation.
    2. Copy the file to the staging directory (creating parent dirs).
    3. Verify the staged copy is identical (size + SHA-256).
    4. Delete the original file if verification succeeds.
    5. Keep the staged copy as a backup.
    """
    if os.path.isdir(path):
        raise ValueError(f"Refusing to delete directory as file: {path}")
    if not os.path.isfile(path):
        raise FileNotFoundError(f"File not found for safe delete: {path}")
    
    _ = get_sha256(path)
    staging_path = _stage_path_for(path)
    os.makedirs(os.path.dirname(staging_path), exist_ok=True)
    copy_file(path, staging_path)
    if not files_identical(path, staging_path):
        try:
            os.remove(staging_path)
        except OSError:
            pass
        raise RuntimeError(f"Staged copy verification failed for {path}")
    os.remove(path)


__all__ = ["safe_delete_file", "get_sha256", "verify_file_size"]
