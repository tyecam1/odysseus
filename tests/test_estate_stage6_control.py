"""Stage 6 control plane (plan §6.0 + Stage 6 "Files"): admission/dispatch
(U13-U17, U21, U24, U29a/b, U34, U37-U40, U63), observation (U18-U20,
U22, U23, U33 path, U73), finalize (U35, U36, U39, U71 control side, U74
recovery variant, 6c finding 1), recovery (U41, U42), push (U65, U66),
and ParkLease preparation (U49, U51, U52, U55, U56, U59)."""
import json
import os
import threading
from datetime import timedelta

import pytest

from tests.helpers.import_state import clear_fake_database_modules
from tests.helpers.sqlite_db import make_temp_sqlite

clear_fake_database_modules()

import core.database as cdb
from core.database import EstateExecution, ParkLease, get_db_session, utcnow_naive
from src import estate_router, park_lease_ops
from src import estate_write_lane as lane
from tests.helpers.fake_worker import FakeWorker

LAB, HOME = "hz2-workstation", "desktop-in7o23d"
_REAL_OBSERVE = lane._observe_worker_execution   # captured before the fixture no-ops it
HEAD = "a" * 40


@pytest.fixture
def db(monkeypatch):
    session_local, engine, tmpfile = make_temp_sqlite(cdb.Base.metadata)
    monkeypatch.setattr(cdb, "SessionLocal", session_local)
    monkeypatch.setattr(estate_router, "current_host_id", lambda: LAB)
    monkeypatch.setattr(lane, "MONITOR_INTERVAL_SECONDS", 0.01)
    observed = []
    monkeypatch.setattr(lane, "_observe_worker_execution", lambda execution_id: observed.append(execution_id))
    yield observed
    engine.dispose()
    os.unlink(tmpfile.name)


@pytest.fixture
def worker(monkeypatch):
    return FakeWorker(monkeypatch, head=HEAD)


def _lease(lease_id="L1", host=HOME, status="active", worktree="/w/feat", branch="feat/x", stale=False):
    heartbeat = utcnow_naive() - timedelta(seconds=(cdb.PARK_LEASE_STALE_SECONDS + 60) if stale else 0)
    with get_db_session() as s:
        s.add(ParkLease(id=lease_id, repo_id="odysseus", host_id=host, worktree_path=worktree,
                        branch=branch, status=status, heartbeat_at=heartbeat))


def _sweep():
    """The estate-wide reconciliation a restarted control plane runs (the
    background sweep); GET itself observes only its own row within budget."""
    from core.database import SessionLocal
    db = cdb.SessionLocal()
    try:
        lane.reconcile_stale_estate_executions(db, EstateExecution)
    finally:
        db.close()


def _row(execution_id):
    with get_db_session() as s:
        row = s.query(EstateExecution).filter(EstateExecution.id == execution_id).one()
        s.expunge(row)
        return row


def _dispatch(host=HOME, **kwargs):
    return lane.execute_write_via_worker("change it", repo_id="odysseus", host_id=host, wait_timeout=0, **kwargs)


def _lease_status(lease_id="L1"):
    with get_db_session() as s:
        return s.query(ParkLease).filter(ParkLease.id == lease_id).one().status


# ---------------------------------------------------------------------
# Admission and dispatch
# ---------------------------------------------------------------------

def test_u13_write_under_home_lease_runs_verify_then_start_on_home(db, worker):
    _lease()
    result = _dispatch()
    assert result["ok"] is True and result["dispatch"] == "new"
    assert worker.verbs() == ["worktree.verify", "start"]
    assert {host for host, _v, _p in worker.calls} == {HOME}
    row = _row(result["execution_id"])
    assert row.host_id == HOME and row.admission_head_sha == HEAD
    placeholder = json.loads(row.worker_handle_json)                     # starting: not yet confirmed
    assert placeholder["dispatch_state"] == "pending_start" and placeholder["start_attempts"] == 1
    start = worker.calls[1][2]
    assert start["lease"] == {"lease_id": "L1", "worktree_path": "/w/feat", "branch": "feat/x",
                              "expected_head_sha": HEAD}
    assert result["next_action"]["cli"] == f"aoteru execution {result['execution_id']} --wait 60"
    assert db == [result["execution_id"]]


def test_u14_lease_held_by_another_host_refuses_without_a_row(db, worker):
    _lease(host=LAB)
    result = _dispatch(host=HOME)
    assert result["ok"] is False and result["error_code"] == "write_lease_missing"
    assert worker.calls == []
    with get_db_session() as s:
        assert s.query(EstateExecution).count() == 0


def test_u15_no_lease_refuses_without_row_or_start(db, worker):
    result = _dispatch()
    assert result["ok"] is False and worker.calls == []


