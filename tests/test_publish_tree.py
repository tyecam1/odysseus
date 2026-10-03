"""Tests for the tree publisher's pure planning logic (no network)."""

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import publish_tree  # noqa: E402


def test_blob_sha_matches_git_hash_object(tmp_path):
    data = b"hello\nworld\n"
    sample = tmp_path / "x.txt"
    sample.write_bytes(data)
    expected = subprocess.run(["git", "hash-object", str(sample)], capture_output=True, text=True, check=True).stdout.strip()
    assert publish_tree.blob_sha(data) == expected


def _remote(**files):
    return {path: {"sha": publish_tree.blob_sha(data), "mode": "100644"} for path, data in files.items()}


def test_plan_reports_new_changed_and_deleted_only_under_prefixes():
    remote = _remote(**{"a/keep.md": b"same", "a/change.md": b"old", "a/gone.md": b"x", "z/other.md": b"untouched"})
    local = {"a/keep.md": b"same", "a/change.md": b"new", "a/add.md": b"fresh", "z/other.md": b"DIFFERENT"}
    assert publish_tree.plan(remote, local, ["a/"]) == [("new", "a/add.md"), ("update", "a/change.md"), ("delete", "a/gone.md")]


def test_a_move_is_a_new_file_plus_a_delete():
    remote = _remote(**{"inbox/t.md": b"body"})
    local = {"done/t.md": b"body"}
    assert publish_tree.plan(remote, local, ["inbox/t", "done/t"]) == [("new", "done/t.md"), ("delete", "inbox/t.md")]


def test_exact_path_prefixes_do_not_delete_neighbours():
    remote = _remote(**{"inbox/t1.md": b"a", "inbox/t2.md": b"b"})
    assert publish_tree.plan(remote, {}, ["inbox/t1.md"]) == [("delete", "inbox/t1.md")]


def test_pycache_is_never_published_or_deleted():
    remote = _remote(**{"s/__pycache__/m.pyc": b"x"})
    assert publish_tree.plan(remote, {"s/__pycache__/n.pyc": b"y"}, ["s/"]) == []


def test_unchanged_tree_plans_nothing():
    remote = _remote(**{"a.md": b"1"})
    assert publish_tree.plan(remote, {"a.md": b"1"}, ["a.md"]) == []


def test_a_plan_that_deletes_a_whole_directory_is_refused():
    remote = _remote(**{f"tasks/t{i}.md": b"x" for i in range(40)})
    actions = publish_tree.plan(remote, {"tasks/edited.md": b"new"}, ["tasks/"])
    assert publish_tree.too_many_deletes(actions, publish_tree.DEFAULT_MAX_DELETES) == 40
    assert publish_tree.too_many_deletes(actions, 100) == 0                  # a deliberate bulk delete can raise the limit
    small = publish_tree.plan(_remote(**{"a.md": b"1"}), {}, ["a.md"])
    assert publish_tree.too_many_deletes(small, publish_tree.DEFAULT_MAX_DELETES) == 0
