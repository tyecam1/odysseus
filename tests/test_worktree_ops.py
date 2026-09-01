import subprocess
from pathlib import Path

import pytest

from src import worktree_ops


def _git(*args: str, cwd: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _init_repo(path: Path) -> Path:
    subprocess.run(["git", "init", "-q", "-b", "main", str(path)], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "Test User"], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.email", "test@example.com"], check=True)
    (path / "tracked.txt").write_text("base\n")
    subprocess.run(["git", "-C", str(path), "add", "tracked.txt"], check=True)
    subprocess.run(["git", "-C", str(path), "commit", "-q", "-m", "init"], check=True)
    return path


@pytest.fixture
def registered_repo(tmp_path, monkeypatch):
    import src.estate_router as estate_router

    repo_path = _init_repo(tmp_path / "projects" / "live-checkout")
    repo_id = "worktree-repo"
    monkeypatch.setattr(estate_router, "resolve_repo_path", lambda requested_repo_id: str(repo_path) if requested_repo_id == repo_id else None)
    return repo_id, repo_path


def test_create_or_reuse_worktree_checks_out_the_real_requested_branch(registered_repo):
    repo_id, repo_path = registered_repo

    created = worktree_ops.create_or_reuse_worktree(repo_id, "feature/demo")

    assert created["created"] is True
    assert Path(created["path"]).exists()
    assert Path(created["path"]).parent == repo_path.parent.parent / "aoteru-worktrees" / repo_id
    assert _git("rev-parse", "--abbrev-ref", "HEAD", cwd=Path(created["path"])) == "feature/demo"
    verification = worktree_ops.verify_worktree(repo_id, created["path"], "feature/demo")
    assert verification["ok"] is True


def test_reusing_existing_matching_worktree_does_not_recreate_it(registered_repo):
    repo_id, repo_path = registered_repo

    first = worktree_ops.create_or_reuse_worktree(repo_id, "feature-reuse")
    second = worktree_ops.create_or_reuse_worktree(repo_id, "feature-reuse")

    assert first["created"] is True
    assert second["created"] is False
    assert second["path"] == first["path"]
    entries = worktree_ops._parse_worktree_list(_git("worktree", "list", "--porcelain", cwd=repo_path))
    matching_paths = [entry for entry in entries if entry.get("worktree") == first["path"]]
    assert len(matching_paths) == 1


def test_is_live_checkout_path_distinguishes_live_checkout_from_real_worktree(registered_repo):
    repo_id, repo_path = registered_repo
    created = worktree_ops.create_or_reuse_worktree(repo_id, "feature-live-check")

    assert worktree_ops.is_live_checkout_path(repo_id, str(repo_path)) is True
    assert worktree_ops.is_live_checkout_path(repo_id, created["path"]) is False


def test_cleanup_worktree_refuses_dirty_tree_and_succeeds_on_clean_one(registered_repo):
    repo_id, repo_path = registered_repo
    dirty = worktree_ops.create_or_reuse_worktree(repo_id, "feature-dirty")
    clean = worktree_ops.create_or_reuse_worktree(repo_id, "feature-clean")
    dirty_path = Path(dirty["path"])
    clean_path = Path(clean["path"])
    (dirty_path / "dirty.txt").write_text("pending\n")

    dirty_result = worktree_ops.cleanup_worktree(repo_id, str(dirty_path), expected_branch="feature-dirty")
    clean_result = worktree_ops.cleanup_worktree(repo_id, str(clean_path), expected_branch="feature-clean")

    assert dirty_result["ok"] is False
    assert dirty_result["code"] == "dirty"
    assert dirty_path.exists()
    assert clean_result == {"ok": True, "path": str(clean_path), "removed": True}
    assert not clean_path.exists()
    remaining = _git("worktree", "list", "--porcelain", cwd=repo_path)
    assert str(dirty_path) in remaining
    assert str(clean_path) not in remaining


def test_create_or_reuse_worktree_catches_timeout_during_add(registered_repo, monkeypatch):
    repo_id, _repo_path = registered_repo

    monkeypatch.setattr(worktree_ops, "_branch_exists", lambda repo_path, branch: True)
    original_run_git = worktree_ops._run_git

    def fake_run_git(args, *, cwd, timeout=30):
        if args[:2] == ["worktree", "add"]:
            raise subprocess.TimeoutExpired(cmd=["git", *args], timeout=timeout)
        return original_run_git(args, cwd=cwd, timeout=timeout)

    monkeypatch.setattr(worktree_ops, "_run_git", fake_run_git)

    with pytest.raises(RuntimeError, match="git worktree add failed"):
        worktree_ops.create_or_reuse_worktree(repo_id, "feature-timeout")