def test_dirty_worktree_refuses_admission(db, worker):
    _lease()
    worker.clean = False
    result = _dispatch()
    assert result["error_code"] == "worktree_not_clean"
    assert worker.verbs() == ["worktree.verify"]


def test_u16_duplicate_dispatch_reuses_in_flight_execution(db, worker):
    _lease()
    first = _dispatch()
    second = _dispatch()
    assert second["dispatch"] == "reused_in_flight" and second["execution_id"] == first["execution_id"]
    assert worker.verbs().count("start") == 1


def test_u17_lost_start_response_retried_with_same_id_one_spawn(db, worker):
    _lease()
    worker.start_mode = "lost_after_spawn"
    result = _dispatch()
    row = _row(result["execution_id"])
    assert row.lifecycle_state in ("accepted", "running")      # never failed on a lost response
    assert [v for v in worker.verbs() if v == "start"] == ["start", "start"]
    assert worker.executions[result["execution_id"]]["spawns"] == 1
    starts = [p for _h, v, p in worker.calls if v == "start"]
    assert starts[0]["execution_id"] == starts[1]["execution_id"]


def test_u40_first_start_deterministic_refusal_is_not_started_and_reopens(db, worker):
    _lease()
    worker.start_mode = "refuse"
    first = _dispatch()
    row = _row(first["execution_id"])
    assert row.lifecycle_state == "failed" and row.worktree_resolution == "not_started"
    worker.start_mode = "normal"
    second = _dispatch()
    assert second["dispatch"] == "new" and second["execution_id"] != first["execution_id"]


def test_u69_refusal_after_ambiguity_is_resolved_only_through_fence(db, worker):
    _lease()
    worker.fail["start"] = ["worker_unreachable", "authority_denied"]
    result = _dispatch()
    fences = [p for _h, v, p in worker.calls if v == "status" and p.get("fence")]
    assert fences, "an ambiguous start must be resolved through status {fence: true}"
    row = _row(result["execution_id"])
    assert row.worktree_resolution == "not_started"            # fence won: positively never ran


@pytest.mark.parametrize("state,code", [
    ("lost", "lease_has_unresolved_lost_execution"),
    ("succeeded", "lease_has_unfinalized_execution"),
    ("failed", "lease_has_unresolved_worktree"),
    ("timed_out", "lease_has_unresolved_worktree"),
    ("interrupted", "lease_has_unresolved_worktree"),
])
def test_u21_u34_u37_u38_unresolved_rows_refuse_new_dispatch(db, worker, state, code):
    _lease()
    with get_db_session() as s:
        s.add(EstateExecution(id="E-old", objective="o", executor="codex-write", provider="codex",
                              host_id=HOME, repo_id="odysseus", lease_id="L1", lifecycle_state=state,
                              worker_handle_json=json.dumps({"pid": 1}), worktree_resolution="unresolved"))
    result = _dispatch()
    assert result["ok"] is False and result["error_code"] == code
    assert result["execution_id"] == "E-old" and result["next_action"]
    assert "start" not in worker.verbs()


def test_u29a_lease_released_between_early_check_and_admission(db, worker):
    _lease()
    worker.on_call = lambda host, verb, payload: verb == "worktree.verify" and _release_directly("L1")
    result = _dispatch()
    assert result["ok"] is False and result["error_code"] == "write_lease_missing"
    assert "start" not in worker.verbs()
    with get_db_session() as s:
        assert s.query(EstateExecution).count() == 0


def _release_directly(lease_id):
    with get_db_session() as s:
        s.query(ParkLease).filter(ParkLease.id == lease_id).update({"status": "released"})


def test_u29_release_blocks_on_admission_then_is_refused(db, worker, monkeypatch):
    _lease()
    inside, proceed = threading.Event(), threading.Event()

    def _hook():
        inside.set()
        proceed.wait(5)
    monkeypatch.setattr(lane, "_ADMISSION_TEST_HOOK", _hook)
    outcome = {}
    admission = threading.Thread(target=lambda: outcome.update(admit=_dispatch()))
    admission.start()
    assert inside.wait(5)
    release = threading.Thread(target=lambda: outcome.update(release=_try_release()))
    release.start()
    release.join(0.5)
    assert release.is_alive(), "release must wait for the admission's write lock"
    proceed.set()
    admission.join(10)
    release.join(15)
    assert outcome["admit"]["ok"] is True
    assert isinstance(outcome["release"], park_lease_ops.LeaseHasUnresolvedExecution)
    assert _lease_status() == "active"


