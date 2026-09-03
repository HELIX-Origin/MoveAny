"""Integration tests for moveany CLI commands.

All tests use click.testing.CliRunner with isolated temporary directories.
No real user data is touched.
"""

import json
import os
import pathlib

import pytest
from click.testing import CliRunner

from moveany.cli import cli


@pytest.fixture()
def runner():
    return CliRunner()


@pytest.fixture()
def src_tree(tmp_path):
    """Create a small source tree."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "hello.txt").write_text("hello world")
    (src / "sub").mkdir()
    (src / "sub" / "data.bin").write_bytes(b"\x00\x01\x02\x03")
    return src


@pytest.fixture()
def dst_tree(tmp_path):
    """Empty destination directory."""
    dst = tmp_path / "dst"
    dst.mkdir()
    return dst


# ---------------------------------------------------------------------------
# help / version
# ---------------------------------------------------------------------------

def test_help(runner):
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "copy" in result.output
    assert "move" in result.output
    assert "gui" in result.output
    assert "config" in result.output


def test_version(runner):
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "moveany" in result.output.lower()


# ---------------------------------------------------------------------------
# list-batches
# ---------------------------------------------------------------------------

def test_list_batches(runner, src_tree, dst_tree):
    result = runner.invoke(cli, [
        "list-batches",
        "--source", str(src_tree),
        "--dest", str(dst_tree),
    ])
    assert result.exit_code == 0, result.output


# ---------------------------------------------------------------------------
# copy
# ---------------------------------------------------------------------------

def test_copy_basic(runner, src_tree, dst_tree):
    result = runner.invoke(cli, [
        "copy",
        "--source", str(src_tree),
        "--dest", str(dst_tree),
    ])
    assert result.exit_code == 0, result.output
    assert (dst_tree / "hello.txt").exists()
    assert (dst_tree / "sub" / "data.bin").exists()


# ---------------------------------------------------------------------------
# verify (after copy)
# ---------------------------------------------------------------------------

def test_verify_after_copy(runner, src_tree, dst_tree):
    runner.invoke(cli, ["copy", "--source", str(src_tree), "--dest", str(dst_tree)])
    result = runner.invoke(cli, [
        "verify",
        "--source", str(src_tree),
        "--dest", str(dst_tree),
    ])
    assert result.exit_code == 0, result.output


# ---------------------------------------------------------------------------
# repair
# ---------------------------------------------------------------------------

def test_repair_after_corrupt(runner, src_tree, dst_tree):
    runner.invoke(cli, ["copy", "--source", str(src_tree), "--dest", str(dst_tree)])
    (dst_tree / "hello.txt").write_text("CORRUPTED")
    result = runner.invoke(cli, [
        "repair",
        "--source", str(src_tree),
        "--dest", str(dst_tree),
    ])
    assert result.exit_code == 0, result.output
    assert (dst_tree / "hello.txt").read_text() == "hello world"


# ---------------------------------------------------------------------------
# delete (requires verify pass first, needs --yes flag)
# ---------------------------------------------------------------------------

def test_delete_after_verified_copy(runner, src_tree, dst_tree):
    runner.invoke(cli, ["copy", "--source", str(src_tree), "--dest", str(dst_tree)])
    result = runner.invoke(cli, [
        "delete",
        "--source", str(src_tree),
        "--dest", str(dst_tree),
        "--yes",
    ])
    assert result.exit_code == 0, result.output



# ---------------------------------------------------------------------------
# history
# ---------------------------------------------------------------------------

def test_history_table(runner):
    result = runner.invoke(cli, ["history", "--limit", "5"])
    assert result.exit_code == 0, result.output


def test_history_json(runner):
    result = runner.invoke(cli, ["history", "--limit", "5", "--json"])
    assert result.exit_code == 0, result.output
    parsed = json.loads(result.output)
    assert isinstance(parsed, list)


def test_history_json_schema(runner, src_tree, dst_tree):
    runner.invoke(cli, ["copy", "--source", str(src_tree), "--dest", str(dst_tree)])
    result = runner.invoke(cli, ["history", "--limit", "1", "--json"])
    assert result.exit_code == 0, result.output
    records = json.loads(result.output)
    if records:
        rec = records[0]
        assert "id" in rec
        assert "op" in rec
        assert "status" in rec
        assert "started_at" in rec


# ---------------------------------------------------------------------------
# exclude
# ---------------------------------------------------------------------------

def test_exclude_list(runner):
    result = runner.invoke(cli, ["exclude", "list"])
    assert result.exit_code == 0, result.output


def test_exclude_add_remove(runner):
    runner.invoke(cli, ["exclude", "add", "__pycache__"])
    result = runner.invoke(cli, ["exclude", "list"])
    assert "__pycache__" in result.output

    runner.invoke(cli, ["exclude", "remove", "__pycache__"])
    runner.invoke(cli, ["exclude", "reset"])


# ---------------------------------------------------------------------------
# config
# ---------------------------------------------------------------------------

def test_config_show(runner):
    result = runner.invoke(cli, ["config", "show"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert "exclusions" in data
    assert "state" in data


def test_config_reset(runner):
    result = runner.invoke(cli, ["config", "reset", "--yes"])
    assert result.exit_code == 0, result.output
    assert "reset" in result.output.lower()
