"""Stage 6 completion-gate clauses (gpt-6-sol gate round 2 PARTIALS table),
control-plane side: each test names the §G clause it exercises verbatim."""
import json
import time

import pytest

from tests.test_estate_stage6_coverage import (  # noqa: F401  (fixtures + helpers)
    HEAD, HOME, LAB, _admitted, _dispatch, _lease, _lease_status, _observe, _row, _set, db, http, worker,
)
from core.database import EstateExecution, ParkLease, get_db_session, utcnow_naive
from src import estate_router, park_lease_ops
from src import estate_write_lane as lane


def test_gate_get_never_blocks_on_spool_release_after_fenced(db, worker, monkeypatch):
    """Gate round 2 finding 1: a GET that observes `fenced` resolves the row
    but defers the release acknowledgement to the sweep."""
    execution_id = _admitted(worker)
    worker.executions[execution_id] = {"claim": "fence"}
    _set(execution_id, last_observed_at=None)
    real = worker._spool_release
    monkeypatch.setattr(worker, "_spool_release", lambda payload: (time.sleep(10), real(payload))[1])
    began = time.monotonic()
    estate_router.get_estate_execution(execution_id, wait_s=18)
    assert time.monotonic() - began < 18.5
    row = _row(execution_id)
    assert row.worktree_resolution == "not_started" and row.spool_released_at is None
    assert "spool.release" not in worker.verbs()


def test_u20_status_returns_promptly_once_the_worker_is_reachable_again(db, worker):
    """U20: '`status` returns promptly once the worker is reachable again'."""
    execution_id = _admitted(worker)
    _observe(worker, execution_id, "running", quiescent=False)
    _set(execution_id, lifecycle_state="lost", last_observed_at=None)
    # lost is terminal for observation: a wait=0 GET answers at once...
    began = time.monotonic()
    assert estate_router.get_estate_execution(execution_id, wait_s=0)["lifecycle_state"] == "lost"
    assert time.monotonic() - began < 2
    # ...and once the worker is reachable again with an outcome, a budgeted
    # GET reconciles and returns promptly rather than waiting out its budget.
    worker.set_state(execution_id, "succeeded", result={"ok": True, "output": "x"})
    began = time.monotonic()
    view = estate_router.get_estate_execution(execution_id, wait_s=18)
    assert time.monotonic() - began < 3 and view["lifecycle_state"] == "succeeded"


@pytest.mark.parametrize("state", ["failed", "timed_out"])
@pytest.mark.parametrize("dirty", [False, True])
def test_u38_failed_and_timed_out_rows_block_clean_and_dirty(db, worker, state, dirty):
    """U38: 'failed and timed_out rows that actually started (unresolved),
    new dispatch, with the worktree both dirty and clean' -> refused
    lease_has_unresolved_worktree in both cases."""
    _lease()
    with get_db_session() as s:
        s.add(EstateExecution(id="E-old", objective="o", executor="codex-write", provider="codex",
                              host_id=HOME, repo_id="odysseus", lease_id="L1", lifecycle_state=state,
                              worker_handle_json=json.dumps({"pid": 1}), worktree_resolution="unresolved"))
    worker.clean = not dirty
    result = _dispatch()
    assert result["error_code"] == "lease_has_unresolved_worktree" and worker.calls == []


def _eligibility(monkeypatch):
    import src.estate_worker_client as client
    hosts = [{"id": LAB, "role": "lab", "identity_verified": True,
              "worker": {"enabled": True, "transport": "local", "qualified_executors": ["local"]}}]
    monkeypatch.setattr(estate_router, "_load_yaml", lambda name: {"hosts": hosts} if name == "estate" else {})
    monkeypatch.setattr(estate_router, "host_reachable", lambda host, live: (True, "this host"))
    monkeypatch.setattr(client, "worker_health", lambda host_id, **kw: {"ok": True})
    monkeypatch.setattr(client, "worker_repo_probe", lambda host_id, repo, **kw: {"resolved": True})
    return {e["host_id"]: e for e in estate_router.eligible_hosts(repo_id="odysseus")}


@pytest.mark.parametrize("answer", [{"state": "prepare_failed", "error": "x", "quiescent": True},
                                    {"state": "fenced", "quiescent": True},
                                    {"state": "prepared", "path": "/w", "branch": "feat/y", "head_sha": HEAD,
                                     "clean": False, "quiescent": True}])