def test_u29b_release_first_then_admission_refuses(db, worker):
    _lease()
    with get_db_session() as s:
        s.query(ParkLease).update({"status": "released"})
    assert _dispatch()["ok"] is False and "start" not in worker.verbs()


def _try_release():
    try:
        return park_lease_ops.release_repo("odysseus", host_id=HOME)
    except park_lease_ops.LeaseHasUnresolvedExecution as exc:
        return exc


# ---------------------------------------------------------------------
# Observation
# ---------------------------------------------------------------------

def _admitted(worker):
    _lease()
    return _dispatch()["execution_id"]


def test_u18_status_observation_without_redispatch(db, worker):
    execution_id = _admitted(worker)
    worker.set_state(execution_id, "running", quiescent=False)
    lane._apply_view(execution_id, worker._view(execution_id))
    assert _row(execution_id).lifecycle_state == "running"
    worker.set_state(execution_id, "succeeded", result={"ok": True, "output": "done"})
    starts = worker.verbs().count("start")
    view = estate_router.get_estate_execution(execution_id, wait_s=0)
    lane._apply_view(execution_id, worker._view(execution_id))
    view = estate_router.get_estate_execution(execution_id, wait_s=0)
    assert view["lifecycle_state"] == "succeeded" and view["worktree_resolution"] == "unresolved"
    assert worker.verbs().count("start") == starts


def test_u19_reachable_quiescent_runner_without_terminal_is_interrupted(db, worker):
    execution_id = _admitted(worker)
    worker.set_state(execution_id, "running", quiescent=False)
    lane._apply_view(execution_id, worker._view(execution_id))
    worker.set_state(execution_id, "interrupted", quiescent=True)
    lane._apply_view(execution_id, worker._view(execution_id))
    row = _row(execution_id)
    assert row.lifecycle_state == "interrupted" and row.worktree_resolution == "unresolved"


def test_u73_terminal_pending_keeps_row_running(db, worker):
    execution_id = _admitted(worker)
    worker.set_state(execution_id, "running", quiescent=False)
    lane._apply_view(execution_id, {**worker._view(execution_id), "terminal_pending": True})
    assert _row(execution_id).lifecycle_state == "running"


def test_u20_unobserved_past_persisted_deadline_is_lost(db, worker):
    execution_id = _admitted(worker)
    with get_db_session() as s:
        s.query(EstateExecution).filter(EstateExecution.id == execution_id).update({
            "execution_deadline_at": utcnow_naive() - timedelta(seconds=lane.LOST_GRACE_SECONDS + 5),
            "lifecycle_state": "running",
            # last successful observation was before deadline + grace
            "last_observed_at": utcnow_naive() - timedelta(seconds=lane.LOST_GRACE_SECONDS + 10)})
    worker.fail["status"] = ["worker_unreachable"]
    _REAL_OBSERVE(execution_id)                       # one failed poll past the bound -> lost, then stop
    assert _row(execution_id).lifecycle_state == "lost"
    # A recent successful observation past the bound is NOT lost.
    with get_db_session() as s:
        s.query(EstateExecution).filter(EstateExecution.id == execution_id).update({
            "lifecycle_state": "running", "last_observed_at": utcnow_naive()})
    assert lane._mark_lost_if_due(execution_id) is False


def test_u22_lost_row_reconciles_to_truthful_state_without_redispatch(db, worker):
    execution_id = _admitted(worker)
    with get_db_session() as s:
        s.query(EstateExecution).filter(EstateExecution.id == execution_id).update({"lifecycle_state": "lost"})
    worker.set_state(execution_id, "succeeded", result={"ok": True, "output": "x"})
    starts = worker.verbs().count("start")
    _sweep()
    row = _row(execution_id)
    assert row.lifecycle_state == "succeeded" and row.worktree_resolution == "unresolved"
    assert worker.verbs().count("start") == starts


def test_u23_legacy_row_on_non_local_host_is_lost_not_interrupted(db, worker, monkeypatch):
    with get_db_session() as s:
        s.add(EstateExecution(id="legacy-1", objective="o", executor="codex-write", provider="codex",
                              host_id=HOME, repo_id="odysseus", lease_id=None, lifecycle_state="running",
                              worker_pid=999999))
    killed = []
    monkeypatch.setattr(os, "kill", lambda pid, sig: killed.append(pid))
    estate_router.get_estate_execution("legacy-1")
    assert _row("legacy-1").lifecycle_state == "lost" and killed == []


def test_u24_placeholder_row_resolves_by_same_id_start_not_as_legacy(db, worker):
    execution_id = _admitted(worker)
    worker.executions.pop(execution_id)                  # start never reached the worker
    with get_db_session() as s:
        s.query(EstateExecution).filter(EstateExecution.id == execution_id).update({"last_observed_at": None})
    _sweep()
    starts = [p for _h, v, p in worker.calls if v == "start"]
    assert len(starts) == 2 and starts[1]["execution_id"] == execution_id
    assert _row(execution_id).lifecycle_state in ("accepted", "running")


