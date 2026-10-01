"""An in-process stand-in for the worker's `worktree.prepare` (Stage 6,
S6.7/S6.9) for tests that exercise real git worktree creation through the
control-plane park path. It performs the same worktree_ops calls the
worker's prepare runner does, and asserts the S6.7 ordering invariant: a
committed `preparing` reservation for the payload's lease_id exists at the
moment of the call (U50/U59)."""
from __future__ import annotations


def install_inline_prepare_worker(monkeypatch, calls=None):
    from src import estate_worker_client as client
    from src import worktree_ops
    from src.park_lease_ops import git_is_clean

    calls = calls if calls is not None else []

    def _fake_call_worker(host_id, verb, payload, *, deadline_s):
        from core.database import ParkLease, get_db_session
        calls.append((host_id, verb, payload))
        if verb != "worktree.prepare":
            raise AssertionError(f"unexpected worker verb {verb!r} in a park test")
        lease_id = payload["lease"]["lease_id"]
        with get_db_session() as db:
            row = db.query(ParkLease).filter(ParkLease.id == lease_id).one_or_none()
            assert row is not None and row.status == "preparing", "prepare before a committed reservation"
        created = worktree_ops.create_or_reuse_worktree(payload["repo_id"], payload["branch"],
                                                        base_ref=payload["base_ref"])
        verified = worktree_ops.verify_worktree(payload["repo_id"], created["path"], payload["branch"])
        clean, _reason = git_is_clean(verified["path"])
        return {"ok": True, "result": {"state": "prepared", "path": verified["path"],
                                       "branch": verified["branch"], "head_sha": verified["head"],
                                       "clean": clean, "reused": False, "quiescent": True}}

    monkeypatch.setattr(client, "call_worker", _fake_call_worker)
    return calls