def test_u51_after_each_known_failure_eligible_hosts_shows_no_conflict(db, worker, monkeypatch, answer):
    """U51: 'eligible_hosts shows no conflict.'"""
    worker.prepare_answer = answer
    with pytest.raises((park_lease_ops.WorktreeVerificationError, park_lease_ops.RepoNotClean)):
        park_lease_ops.park_with_worktree("odysseus", HOME, "feat/y")
    assert _eligibility(monkeypatch)[LAB]["eligible"] is True


def test_u62_failed_release_leaves_resolution_and_is_retried_but_never_for_legacy(db, worker):
    """U62: 'failure leaves resolution intact and spool_released_at null;
    reconcile retries it; never sent for legacy rows'."""
    _lease()
    worker.start_mode = "refuse"
    worker.fail["spool.release"] = ["worker_unreachable"]
    execution_id = _dispatch()["execution_id"]
    row = _row(execution_id)
    assert row.worktree_resolution == "not_started" and row.spool_released_at is None
    with get_db_session() as s:
        s.add(EstateExecution(id="legacy-r", objective="o", executor="codex-write", provider="codex",
                              host_id=HOME, repo_id="odysseus", lease_id=None, lifecycle_state="failed",
                              worker_handle_json=None, worktree_resolution="legacy_closed"))
    from tests.test_estate_stage6_control import _sweep
    _sweep()
    assert _row(execution_id).spool_released_at is not None
    released = [p["execution_id"] for _h, v, p in worker.calls if v == "spool.release"]
    assert "legacy-r" not in released and released.count(execution_id) == 2


def test_u25_full_telemetry_matrix_including_placement_mismatch(monkeypatch):
    """U25: 'RoutingDecision.host_id == route.host and executed_host_id ∈
    {route.host, null}; never another host except under placement_mismatch'."""
    import src.estate_worker_client as client
    for host in (LAB, HOME):
        for mode in ("ok", "execution_failed", "worker_unreachable", "worker_protocol_error",
                     "placement_mismatch"):
            recorded, decisions = {}, {}
            monkeypatch.setattr(estate_router, "_update_decision_outcome",
                                lambda decision_id, **kw: recorded.update(kw))
            monkeypatch.setattr(estate_router, "resolve_route", lambda task, host=host: (
                decisions.update(host_id=host) or {
                    "decision_id": "D", "route": {"host": host, "executor": "local", "concrete_model": "m",
                                                  "model_alias": "local-fast"},
                    "hosts_checked": [{"host_id": host, "qualified_executors": ["local"]}]}))

            def _call(host_id, verb, payload, *, deadline_s, mode=mode, host=host):
                assert host_id == host
                if mode == "ok":
                    return {"ok": True, "result": {"ok": True, "output": "hi"}, "attestation": {"host_id": host}}
                if mode == "placement_mismatch":
                    raise client.WorkerTransportError(mode, "x", observed_host_id="intruder")
                raise client.WorkerTransportError(mode, "x")
            monkeypatch.setattr(client, "call_worker", _call)
            result = estate_router.run_task({"objective": "hi", "requirements": {"capabilities": ["local-fast"]}})
            assert decisions["host_id"] == host == result["route"]["host"]
            if mode == "placement_mismatch":
                assert recorded.get("executed_host_id") is None
                assert recorded.get("actual_route") == "placement_mismatch:intruder"
            else:
                assert recorded.get("executed_host_id") in (host, None), (host, mode)


def test_u27_codex_readonly_sends_repo_id_to_home_never_a_lab_path(monkeypatch):
    """U27: 'codex-readonly on home fake gets repo_id and resolves cwd on
    home' -- the control plane sends only repo_id (never a path), so the cwd
    can only come from home's own resolve_repo_path (worker side:
    test_execute_codex_readonly_delegates_with_repo_cwd)."""
    import src.estate_worker_client as client
    sent = []
    monkeypatch.setattr(estate_router, "resolve_repo_path",
                        lambda repo_id: pytest.fail("control plane must not resolve the repo path"))

    def _call(host_id, verb, payload, *, deadline_s):
        sent.append((host_id, verb, payload))
        return {"ok": True, "result": {"ok": True, "output": "read"}, "attestation": {"host_id": host_id}}
    monkeypatch.setattr(client, "call_worker", _call)
    result = estate_router._dispatch_read_only(HOME, "codex", {"objective": "inspect", "repo": "obsidian-phd"},
                                               timeout=30)
    assert sent[0][0] == HOME and sent[0][2]["kind"] == "codex-readonly"
    assert sent[0][2]["repo_id"] == "obsidian-phd"
    assert not any(isinstance(v, str) and v.startswith("/") for v in sent[0][2].values())


