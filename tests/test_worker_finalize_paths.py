"""Regression tests for worker-owned finalisation of awkward paths and scope.

/lazyUsage run b5db0e86 finalised through the worker. `_finalize_logic` parsed
text-mode `git status --porcelain`, which (a) renders a staged rename as one
`old -> new` token that is then passed to `git add` as a single pathspec, and
(b) quotes/escapes names with spaces, quotes or non-ASCII bytes. Both made
finalisation fail, and a failed finalise closes the execution, so the controller
had to recover by hand. The worker also never enforced the card's path scope, so
a writer could commit outside the review-side area or edit its own task card.
"""
import pytest

from tests.test_estate_worker_stage6 import _finalize_request, _git, _spool, cfg, repo  # noqa: F401
from src import estate_worker


def _finalize(repo, **extra):
    return estate_worker._finalize_logic("E1", _spool("E1"), {**_finalize_request(repo), **extra})


def _tree(wt):
    return set(_git(wt, "ls-tree", "-r", "--name-only", "HEAD").splitlines())


def test_a_staged_rename_is_committed_as_both_sides(cfg, repo):
    wt = repo["wt"]
    (wt / "old name.txt").write_text("content that is long enough to be detected as a rename\n" * 5)
    _git(wt, "add", "old name.txt")
    _git(wt, "commit", "-q", "-m", "add")
    head = _git(wt, "rev-parse", "HEAD")
    _git(wt, "mv", "old name.txt", "new name.txt")           # staged rename: status prints `R  old -> new`
    done = _finalize(repo, expected_head_sha=head)
    assert done["outcome"] == "finalized" and done["committed"] is True, done
    assert "new name.txt" in _tree(wt) and "old name.txt" not in _tree(wt)
    assert _git(wt, "status", "--porcelain") == ""
    assert sorted(done["dirty_paths"]) == ["new name.txt", "old name.txt"]


def test_quoted_and_non_ascii_names_are_committed_by_their_real_name(cfg, repo):
    wt = repo["wt"]
    tracked = 'déjà "vu".txt'
    (wt / tracked).write_text("v1\n")
    _git(wt, "add", "--", tracked)
    _git(wt, "commit", "-q", "-m", "add")
    head = _git(wt, "rev-parse", "HEAD")
    (wt / tracked).write_text("v2\n")
    (wt / "tab\there.txt").write_text("untracked with a tab\n")
    (wt / "a -> b.txt").write_text("a literal arrow in the name\n")
    done = _finalize(repo, expected_head_sha=head)
    assert done["outcome"] == "finalized" and done["committed"] is True, done
    names = _git(wt, "-c", "core.quotepath=false", "ls-tree", "-r", "--name-only", "-z", "HEAD")
    tree = {n for n in names.split("\0") if n}
    assert {tracked, "tab\there.txt", "a -> b.txt"} <= tree
    assert _git(wt, "status", "--porcelain") == ""


def test_out_of_scope_paths_are_discarded_not_committed(cfg, repo):
    wt = repo["wt"]
    (wt / "automation" / "review" / "agent-tasks").mkdir(parents=True)
    (wt / "automation" / "review" / "agent-tasks" / "card.md").write_text("status: ready\n")
    (wt / "src").mkdir()
    (wt / "src" / "canon.py").write_text("canonical\n")
    _git(wt, "add", "-A")
    _git(wt, "commit", "-q", "-m", "seed")
    head = _git(wt, "rev-parse", "HEAD")
    (wt / "automation" / "review" / "report.md").write_text("review-side artifact\n")        # in scope
    (wt / "automation" / "review" / "agent-tasks" / "card.md").write_text("status: done\n")   # denied: self-approval
    (wt / "src" / "canon.py").write_text("tampered\n")                                        # outside allowed
    (wt / "src" / "new.py").write_text("untracked and outside\n")
    done = _finalize(repo, expected_head_sha=head, allowed_paths=["automation/review/**"],
                     denied_paths=["automation/review/agent-tasks/**"])
    assert done["outcome"] == "finalized" and done["committed"] is True, done
    assert done["scope_violations"] == ["automation/review/agent-tasks/card.md", "src/canon.py", "src/new.py"]
    assert _tree(wt) >= {"automation/review/report.md"}
    assert _git(wt, "show", "HEAD:src/canon.py") == "canonical"
    assert _git(wt, "show", "HEAD:automation/review/agent-tasks/card.md") == "status: ready"
    assert not (wt / "src" / "new.py").exists()
    assert _git(wt, "status", "--porcelain") == ""
    assert sorted(done["dirty_paths"]) == ["automation/review/report.md"]


def test_only_out_of_scope_changes_commit_nothing_and_report_the_violation(cfg, repo):
    wt = repo["wt"]
    (wt / "README").write_text("tampered\n")
    done = _finalize(repo, allowed_paths=["automation/review/**"])
    assert done["outcome"] == "finalized" and done["committed"] is False, done
    assert done["scope_violations"] == ["README"]
    assert _git(wt, "rev-parse", "HEAD") == repo["head"] and _git(wt, "status", "--porcelain") == ""


def test_scope_is_not_enforced_when_the_request_carries_none(cfg, repo):
    """Controller-driven finalisation keeps its existing behaviour."""
    (repo["wt"] / "README").write_text("changed\n")
    done = _finalize(repo)
    assert done["committed"] is True and "scope_violations" not in done
