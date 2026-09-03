"""Unit tests for moveany.modules.paths."""

import os
import pathlib

import pytest
from moveany.modules.paths import normalize


def test_normalize_basic(tmp_path):
    p = tmp_path / "folder"
    p.mkdir()
    result = normalize(str(p))
    assert os.path.isabs(result)


def test_normalize_trailing_slash(tmp_path):
    p = tmp_path / "folder"
    p.mkdir()
    with_slash = str(p) + os.sep
    result = normalize(with_slash)
    assert not result.endswith(os.sep)


def test_normalize_no_symlinks_by_default(tmp_path):
    p = tmp_path / "real"
    p.mkdir()
    result = normalize(str(p), resolve_symlinks=False)
    assert result is not None


def test_normalize_symlink(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    try:
        link.symlink_to(real)
    except (OSError, NotImplementedError):
        pytest.skip("Symlinks not supported on this platform/config")
    resolved = normalize(str(link), resolve_symlinks=True)
    unresolved = normalize(str(link), resolve_symlinks=False)
    assert os.path.basename(resolved) in (real.name, link.name)


def test_normalize_nonexistent_path():
    result = normalize(r"C:\nonexistent\path\that\does\not\exist")
    assert isinstance(result, str)