def test_u63_placeholder_past_deadline_is_fenced_not_restarted(db, worker):
    execution_id = _admitted(worker)
    worker.executions.pop(execution_id)
    with get_db_session() as s:
        s.query(EstateExecution).filter(EstateExecution.id == execution_id).update({
            "execution_deadline_at": utcnow_naive() - timedelta(seconds=1), "last_observed_at": None})
    starts = worker.verbs().count("start")
    _sweep()
    assert worker.verbs().count("start") == starts
    row = _row(execution_id)
    assert row.lifecycle_state == "failed" and row.worktree_resolution == "not_started"


def test_u33_confirmed_running_observation_renews_the_exact_lease(db, worker):
    execution_id = _admitted(worker)
    with get_db_session() as s:
        s.query(ParkLease).update({"heartbeat_at": utcnow_naive() - timedelta(seconds=600)})
    worker.set_state(execution_id, "running", quiescent=False)
    lane._apply_view(execution_id, worker._view(execution_id))
    with get_db_session() as s:
        heartbeat = s.query(ParkLease).one().heartbeat_at
    assert (utcnow_naive() - heartbeat).total_seconds() < 5


def test_monitor_thread_stops_at_terminal(db, worker, monkeypatch):
    execution_id = _admitted(worker)
    worker.set_state(execution_id, "succeeded", result={"ok": True, "output": "x"})
    _REAL_OBSERVE(execution_id)
    assert _row(execution_id).lifecycle_state == "succeeded"
    assert worker.verbs().count("start") == 1         # observation never redispatches


# ---------------------------------------------------------------------
# Finalize
# ---------------------------------------------------------------------

def _succeeded(worker):
    execution_id = _admitted(worker)
    worker.set_state(execution_id, "succeeded", result={"ok": True, "output": "x"})
    lane._apply_view(execution_id, worker._view(execution_id))
    assert _row(execution_id).lifecycle_state == "succeeded"
    return execution_id


def test_u39_finalize_closes_first_then_records_finalized_and_reopens(db, worker):
    execution_id = _succeeded(worker)
    worker.head = "b" * 40
    result = lane.finalize_execution(execution_id=execution_id, repo_id="odysseus", host_id=HOME,
                                     commit_message="done")
    assert result["finalized"] is True and result["commit_sha"] == "b" * 40
    verbs = worker.verbs()
    assert verbs.index("worktree.finalize") < next(i for i, (_h, v, p) in enumerate(worker.calls)
                                                   if v == "status" and p.get("close"))
    assert _row(execution_id).worktree_resolution == "finalized"
    assert "spool.release" in verbs
    again = _dispatch()
    assert again["dispatch"] == "new"


def test_6c_f1_lost_finalize_response_is_resolved_from_the_closure_view(db, worker):
    execution_id = _succeeded(worker)
    worker.head = "b" * 40
    worker.executions[execution_id]["finalize_result"] = dict(worker.finalize_outcome)
    worker.fail["worktree.finalize"] = ["worker_unreachable"]
    result = lane.finalize_execution(execution_id=execution_id, repo_id="odysseus", host_id=HOME,
                                     commit_message="done")
    assert result["finalized"] is True
    assert _row(execution_id).worktree_resolution == "finalized"


def test_finalize_refused_while_aggregate_not_quiescent(db, worker):
    execution_id = _succeeded(worker)
    worker.executions[execution_id]["quiescent"] = False
    result = lane.finalize_execution(execution_id=execution_id, repo_id="odysseus", host_id=HOME,
                                     commit_message="done")
    assert result["finalized"] is False and result["reason"] == "writer_quiescence_unproven"
    assert "worktree.finalize" not in worker.verbs()


@pytest.mark.parametrize("state", ["interrupted", "lost"])
def test_u35_finalize_refused_for_non_succeeded(db, worker, state):
    execution_id = _admitted(worker)
    with get_db_session() as s:
        s.query(EstateExecution).filter(EstateExecution.id == execution_id).update({"lifecycle_state": state})
    calls = len(worker.calls)
    result = lane.finalize_execution(execution_id=execution_id, repo_id="odysseus", host_id=HOME,
                                     commit_message="x")
    assert result["finalized"] is False and len(worker.calls) == calls


def test_u36_finalize_refused_after_lease_released_or_reassigned(db, worker):
    execution_id = _succeeded(worker)
    _release_directly("L1")
    calls = len(worker.calls)
    result = lane.finalize_execution(execution_id=execution_id, repo_id="odysseus", host_id=HOME,
                                     commit_message="x")
    assert result["finalized"] is False and len(worker.calls) == calls