def test_u71_second_finalize_adopts_through_the_real_commit_record_seam(db, worker):
    """U71: 'second finalize_execution (payload carries execution_id) ->
    worker adopts HEAD because commit.json matches it -> finalized with push
    recorded.' Control-plane half: the second call sends execution_id and
    records the worker's adopted outcome (worker half:
    test_u71_lost_response_retry_adopts_via_commit_record)."""
    execution_id = _admitted(worker)
    _observe(worker, execution_id, "succeeded", result={"ok": True, "output": "x"})
    worker.head = "b" * 40
    worker.fail["worktree.finalize"] = ["worker_unreachable"]
    worker.fail["status"] = [None]           # placeholder, replaced below
    worker.fail["status"] = []
    real_status = worker._status
    calls = {"n": 0}

    def _status_first_close_unreachable(payload):
        if payload.get("close") and calls["n"] == 0:
            calls["n"] += 1
            worker._raise("worker_unreachable")
        return real_status(payload)
    worker._status = _status_first_close_unreachable
    first = lane.finalize_execution(execution_id=execution_id, repo_id="odysseus", host_id=HOME, commit_message="x")
    assert first["finalized"] is False
    worker.finalize_outcome = {**worker.finalize_outcome, "adopted": True}
    second = lane.finalize_execution(execution_id=execution_id, repo_id="odysseus", host_id=HOME, commit_message="x")
    payloads = [p for _h, v, p in worker.calls if v == "worktree.finalize"]
    assert all(p["execution_id"] == execution_id for p in payloads) and len(payloads) == 2
    assert second["finalized"] is True and second["adopted"] is True and second["push"]["state"] == "pushed"


def test_u74_committed_record_missing_attempt_blocks_recovery_until_empty(db, worker):
    """U74: 'a finalize attempt has committed (tree clean) but is still
    populated without commit.json -> recover_execution_lease refused
    writer_quiescence_unproven (aggregate false) and the lease stays
    active; after the attempt unit empties -> recovery allowed'."""
    execution_id = _admitted(worker)
    _observe(worker, execution_id, "running", quiescent=False)
    _observe(worker, execution_id, "interrupted", quiescent=True)
    worker.head = "b" * 40                          # committed, tree clean
    worker.executions[execution_id]["quiescent"] = False          # attempt unit populated
    worker.executions[execution_id]["finalize_commit"] = None     # no commit.json yet
    ids = dict(lease_id="L1", host_id=HOME, repo_id="odysseus", branch="feat/x", worktree_path="/w/feat")
    assert lane.recover_execution_lease(execution_id, **ids)["code"] == "writer_quiescence_unproven"
    assert _lease_status() == "active"
    worker.executions[execution_id]["quiescent"] = True
    result = lane.recover_execution_lease(execution_id, **ids)
    assert result["recovered"] is True and result["recovery"]["head_sha"] == "b" * 40
    assert result["recovery"]["finalize_ambiguous"] is True       # commit without proof -> pushable, flagged


def test_u75_commit_during_closure_is_recorded_as_the_post_commit_head(db, worker):
    """U75: 'a finalize attempt committing while closure waits leads recovery
    to record the post-commit HEAD (with finalize_commit: true once
    commit.json exists), never the pre-commit HEAD'."""
    execution_id = _admitted(worker)
    _observe(worker, execution_id, "running", quiescent=False)
    _observe(worker, execution_id, "interrupted", quiescent=True)

    def _commit_lands_during_close(host, verb, payload):
        if verb == "status" and payload.get("close"):
            worker.head = "c" * 40
            worker.executions[execution_id]["finalize_commit"] = {"commit_sha": "c" * 40}
    worker.on_call = _commit_lands_during_close
    result = lane.recover_execution_lease(execution_id, lease_id="L1", host_id=HOME, repo_id="odysseus",
                                          branch="feat/x", worktree_path="/w/feat")
    assert result["recovery"]["head_sha"] == "c" * 40 and result["recovery"]["finalize_commit"] is True
