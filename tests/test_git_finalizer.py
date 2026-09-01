import subprocess
from pathlib import Path

import pytest

from core.database import ParkLease, get_db_session
from src import git_finalizer, worktree_ops
from src.park_lease_ops import park_repo


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
    subprocess.run(["git", "-C", str(path), "remote", "add", "origin", str(path) + "-bare.git"], check=True)
    (path / "tracked.txt").write_text("base\n")
    subprocess.run(["git", "-C", str(path), "add", "tracked.txt"], check=True)
    subprocess.run(["git", "-C", str(path), "commit", "-q", "-m", "init"], check=True)
    return path


@pytest.fixture(autouse=True)
def _clean_leases():
    with get_db_session() as db:
        db.query(ParkLease).filter(ParkLease.repo_id == "finalizer-repo").delete(synchronize_session=False)
    yield
    with get_db_session() as db:
        db.query(ParkLease).filter(ParkLease.repo_id == "finalizer-repo").delete(synchronize_session=False)


@pytest.fixture
def isolated_worktree(tmp_path, monkeypatch):
    """A registered live checkout with a real bare origin remote, plus a
    real isolated linked worktree on a feature branch, plus a matching
    active ParkLease pointed at that worktree - the exact shape
    finalize_scoped() is meant to operate on."""
    import src.estate_router as estate_router

    live_path = _init_repo(tmp_path / "projects" / "finalizer-repo")
    bare_path = tmp_path / "projects" / "finalizer-repo-bare.git"
    subprocess.run(["git", "init", "-q", "--bare", str(bare_path)], check=True)
    subprocess.run(["git", "-C", str(live_path), "push", "-q", "origin", "main"], check=True)

    repo_id = "finalizer-repo"
    host_id = "test-lab"
    branch = "feature/finalize-demo"
    monkeypatch.setattr(
        estate_router, "resolve_repo_path",
        lambda requested: str(live_path) if requested == repo_id else None,
    )

    created = worktree_ops.create_or_reuse_worktree(repo_id, branch, base_ref="main")
    worktree_path = Path(created["path"])
    park_repo(repo_id, host_id, str(worktree_path), branch=branch)

    return repo_id, host_id, branch, worktree_path


def test_finalize_stages_and_commits_only_the_allowed_files(isolated_worktree):
    repo_id, host_id, branch, worktree_path = isolated_worktree
    (worktree_path / "src_change.py").write_text("x = 1\n")

    result = git_finalizer.finalize_scoped(
        repo_id, host_id,
        expected_branch=branch,
        allowed_paths=["src_change.py"],
        commit_message="feat: add src_change.py",
        push=True,
    )

    assert result["finalized"] is True
    assert result["committed"] is True
    assert result["pushed"] is True
    assert result["staged_paths"] == ["src_change.py"]
    assert _git("status", "--porcelain", cwd=worktree_path) == ""
    log = _git("log", "-1", "--name-only", "--format=", cwd=worktree_path)
    assert log.strip() == "src_change.py"


def test_finalize_rejects_dirty_file_outside_allowed_scope(isolated_worktree):
    repo_id, host_id, branch, worktree_path = isolated_worktree
    (worktree_path / "src_change.py").write_text("x = 1\n")
    (worktree_path / "tracked.txt").write_text("unexpected edit\n")

    result = git_finalizer.finalize_scoped(
        repo_id, host_id,
        expected_branch=branch,
        allowed_paths=["src_change.py"],
        commit_message="feat: add src_change.py",
    )

    assert result["finalized"] is False
    assert result["reason"] == "scope_violation"
    assert result["unexpected_paths"] == ["tracked.txt"]
    # Nothing was staged or committed - the whole call refused, not a
    # partial commit of just the allowed file.
    status = _git("status", "--porcelain", cwd=worktree_path)
    assert "src_change.py" in status
    assert "tracked.txt" in status
    assert _git("log", "-1", "--format=%s", cwd=worktree_path) == "init"


def test_finalize_rejects_untracked_file_outside_allowed_scope(isolated_worktree):
    repo_id, host_id, branch, worktree_path = isolated_worktree
    (worktree_path / "src_change.py").write_text("x = 1\n")
    (worktree_path / "stray_debug_notes.txt").write_text("oops, forgot this was here\n")

    result = git_finalizer.finalize_scoped(
        repo_id, host_id,
        expected_branch=branch,
        allowed_paths=["src_change.py"],
        commit_message="feat: add src_change.py",
    )

    assert result["finalized"] is False
    assert result["reason"] == "scope_violation"
    assert result["unexpected_paths"] == ["stray_debug_notes.txt"]
    assert (worktree_path / "stray_debug_notes.txt").exists()
    status = _git("status", "--porcelain", cwd=worktree_path)
    assert "?? stray_debug_notes.txt" in status


def test_finalize_never_uses_add_dash_a(isolated_worktree, monkeypatch):
    """Deterministic proof the recovered git add -A pattern is gone, not
    just that the observable behaviour looks safe: fail the test outright
    if -A is ever passed to git add."""
    repo_id, host_id, branch, worktree_path = isolated_worktree
    (worktree_path / "src_change.py").write_text("x = 1\n")

    import src.git_finalizer as gf
    real_run_git = gf._run_git

    def _guarded_run_git(repo_path, args, **kwargs):
        if args and args[0] == "add":
            assert "-A" not in args and "--all" not in args, f"git add invoked with -A/--all: {args}"
        return real_run_git(repo_path, args, **kwargs)

    monkeypatch.setattr(gf, "_run_git", _guarded_run_git)

    result = gf.finalize_scoped(
        repo_id, host_id,
        expected_branch=branch,
        allowed_paths=["src_change.py"],
        commit_message="feat: add src_change.py",
    )
    assert result["finalized"] is True


def test_finalize_refuses_live_checkout_even_if_leased(tmp_path, monkeypatch):
    import src.estate_router as estate_router

    live_path = _init_repo(tmp_path / "projects" / "finalizer-repo")
    repo_id = "finalizer-repo"
    host_id = "test-lab"
    monkeypatch.setattr(
        estate_router, "resolve_repo_path",
        lambda requested: str(live_path) if requested == repo_id else None,
    )
    park_repo(repo_id, host_id, str(live_path), branch="main")
    (live_path / "src_change.py").write_text("x = 1\n")

    result = git_finalizer.finalize_scoped(
        repo_id, host_id,
        expected_branch="main",
        allowed_paths=["src_change.py"],
        commit_message="feat: add src_change.py",
    )

    assert result["finalized"] is False
    assert "live registered checkout" in result["reason"]
    assert _git("log", "-1", "--format=%s", cwd=live_path) == "init"


def test_finalize_reports_no_changes_when_worktree_already_clean(isolated_worktree):
    repo_id, host_id, branch, worktree_path = isolated_worktree

    result = git_finalizer.finalize_scoped(
        repo_id, host_id,
        expected_branch=branch,
        allowed_paths=["src_change.py"],
        commit_message="feat: add src_change.py",
    )

    assert result["finalized"] is False
    assert result["reason"] == "no_changes_to_finalize"


def test_finalize_requires_allowed_paths():
    result = git_finalizer.finalize_scoped(
        "finalizer-repo", "test-lab",
        expected_branch="main",
        allowed_paths=[],
        commit_message="feat: nothing",
    )
    assert result["finalized"] is False
    assert result["reason"] == "no_allowed_paths_supplied"
