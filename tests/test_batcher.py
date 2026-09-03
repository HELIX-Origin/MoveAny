"""Unit tests for moveany.modules.batcher."""

import pytest
from moveany.modules.batcher import split_batches


def _make_tree(root, paths):
    for rel in paths:
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"x")
    return root


def test_split_batches_basic(tmp_path):
    src = tmp_path / "src"
    _make_tree(src, ["a/file1.txt", "b/file2.txt"])
    dst = tmp_path / "dst"
    dst.mkdir()
    batches = split_batches(str(src), str(dst), exclude_dirs=())
    assert isinstance(batches, list)
    assert len(batches) >= 1


def test_split_batches_deterministic(tmp_path):
    src = tmp_path / "src"
    _make_tree(src, ["z/z.txt", "a/a.txt", "m/m.txt"])
    dst = tmp_path / "dst"
    dst.mkdir()
    result1 = split_batches(str(src), str(dst), exclude_dirs=())
    result2 = split_batches(str(src), str(dst), exclude_dirs=())
    names1 = [b["name"] for b in result1]
    names2 = [b["name"] for b in result2]
    assert names1 == names2, "Batch order must be deterministic"


def test_split_batches_respects_exclusions(tmp_path):
    src = tmp_path / "src"
    _make_tree(src, ["__pycache__/compiled.pyc", "main.py"])
    dst = tmp_path / "dst"
    dst.mkdir()
    batches = split_batches(str(src), str(dst), exclude_dirs=("__pycache__",))
    for b in batches:
        assert "__pycache__" not in b.get("name", "")


def test_split_batches_empty_dir(tmp_path):
    src = tmp_path / "empty"
    src.mkdir()
    dst = tmp_path / "dst"
    dst.mkdir()
    batches = split_batches(str(src), str(dst), exclude_dirs=())
    total_files = sum(b.get("files", 0) for b in batches)
    assert total_files == 0, f"Expected 0 files in empty src, got {total_files}"
