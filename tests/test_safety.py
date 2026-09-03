import os
import shutil
import tempfile
import pytest

from moveany.modules.safety import safe_delete_file
from moveany.cfg.defaults import DEFAULT_SAFE_DELETE_STAGING

@pytest.fixture(autouse=True)
def clean_staging():
    # Ensure staging dir is clean before and after each test
    staging_dir = os.path.abspath(DEFAULT_SAFE_DELETE_STAGING)
    if os.path.isdir(staging_dir):
        shutil.rmtree(staging_dir)
    yield
    if os.path.isdir(staging_dir):
        shutil.rmtree(staging_dir)

def test_safe_delete_file_stages_and_deletes(tmp_path):
    # Create a temporary file with some content
    tmp_file = tmp_path / "sample.txt"
    content = b"Hello MoveAny!"
    tmp_file.write_bytes(content)

    # Ensure the file exists
    assert tmp_file.is_file()

    # Call the safe delete function
    safe_delete_file(str(tmp_file))

    # Original file should be removed
    assert not tmp_file.exists()

    # Staged copy should exist in the staging directory and match content
    staging_dir = os.path.abspath(DEFAULT_SAFE_DELETE_STAGING)
    # Determine staging path using same logic as safety module (handles cross‑drive paths)
    try:
        rel_path = os.path.relpath(str(tmp_file), start=os.getcwd())
    except ValueError:
        rel_path = os.path.basename(str(tmp_file))
    else:
        if rel_path.startswith(".."):  # fallback case
            rel_path = os.path.basename(str(tmp_file))
    staged_path = os.path.join(staging_dir, rel_path)
    assert os.path.isfile(staged_path)
    assert open(staged_path, "rb").read() == content
