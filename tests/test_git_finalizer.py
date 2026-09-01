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
    finalize_scoped() is meant to operate on. `head` is the worktree's
    HEAD at fixture setup time - the task's authorised starting commit,
    the value every finalize_scoped() call in these tests must supply as
    expected_head unless a test is deliberately exercising a mismatch."""
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
    head = _git("rev-parse", "HEAD", cwd=worktree_path)

    return repo_id, host_id, branch, worktree_path, head


def test_finalize_stages_and_commits_only_the_allowed_files(isolated_worktree):
    repo_id, host_id, branch, worktree_path, head = isolated_worktree
    (worktree_path / "src_change.py").write_text("x = 1\n")

    result = git_finalizer.finalize_scoped(
        repo_id, host_id,
        expected_branch=branch,
        expected_head=head,
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
    # The commit's own parent must be exactly the authorised starting
    # HEAD - the direct proof this task's commit was built on top of
    # nothing else.
    assert _git("log", "-1", "--format=%P", cwd=worktree_path) == head


def test_finalize_rejects_dirty_file_outside_allowed_scope(isolated_worktree):
    repo_id, host_id, branch, worktree_path, head = isolated_worktree
    (worktree_path / "src_change.py").write_text("x = 1\n")
    (worktree_path / "tracked.txt").write_text("unexpected edit\n")

    result = git_finalizer.finalize_scoped(
        repo_id, host_id,
        expected_branch=branch,
        expected_head=head,
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
    repo_id, host_id, branch, worktree_path, head = isolated_worktree
    (worktree_path / "src_change.py").write_text("x = 1\n")
    (worktree_path / "stray_debug_notes.txt").write_text("oops, forgot this was here\n")

    result = git_finalizer.finalize_scoped(
        repo_id, host_id,
        expected_branch=branch,
        expected_head=head,
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
    repo_id, host_id, branch, worktree_path, head = isolated_worktree
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
        expected_head=head,
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
    head = _git("rev-parse", "HEAD", cwd=live_path)
    (live_path / "src_change.py").write_text("x = 1\n")

    result = git_finalizer.finalize_scoped(
        repo_id, host_id,
        expected_branch="main",
        expected_head=head,
        allowed_paths=["src_change.py"],
        commit_message="feat: add src_change.py",
    )

    assert result["finalized"] is False
    assert "live registered checkout" in result["reason"]
    assert _git("log", "-1", "--format=%s", cwd=live_path) == "init"


def test_finalize_reports_no_changes_when_worktree_already_clean(isolated_worktree):
    repo_id, host_id, branch, worktree_path, head = isolated_worktree

    result = git_finalizer.finalize_scoped(
        repo_id, host_id,
        expected_branch=branch,
        expected_head=head,
        allowed_paths=["src_change.py"],
        commit_message="feat: add src_change.py",
    )

    assert result["finalized"] is False
    assert result["reason"] == "no_changes_to_finalize"


def test_finalize_rejects_directory_level_allowed_path(isolated_worktree):
    repo_id, host_id, branch, worktree_path, head = isolated_worktree
    (worktree_path / "dir").mkdir()
    (worktree_path / "dir" / "allowed.txt").write_text("a\n")

    result = git_finalizer.finalize_scoped(
        repo_id, host_id, expected_branch=branch, expected_head=head,
        allowed_paths=["dir/"],
        commit_message="feat: x",
    )

    assert result["finalized"] is False
    assert result["reason"].startswith("invalid_allowed_path")
    assert _git("log", "-1", "--format=%s", cwd=worktree_path) == "init"


def test_finalize_rejects_stray_nested_file_when_only_one_file_in_dir_is_allowed(isolated_worktree):
    repo_id, host_id, branch, worktree_path, head = isolated_worktree
    (worktree_path / "dir").mkdir()
    (worktree_path / "dir" / "allowed.txt").write_text("a\n")
    (worktree_path / "dir" / "stray.txt").write_text("b\n")

    result = git_finalizer.finalize_scoped(
        repo_id, host_id, expected_branch=branch, expected_head=head,
        allowed_paths=["dir/allowed.txt"],
        commit_message="feat: x",
    )

    assert result["finalized"] is False
    assert result["reason"] == "scope_violation"
    assert result["unexpected_paths"] == ["dir/stray.txt"]
    assert _git("log", "-1", "--format=%s", cwd=worktree_path) == "init"


def test_finalize_succeeds_for_exact_nested_file_with_no_stray_sibling(isolated_worktree):
    repo_id, host_id, branch, worktree_path, head = isolated_worktree
    (worktree_path / "dir").mkdir()
    (worktree_path / "dir" / "allowed.txt").write_text("a\n")

    result = git_finalizer.finalize_scoped(
        repo_id, host_id, expected_branch=branch, expected_head=head,
        allowed_paths=["dir/allowed.txt"],
        commit_message="feat: x",
    )

    assert result["finalized"] is True
    assert result["staged_paths"] == ["dir/allowed.txt"]


def test_finalize_handles_filenames_with_spaces_quotes_and_literal_arrow(isolated_worktree):
    repo_id, host_id, branch, worktree_path, head = isolated_worktree
    tricky_name = 'weird "name" with -> arrow and spaces.txt'
    (worktree_path / tricky_name).write_text("x\n")

    result = git_finalizer.finalize_scoped(
        repo_id, host_id, expected_branch=branch, expected_head=head,
        allowed_paths=[tricky_name],
        commit_message="feat: tricky filename",
    )

    assert result["finalized"] is True
    assert result["staged_paths"] == [tricky_name]


def test_finalize_requires_both_names_of_a_real_rename_to_be_allowed(isolated_worktree):
    repo_id, host_id, branch, worktree_path, head = isolated_worktree
    (worktree_path / "old_name.txt").write_text("line one\nline two\nline three\nline four\nline five\n")
    subprocess.run(["git", "-C", str(worktree_path), "add", "old_name.txt"], check=True)
    subprocess.run(["git", "-C", str(worktree_path), "commit", "-q", "-m", "add old_name.txt"], check=True)
    head = _git("rev-parse", "HEAD", cwd=worktree_path)
    (worktree_path / "old_name.txt").rename(worktree_path / "new_name.txt")

    only_new_name = git_finalizer.finalize_scoped(
        repo_id, host_id, expected_branch=branch, expected_head=head,
        allowed_paths=["new_name.txt"],
        commit_message="feat: rename",
    )
    assert only_new_name["finalized"] is False
    assert only_new_name["reason"] == "scope_violation"
    assert only_new_name["unexpected_paths"] == ["old_name.txt"]

    both_names = git_finalizer.finalize_scoped(
        repo_id, host_id, expected_branch=branch, expected_head=head,
        allowed_paths=["new_name.txt", "old_name.txt"],
        commit_message="feat: rename",
    )
    assert both_names["finalized"] is True


@pytest.mark.parametrize("bad_path", [
    "/etc/passwd",
    "../outside.txt",
    "a/../../outside.txt",
    "dir/",
    "./file.txt",
    ".",
    "..",
    "",
    ":(icase)file.txt",
])
def test_finalize_rejects_unsafe_allowed_paths_before_touching_git(isolated_worktree, bad_path):
    repo_id, host_id, branch, worktree_path, head = isolated_worktree
    (worktree_path / "real_change.txt").write_text("x\n")

    result = git_finalizer.finalize_scoped(
        repo_id, host_id, expected_branch=branch, expected_head=head,
        allowed_paths=[bad_path],
        commit_message="feat: x",
    )

    assert result["finalized"] is False
    assert result["reason"].startswith("invalid_allowed_path")
    assert _git("log", "-1", "--format=%s", cwd=worktree_path) == "init"
    assert _git("status", "--porcelain", cwd=worktree_path) != ""


def test_finalize_rejects_allowed_path_resolving_outside_worktree_via_symlink(isolated_worktree, tmp_path):
    repo_id, host_id, branch, worktree_path, head = isolated_worktree
    outside = tmp_path / "outside_target.txt"
    outside.write_text("should never be touched\n")
    (worktree_path / "escape_link").symlink_to(outside)

    result = git_finalizer.finalize_scoped(
        repo_id, host_id, expected_branch=branch, expected_head=head,
        allowed_paths=["escape_link"],
        commit_message="feat: x",
    )

    assert result["finalized"] is False
    assert result["reason"].startswith("invalid_allowed_path")


def test_finalize_detects_concurrent_write_between_initial_check_and_commit(isolated_worktree, monkeypatch):
    repo_id, host_id, branch, worktree_path, head = isolated_worktree
    (worktree_path / "allowed.txt").write_text("a\n")

    import src.git_finalizer as gf
    real_status_paths = gf._status_paths
    calls = {"n": 0}

    def _racy_status_paths(repo_path):
        calls["n"] += 1
        result = real_status_paths(repo_path)
        if calls["n"] == 1:
            (worktree_path / "raced_in.txt").write_text("surprise\n")
        return result

    monkeypatch.setattr(gf, "_status_paths", _racy_status_paths)

    result = gf.finalize_scoped(
        repo_id, host_id, expected_branch=branch, expected_head=head,
        allowed_paths=["allowed.txt"],
        commit_message="feat: x",
    )

    assert result["finalized"] is False
    assert result["reason"] == "concurrent_write_detected"
    assert result["unexpected_paths"] == ["raced_in.txt"]
    assert _git("log", "-1", "--format=%s", cwd=worktree_path) == "init"


def test_finalize_refuses_success_if_residual_dirt_appears_after_commit(isolated_worktree, monkeypatch):
    repo_id, host_id, branch, worktree_path, head = isolated_worktree
    (worktree_path / "allowed.txt").write_text("a\n")

    import src.git_finalizer as gf
    real_run_git = gf._run_git

    def _run_git_then_dirty(repo_path, args, **kwargs):
        result = real_run_git(repo_path, args, **kwargs)
        if args and args[0] == "commit":
            (worktree_path / "post_commit_surprise.txt").write_text("oops\n")
        return result

    monkeypatch.setattr(gf, "_run_git", _run_git_then_dirty)

    result = gf.finalize_scoped(
        repo_id, host_id, expected_branch=branch, expected_head=head,
        allowed_paths=["allowed.txt"],
        commit_message="feat: x",
        push=True,
    )

    assert result["finalized"] is False
    assert result["committed"] is True
    assert result["reason"] == "residual_dirty_state_after_commit"
    assert result["unexpected_paths"] == ["post_commit_surprise.txt"]
    assert "pushed" not in result
    # The local commit is not rolled back (no silent reset/discard), but
    # it must never have reached origin.
    log = _git("log", "-1", "--format=%s", cwd=worktree_path)
    assert log == "feat: x"


def test_finalize_requires_allowed_paths():
    result = git_finalizer.finalize_scoped(
        "finalizer-repo", "test-lab",
        expected_branch="main",
        expected_head="0" * 40,
        allowed_paths=[],
        commit_message="feat: nothing",
    )
    assert result["finalized"] is False
    assert result["reason"] == "no_allowed_paths_supplied"


def test_finalize_rejects_stale_branch_with_unrelated_commit_ahead_of_expected_head(isolated_worktree):
    """The controller-identified defect: file scope alone does not bound
    history. A reused/stale isolated branch can already carry an
    unrelated commit B on top of the task's real authorised base A while
    the working tree is completely clean of it - all file-scope checks
    would pass, and pushing the task's own scope-correct commit on top
    would publish B too. expected_head must catch this immediately, on
    the very first worktree verification, before any file scope is even
    considered."""
    repo_id, host_id, branch, worktree_path, authorised_head = isolated_worktree

    # Simulate a previous/other agent leaving an unrelated commit B on
    # this same branch after the task's real authorised base.
    (worktree_path / "unrelated_file.py").write_text("leftover = True\n")
    subprocess.run(["git", "-C", str(worktree_path), "add", "unrelated_file.py"], check=True)
    subprocess.run(["git", "-C", str(worktree_path), "commit", "-q", "-m", "unrelated commit B"], check=True)

    # The current task's own, entirely legitimate, in-scope change.
    (worktree_path / "allowed.py").write_text("x = 1\n")

    result = git_finalizer.finalize_scoped(
        repo_id, host_id,
        expected_branch=branch,
        expected_head=authorised_head,
        allowed_paths=["allowed.py"],
        commit_message="feat: allowed change",
    )

    assert result["finalized"] is False
    assert result["reason"].startswith("worktree_verification_failed")
    assert "head_mismatch" in result["reason"] or "HEAD mismatch" in result["reason"]
    # Nothing was pushed - the bare origin must not have moved past main.
    origin_refs = subprocess.run(
        ["git", "-C", str(worktree_path), "ls-remote", "origin", branch],
        capture_output=True, text=True, check=True,
    ).stdout
    assert origin_refs.strip() == ""


def test_finalize_rejects_when_head_moves_after_initial_verification_but_before_commit(isolated_worktree, monkeypatch):
    """A concurrent writer race distinct from the file-scope race already
    covered above: something else commits onto the branch AFTER
    verify_worktree's initial expected_head check has already passed
    (e.g. it ran in the small window before this call started touching
    the worktree at all), but before this call actually commits. The
    pre-commit HEAD re-check must catch this even though the earlier,
    file-scope-only race detection would not (that only watches the
    working tree, not the branch tip itself)."""
    repo_id, host_id, branch, worktree_path, head = isolated_worktree
    (worktree_path / "allowed.py").write_text("x = 1\n")

    import src.git_finalizer as gf
    real_verify_worktree = worktree_ops.verify_worktree
    calls = {"n": 0}

    def _racy_verify_worktree(*args, **kwargs):
        calls["n"] += 1
        result = real_verify_worktree(*args, **kwargs)
        if calls["n"] == 1 and result["ok"]:
            # Inject a commit onto the branch immediately after the
            # initial verification succeeded, simulating another writer.
            (worktree_path / "raced_commit_file.py").write_text("intruder = True\n")
            subprocess.run(["git", "-C", str(worktree_path), "add", "raced_commit_file.py"], check=True)
            subprocess.run(["git", "-C", str(worktree_path), "commit", "-q", "-m", "raced-in commit"], check=True)
        return result

    monkeypatch.setattr(gf.worktree_ops, "verify_worktree", _racy_verify_worktree)

    result = gf.finalize_scoped(
        repo_id, host_id, expected_branch=branch, expected_head=head,
        allowed_paths=["allowed.py"],
        commit_message="feat: allowed change",
    )

    assert result["finalized"] is False
    assert result["reason"] == "head_moved_before_commit"
    assert result["expected_head"] == head
    assert result["actual_head"] != head
    # The task's own commit must never have been created on top of the
    # raced-in one.
    log = _git("log", "-1", "--format=%s", cwd=worktree_path)
    assert log == "raced-in commit"
    origin_refs = subprocess.run(
        ["git", "-C", str(worktree_path), "ls-remote", "origin", branch],
        capture_output=True, text=True, check=True,
    ).stdout
    assert origin_refs.strip() == ""