def test_finalize_ambiguous_is_not_finalized_and_points_to_recovery(db, worker):
    execution_id = _succeeded(worker)
    worker.finalize_outcome = {"outcome": "finalize_ambiguous", "head": "c" * 40}
    result = lane.finalize_execution(execution_id=execution_id, repo_id="odysseus", host_id=HOME,
                                     commit_message="x")
    assert result["finalized"] is False and result["next_action"] == "recover"
    assert _row(execution_id).worktree_resolution == "unresolved"


# ---------------------------------------------------------------------
# Recovery (S6.2)
# ---------------------------------------------------------------------

def _interrupted(worker):
    execution_id = _admitted(worker)
    worker.set_state(execution_id, "running", quiescent=False)
    lane._apply_view(execution_id, worker._view(execution_id))
    worker.set_state(execution_id, "interrupted", quiescent=True)
    lane._apply_view(execution_id, worker._view(execution_id))
    return execution_id


def _recover(execution_id, **overrides):
    ids = {"lease_id": "L1", "host_id": HOME, "repo_id": "odysseus", "branch": "feat/x",
           "worktree_path": "/w/feat", **overrides}
    return lane.recover_execution_lease(execution_id, **ids)


def test_u41_recovery_releases_and_requires_a_fresh_park(db, worker):
    execution_id = _interrupted(worker)
    result = _recover(execution_id)
    assert result["recovered"] is True
    assert _row(execution_id).worktree_resolution == "recovered" and _lease_status() == "released"
    close_calls = [p for _h, v, p in worker.calls if v == "status" and p.get("close")]
    assert close_calls, "recovery must close the execution (S6.12)"
    order = [v if not (v == "status" and p.get("close")) else "close" for _h, v, p in worker.calls]
    assert order.index("close") < len(order) - 1 - order[::-1].index("worktree.verify")
    assert park_lease_ops.renew_lease_for_execution(execution_id) is False


@pytest.mark.parametrize("override", [{"lease_id": "L9"}, {"host_id": LAB}, {"repo_id": "x"},
                                      {"branch": "other"}, {"worktree_path": "/elsewhere"}])
def test_u42a_any_identifier_mismatch_refuses(db, worker, override):
    execution_id = _interrupted(worker)
    assert _recover(execution_id, **override)["recovered"] is False
    assert _lease_status() == "active" and _row(execution_id).worktree_resolution == "unresolved"


def test_u42b_unsettled_rows_refuse(db, worker):
    execution_id = _admitted(worker)
    assert _recover(execution_id)["code"] == "execution_not_settled"


def test_u42c_unreachable_and_e_dirty_and_quiescence_refuse(db, worker):
    execution_id = _interrupted(worker)
    worker.fail["status"] = ["worker_unreachable"]
    assert _recover(execution_id)["code"] == "worker_unreachable"
    worker.clean = False
    assert _recover(execution_id)["code"] == "worktree_not_clean"
    worker.clean = True
    worker.executions[execution_id]["quiescent"] = None
    assert _recover(execution_id)["code"] == "writer_quiescence_unproven"
    assert _lease_status() == "active"


def test_u42d_handle_mismatch_refuses(db, worker, monkeypatch):
    execution_id = _interrupted(worker)
    monkeypatch.setattr(worker, "handle", lambda eid: {"pid": 1, "create_time": 9, "cgroup": "/x", "unit": "u"})
    assert _recover(execution_id)["code"] == "handle_mismatch"


def test_u74_recovery_waits_for_an_in_flight_finalize_attempt(db, worker):
    execution_id = _interrupted(worker)
    worker.executions[execution_id]["quiescent"] = False          # a finalize attempt still populated
    assert _recover(execution_id)["code"] == "writer_quiescence_unproven"
    worker.executions[execution_id]["quiescent"] = True
    assert _recover(execution_id)["recovered"] is True


def test_u71_recovery_records_a_proven_finalize_commit_and_push_applies(db, worker):
    execution_id = _interrupted(worker)
    worker.head = "b" * 40
    worker.executions[execution_id]["finalize_commit"] = {"commit_sha": "b" * 40}
    result = _recover(execution_id)
    assert result["recovered"] is True and result["recovery"]["finalize_commit"] is True
    assert result["next_action"]["cli"] == f"aoteru push {execution_id}"
    pushed = lane.push_finalized_execution(execution_id)
    assert pushed["pushed"] is True
    assert worker.calls[-1][0] == HOME and worker.calls[-1][2]["commit_sha"] == "b" * 40
    assert json.loads(_row(execution_id).finalization_json)["push"]["state"] == "pushed"


