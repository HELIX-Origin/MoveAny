"""Low-level file operations: hashing, comparison, copying, deletion."""
import hashlib
import os
import shutil


def file_hash(path, chunk=1 << 20):
    """Return SHA-256 hex digest of a file, streaming in chunks."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            block = fh.read(chunk)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def files_identical(src, dst, chunk=1 << 20):
    """Cheap size check first, then compare content hashes."""
    try:
        if os.path.getsize(src) != os.path.getsize(dst):
            return False
    except OSError:
        return False
    if os.path.getsize(src) == 0:
        return True
    try:
        return file_hash(src, chunk) == file_hash(dst, chunk)
    except OSError:
        return False


def copy_file(src, dst):
    """Copy a single file, creating parent directories as needed."""
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst)


def safe_delete_file(path):
    """Delete a file, refusing if it is actually a directory."""
    if os.path.isdir(path):
        raise ValueError(f"Refusing to delete directory as file: {path}")
    os.remove(path)


def remove_dir_if_empty(path):
    """Remove `path` if it is an empty directory. Return True if removed."""
    if not os.path.isdir(path):
        return False
    try:
        if os.listdir(path):
            return False
    except OSError:
        return False
    try:
        os.rmdir(path)
        return True
    except OSError:
        return False