# ---------------------------------------------------------------------
# Push (S6.10)
# ---------------------------------------------------------------------

def test_u65_failed_push_is_retried_on_the_rows_host_only(db, worker):
    execution_id = _succeeded(worker)
    worker.head = "b" * 40
    worker.finalize_outcome = {**worker.finalize_outcome, "push": {"state": "failed", "commit_sha": "b" * 40}}
    result = lane.finalize_execution(execution_id=execution_id, repo_id="odysseus", host_id=HOME,
                                     commit_message="done")
    assert result["finalized"] is True and result["next_action"]["cli"] == f"aoteru push {execution_id}"
    released = park_lease_ops.release_repo("odysseus", host_id=HOME)
    assert released["unpushed_executions"] == [{"execution_id": execution_id, "commit_sha": "b" * 40}]
    pushed = lane.push_finalized_execution(execution_id)
    assert pushed["pushed"] is True
    assert [h for h, v, _p in worker.calls if v == "worktree.push"] == [HOME]


def test_u66_push_preconditions(db, worker):
    execution_id = _succeeded(worker)
    calls = len(worker.calls)
    assert lane.push_finalized_execution(execution_id)["code"] == "not_eligible"
    assert len(worker.calls) == calls


# ---------------------------------------------------------------------
# Park with worktree (S6.7 / S6.9)
# ---------------------------------------------------------------------

def test_u52_u59_successful_prepare_binds_active_lease(db, worker):
    result = park_lease_ops.park_with_worktree("odysseus", LAB, "feat/y")
    assert result["status"] == "active" and result["worktree_path"] == worker.path
    prepare = [(h, p) for h, v, p in worker.calls if v == "worktree.prepare"]
    assert prepare == [(LAB, {"repo_id": "odysseus", "branch": "feat/y", "base_ref": "HEAD",
                              "lease": {"lease_id": result["lease_id"], "host_id": LAB}})]
    assert _lease_status(result["lease_id"]) == "active"


@pytest.mark.parametrize("answer,error", [
    ({"state": "prepare_failed", "error": "boom", "quiescent": True}, park_lease_ops.WorktreeVerificationError),
    ({"state": "fenced", "quiescent": True}, park_lease_ops.WorktreeVerificationError),
    ({"state": "prepared", "path": "/w", "branch": "feat/y", "head_sha": HEAD, "clean": False, "quiescent": True},
     park_lease_ops.RepoNotClean),
    ({"state": "prepared", "path": "/w", "branch": "other", "head_sha": HEAD, "clean": True, "quiescent": True},
     park_lease_ops.WorktreeVerificationError),
])
def test_u51_positively_known_failures_release_the_reservation(db, worker, answer, error):
    worker.prepare_answer = answer
    with pytest.raises(error):
        park_lease_ops.park_with_worktree("odysseus", LAB, "feat/y")
    with get_db_session() as s:
        assert s.query(ParkLease).filter(ParkLease.status.in_(("active", "preparing"))).count() == 0


@pytest.mark.parametrize("code", ["worker_unreachable", "worker_protocol_error", "placement_mismatch"])
def test_u55_ambiguous_prepare_keeps_the_reservation(db, worker, code):
    worker.fail["worktree.prepare"] = [code]
    with pytest.raises(park_lease_ops.PrepareOutcomeUnresolved) as info:
        park_lease_ops.park_with_worktree("odysseus", HOME, "feat/y")
    assert _lease_status(info.value.lease_id) == "preparing"
    calls = len(worker.calls)
    with pytest.raises(park_lease_ops.ParkConflict):
        park_lease_ops.park_with_worktree("odysseus", LAB, "feat/z")
    assert len(worker.calls) == calls                           # the loser never reached a worker


def test_u55_still_preparing_is_ambiguous(db, worker):
    worker.prepare_answer = {"state": "preparing", "quiescent": None}
    with pytest.raises(park_lease_ops.PrepareOutcomeUnresolved):
        park_lease_ops.park_with_worktree("odysseus", HOME, "feat/y")


def test_u56_stale_reservation_resolved_only_by_worker_proof(db, worker):
    worker.fail["worktree.prepare"] = ["worker_unreachable"]
    with pytest.raises(park_lease_ops.PrepareOutcomeUnresolved) as info:
        park_lease_ops.park_with_worktree("odysseus", HOME, "feat/y")
    lease_id = info.value.lease_id
    worker.prepare_status_answer = {"state": "preparing", "quiescent": False}
    assert park_lease_ops.resolve_preparing_reservation(lease_id)["reason"] == "prepare_still_running"
    assert _lease_status(lease_id) == "preparing"
    worker.prepare_status_answer = {"state": "fenced", "quiescent": True}
    assert park_lease_ops.resolve_preparing_reservation(lease_id)["released"] is True
    fenced = [p for _h, v, p in worker.calls if v == "worktree.prepare_status"]
    assert all(p == {"lease_id": lease_id, "fence": True} for p in fenced)


def test_u56_competing_park_probes_a_stale_reservation_then_succeeds(db, worker):
    _lease("P-old", host=HOME, status="preparing", worktree="", stale=True)
    worker.prepare_status_answer = {"state": "prepare_interrupted", "quiescent": True}
    result = park_lease_ops.park_with_worktree("odysseus", LAB, "feat/y")
    assert result["status"] == "active" and _lease_status("P-old") == "released"


def test_u49_concurrent_parks_one_reservation_one_prepare(db, worker):
    barrier = threading.Barrier(2)
    outcomes = []

    def _park(branch):
        barrier.wait()
        try:
            outcomes.append(park_lease_ops.park_with_worktree("odysseus", LAB, branch))
        except park_lease_ops.ParkConflict as exc:
            outcomes.append(exc)

    threads = [threading.Thread(target=_park, args=(b,)) for b in ("feat/a", "feat/b")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(20)
    assert sum(isinstance(o, dict) for o in outcomes) == 1
    assert sum(isinstance(o, park_lease_ops.ParkConflict) for o in outcomes) == 1
    assert worker.verbs().count("worktree.prepare") == 1



# ---------------------------------------------------------------------
# 6d adjudication regressions
# ---------------------------------------------------------------------

@pytest.mark.parametrize("answer", [{"state": "unknown", "quiescent": True},
                                    {"state": "prepared", "path": "/w", "branch": "feat/y", "head_sha": HEAD,
                                     "clean": True},             # no quiescence proof
                                    {"state": "prepare_failed", "quiescent": None}])
def test_6d_f6_unrecognised_or_unproven_prepare_answers_keep_the_reservation(db, worker, answer):
    worker.prepare_answer = answer
    with pytest.raises(park_lease_ops.PrepareOutcomeUnresolved) as info:
        park_lease_ops.park_with_worktree("odysseus", HOME, "feat/y")
    assert _lease_status(info.value.lease_id) == "preparing"


def test_6d_f2_persisted_start_ambiguity_survives_a_later_dispatch_attempt(db, worker):
    """Ambiguous start + unreachable fence, then a LATER reconcile's start
    is refused pre-claim: the refusal must not resolve not_started."""
    _lease()
    worker.fail["start"] = ["worker_unreachable", "worker_unreachable"]
    worker.fail["status"] = ["worker_unreachable"]
    execution_id = _dispatch()["execution_id"]
    assert json.loads(_row(execution_id).worker_handle_json).get("start_ambiguous") is True
    worker.fail["start"] = ["authority_denied"]
    worker.fail["status"] = ["worker_unreachable"]
    lane._dispatch_start(execution_id)
    row = _row(execution_id)
    assert row.worktree_resolution == "unresolved" and row.lifecycle_state == "accepted"
    worker.fail.clear()
    lane._dispatch_start(execution_id)          # before the deadline: same-id start re-issued, now claims
    row = _row(execution_id)
    assert row.worktree_resolution == "unresolved" and worker.executions[execution_id]["spawns"] == 1


def test_6d_f5_no_start_is_sent_once_the_persisted_deadline_passed(db, worker):
    _lease()
    worker.fail["start"] = ["worker_unreachable"]
    execution_id = _dispatch()["execution_id"]
    with get_db_session() as s:
        s.query(EstateExecution).filter(EstateExecution.id == execution_id).update(
            {"execution_deadline_at": utcnow_naive() - timedelta(seconds=1)})
    starts = worker.verbs().count("start")
    worker.executions.pop(execution_id, None)
    lane._dispatch_start(execution_id)
    assert worker.verbs().count("start") == starts
    assert _row(execution_id).worktree_resolution == "not_started"


def test_6d_f3_racing_push_retries_never_regress_pushed(db, worker):
    execution_id = _succeeded(worker)
    worker.head = "b" * 40
    worker.finalize_outcome = {**worker.finalize_outcome, "push": {"state": "failed", "commit_sha": "b" * 40}}
    lane.finalize_execution(execution_id=execution_id, repo_id="odysseus", host_id=HOME, commit_message="x")
    worker.push_answer = {"pushed": True, "push": {"state": "pushed"}}
    assert lane.push_finalized_execution(execution_id)["pushed"] is True
    # a stale concurrent retry that read `failed` earlier and now reports failure
    with get_db_session() as s:
        row = s.query(EstateExecution).filter(EstateExecution.id == execution_id).one()
        stale = json.loads(row.finalization_json)
    stale["push"]["state"] = "failed"
    worker.push_answer = {"pushed": False, "push": {"state": "failed", "error": "late"}}
    import unittest.mock as mock
    with mock.patch.object(lane, "_load_row", wraps=lane._load_row) as loader:
        original = lane._load_row(execution_id)
        original.finalization_json = json.dumps(stale)
        loader.return_value = original
        loader.side_effect = None
        lane.push_finalized_execution(execution_id)
    push = json.loads(_row(execution_id).finalization_json)["push"]
    assert push["state"] == "pushed" and push["attempts"] >= 3


def test_6d_f4_get_only_observes_its_own_row(db, worker, monkeypatch):
    other = _admitted(worker)
    monkeypatch.setattr(lane, "_trigger_background_reconcile", lambda: None)
    with get_db_session() as s:
        s.add(EstateExecution(id="mine", objective="o", executor="codex-write", provider="codex",
                              host_id=HOME, repo_id="other-repo", lease_id="LX", lifecycle_state="running",
                              worker_handle_json=json.dumps({"pid": 1}), worktree_resolution="unresolved"))
        s.query(EstateExecution).update({"last_observed_at": None})
    calls = len(worker.calls)
    worker.executions["mine"] = {"claim": "start", "state": "failed", "quiescent": True}
    estate_router.get_estate_execution("mine", wait_s=30)
    statuses = [p["execution_id"] for _h, v, p in worker.calls[calls:] if v == "status"]
    assert statuses and set(statuses) == {"mine"} and other not in statuses


def test_6e_f2_wait_zero_makes_no_worker_call_and_returns_the_snapshot(db, worker, monkeypatch):
    import time as _time
    execution_id = _admitted(worker)
    monkeypatch.setattr(lane, "_trigger_background_reconcile", lambda: None)
    with get_db_session() as s:
        s.query(EstateExecution).update({"last_observed_at": None})
    calls = len(worker.calls)
    started = _time.monotonic()
    view = estate_router.get_estate_execution(execution_id, wait_s=0)
    assert _time.monotonic() - started < 2 and len(worker.calls) == calls
    assert view["execution_id"] == execution_id


def test_6e_f1_concurrent_start_callers_never_take_a_refusal_as_proof(db, worker, monkeypatch):
    """Caller A's start is paused in flight; caller B (e.g. a reconcile)
    issues a second start that is refused pre-claim. B must not resolve
    not_started: two attempts were issued."""
    import threading as _threading
    _lease()
    worker.start_mode = "refuse"
    paused, go = _threading.Event(), _threading.Event()
    real_call = worker.call
    first = {"seen": False}

    def _call(host_id, verb, payload, *, deadline_s):
        if verb == "start" and not first["seen"]:
            first["seen"] = True
            paused.set()
            go.wait(5)
            worker.start_mode = "normal"
        return real_call(host_id, verb, payload, deadline_s=deadline_s)

    monkeypatch.setattr(worker.client, "call_worker", _call)
    monkeypatch.setattr(lane, "_dispatch_start", lane._dispatch_start)
    outcome = {}
    dispatch = _threading.Thread(target=lambda: outcome.update(a=_dispatch()))
    dispatch.start()
    assert paused.wait(5)
    with get_db_session() as s:
        execution_id = s.query(EstateExecution).one().id
    lane._dispatch_start(execution_id)                      # caller B: refused pre-claim
    # B's refusal was NOT taken as proof (two attempts were issued); B
    # fenced instead, and the fence won on the worker before A's paused
    # start arrived -- so not_started now rests on the fence, not the refusal.
    fences = [p for _h, v, p in worker.calls if v == "status" and p.get("fence")]
    assert fences and fences[0]["execution_id"] == execution_id
    assert _row(execution_id).worktree_resolution == "not_started"
    go.set()
    dispatch.join(10)
    assert worker.executions[execution_id].get("claim") == "fence"
    assert "spawns" not in worker.executions[execution_id]      # A's delayed start never spawned
    assert _row(execution_id).worktree_resolution == "not_started"


def test_6e_f1_refusal_is_proof_only_for_the_sole_first_attempt(db, worker):
    _lease()
    worker.start_mode = "refuse"
    execution_id = _dispatch()["execution_id"]
    placeholder = json.loads(_row(execution_id).worker_handle_json)
    assert placeholder["start_attempts"] == 1
    assert _row(execution_id).worktree_resolution == "not_started"
    assert not [p for _h, v, p in worker.calls if v == "status"]       # no fence needed: sole attempt
