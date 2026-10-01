"""Stage 6 §G coverage completion (6e adjudication finding 3): the
control-plane and HTTP halves of scenarios that were only partially
exercised -- U18, U19, U20, U22, U25, U33, U36, U38, U39, U40/U47, U42(f),
U46, U50, U51, U55, U56, U59, U63, U64, U65, U66, U75, U76 -- plus I7 and
I8 over HTTP (TestClient) and I10's `aoteru recover` client path."""
import json
import os
import threading
import time
from datetime import timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.helpers.import_state import clear_fake_database_modules
from tests.helpers.sqlite_db import make_temp_sqlite

clear_fake_database_modules()

import core.database as cdb
from core.database import EstateExecution, ParkLease, get_db_session, utcnow_naive
from src import estate_router, park_lease_ops
from src import estate_write_lane as lane
from tests.helpers.fake_worker import FakeWorker

LAB, HOME = "hz2-workstation", "desktop-in7o23d"
HEAD = "a" * 40


@pytest.fixture
def db(monkeypatch):
    session_local, engine, tmpfile = make_temp_sqlite(cdb.Base.metadata)
    monkeypatch.setattr(cdb, "SessionLocal", session_local)
    monkeypatch.setattr(estate_router, "current_host_id", lambda: LAB)
    monkeypatch.setattr(lane, "_observe_worker_execution", lambda execution_id: None)
    monkeypatch.setattr(lane, "_trigger_background_reconcile", lambda: None)
    outcomes = []
    monkeypatch.setattr(estate_router, "_update_decision_outcome",
                        lambda decision_id, **kwargs: outcomes.append((decision_id, kwargs)))
    yield outcomes
    engine.dispose()
    os.unlink(tmpfile.name)


@pytest.fixture
def worker(monkeypatch):
    return FakeWorker(monkeypatch, head=HEAD)


@pytest.fixture
def http(monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "false")
    import routes.estate_routing_routes as routes_mod
    monkeypatch.setattr(routes_mod, "current_host_id", lambda: LAB)
    app = FastAPI()
    app.include_router(routes_mod.setup_estate_routing_routes())
    return TestClient(app)


def _lease(lease_id="L1", host=HOME, status="active", worktree="/w/feat", branch="feat/x"):
    with get_db_session() as s:
        s.add(ParkLease(id=lease_id, repo_id="odysseus", host_id=host, worktree_path=worktree,
                        branch=branch, status=status))


def _row(execution_id):
    with get_db_session() as s:
        row = s.query(EstateExecution).filter(EstateExecution.id == execution_id).one()
        s.expunge(row)
        return row


def _dispatch(host=HOME, decision_id=None):
    return lane.execute_write_via_worker("change it", repo_id="odysseus", host_id=host, wait_timeout=0,
                                         decision_id=decision_id)


def _admitted(worker, decision_id=None):
    _lease()
    return _dispatch(decision_id=decision_id)["execution_id"]


def _observe(worker, execution_id, state, **kwargs):
    worker.set_state(execution_id, state, **kwargs)
    lane._apply_view(execution_id, worker._view(execution_id))


def _set(execution_id, **fields):
    with get_db_session() as s:
        s.query(EstateExecution).filter(EstateExecution.id == execution_id).update(fields)


def _lease_status(lease_id="L1"):
    with get_db_session() as s:
        return s.query(ParkLease).filter(ParkLease.id == lease_id).one().status


# ---------------------------------------------------------------------
# Observation
# ---------------------------------------------------------------------

def test_u18_bounded_wait_observes_running_to_succeeded_without_redispatch(db, worker):
    execution_id = _admitted(worker)
    _observe(worker, execution_id, "running", quiescent=False)
    _set(execution_id, last_observed_at=None)
    threading.Timer(0.5, lambda: worker.set_state(execution_id, "succeeded",
                                                  result={"ok": True, "output": "x"})).start()
    starts = worker.verbs().count("start")
    view = estate_router.get_estate_execution(execution_id, wait_s=30)
    deadline = time.monotonic() + 20
    while view["lifecycle_state"] != "succeeded" and time.monotonic() < deadline:
        _set(execution_id, last_observed_at=None)
        view = estate_router.get_estate_execution(execution_id, wait_s=30)
    assert view["lifecycle_state"] == "succeeded"
    assert worker.verbs().count("start") == starts                 # zero dispatch during observation


@pytest.mark.parametrize("stored", ["accepted", "running"])
def test_u19_interrupted_records_decision_outcome_with_executed_host(db, worker, stored):
    execution_id = _admitted(worker, decision_id="D1")
    if stored == "running":
        _observe(worker, execution_id, "running", quiescent=False)
    _observe(worker, execution_id, "interrupted", quiescent=True)
    assert _row(execution_id).lifecycle_state == "interrupted"
    recorded = [kw for decision, kw in db if decision == "D1"]
    assert recorded and recorded[-1]["executed_host_id"] == HOME and recorded[-1]["status"] == "failed"


def test_u20_unreachable_within_window_is_not_lost_then_lost_after(db, worker):
    execution_id = _admitted(worker)
    _observe(worker, execution_id, "running", quiescent=False)
    _set(execution_id, execution_deadline_at=utcnow_naive() + timedelta(seconds=30),
         last_observed_at=utcnow_naive() - timedelta(seconds=600))
    for _ in range(3):
        assert lane._mark_lost_if_due(execution_id) is False           # inside deadline + grace
    assert _row(execution_id).lifecycle_state == "running"
    _set(execution_id, execution_deadline_at=utcnow_naive() - timedelta(seconds=lane.LOST_GRACE_SECONDS + 1))
    assert lane._mark_lost_if_due(execution_id) is True
    assert _row(execution_id).lifecycle_state == "lost"


@pytest.mark.parametrize("worker_state,expected", [("running", "running"), ("interrupted", "interrupted"),
                                                   ("failed", "failed")])
def test_u22_lost_reconciles_to_every_truthful_state(db, worker, worker_state, expected):
    execution_id = _admitted(worker)
    _observe(worker, execution_id, "running", quiescent=False)
    _set(execution_id, lifecycle_state="lost")
    worker.set_state(execution_id, worker_state, quiescent=worker_state != "running",
                     result={"ok": False, "error": "x"} if worker_state == "failed" else None)
    starts = worker.verbs().count("start")
    lane._apply_view(execution_id, worker._view(execution_id))
    row = _row(execution_id)
    assert row.lifecycle_state == expected and row.worktree_resolution == "unresolved"
    assert worker.verbs().count("start") == starts


def test_u33_no_renewal_for_starting_or_after_failed_status(db, worker):
    execution_id = _admitted(worker)
    old = utcnow_naive() - timedelta(seconds=900)
    with get_db_session() as s:
        s.query(ParkLease).update({"heartbeat_at": old})
    lane._apply_view(execution_id, {"state": "starting"})
    worker.fail["status"] = ["worker_unreachable"]
    view, exc = lane._worker(HOME, "status", {"execution_id": execution_id}, deadline_s=5)
    assert exc is not None
    with get_db_session() as s:
        assert s.query(ParkLease).one().heartbeat_at == old
    assert not [v for _h, v, _p in worker.calls if "heartbeat" in v or "lease" in v]


def test_u63_tombstone_for_an_unresolved_row_stays_unresolved_with_error(db, worker):
    execution_id = _admitted(worker)
    lane._apply_view(execution_id, {"state": "tombstone", "released": True})
    row = _row(execution_id)
    assert row.worktree_resolution == "unresolved" and row.error == "spool_released_before_resolution"


# ---------------------------------------------------------------------
# Admission / start
# ---------------------------------------------------------------------

def test_u40_u47_start_answer_start_failed_is_not_started(db, worker, monkeypatch):
    _lease()
    real = worker._start
    monkeypatch.setattr(worker, "_start", lambda payload: {**real(payload), "state": "start_failed"}
                        if not worker.executions.update({payload["execution_id"]: {"claim": "start",
                                                                                    "state": "start_failed",
                                                                                    "quiescent": True}})
                        else None)
    execution_id = _dispatch()["execution_id"]
    row = _row(execution_id)
    assert row.lifecycle_state == "failed" and row.worktree_resolution == "not_started"
    assert _dispatch()["dispatch"] == "new"


def test_u46_starting_answers_keep_the_row_pending_never_failed(db, worker):
    execution_id = _admitted(worker)
    for _ in range(3):
        lane._apply_view(execution_id, {"state": "starting", "handle": None})
        row = _row(execution_id)
        assert row.lifecycle_state == "accepted" and lane._is_placeholder(row)


def test_u64_moved_head_start_refusal_maps_to_not_started(db, worker):
    _lease()
    worker.start_mode = "refuse"               # worker refuses pre-claim: HEAD != expected_head_sha
    execution_id = _dispatch()["execution_id"]
    assert _row(execution_id).worktree_resolution == "not_started"
    start = [p for _h, v, p in worker.calls if v == "start"][0]
    assert start["lease"]["expected_head_sha"] == HEAD


@pytest.mark.parametrize("dirty", [False, True])
def test_u38_started_failed_rows_block_with_clean_or_dirty_worktree(db, worker, dirty):
    _lease()
    with get_db_session() as s:
        s.add(EstateExecution(id="E-old", objective="o", executor="codex-write", provider="codex",
                              host_id=HOME, repo_id="odysseus", lease_id="L1", lifecycle_state="failed",
                              worker_handle_json=json.dumps({"pid": 1}), worktree_resolution="unresolved"))
    worker.clean = not dirty
    result = _dispatch()
    assert result["ok"] is False and "start" not in worker.verbs()
    # §G U38: the unresolved row decides, clean or dirty -- a clean tree
    # never reopens admission; only S6.2 recovery does. No worker call.
    assert result["error_code"] == "lease_has_unresolved_worktree"
    assert worker.calls == []


def test_u65_admission_under_the_lease_while_push_failed(db, worker):
    execution_id = _admitted(worker)
    _observe(worker, execution_id, "succeeded", result={"ok": True, "output": "x"})
    worker.head = "b" * 40
    worker.finalize_outcome = {**worker.finalize_outcome, "push": {"state": "failed", "commit_sha": "b" * 40}}
    assert lane.finalize_execution(execution_id=execution_id, repo_id="odysseus", host_id=HOME,
                                   commit_message="x")["finalized"] is True
    worker.head = "b" * 40
    assert _dispatch()["dispatch"] == "new"


def test_u66_push_with_unreachable_worker_leaves_state_unchanged(db, worker):
    execution_id = _admitted(worker)
    _observe(worker, execution_id, "succeeded", result={"ok": True, "output": "x"})
    worker.head = "b" * 40
    worker.finalize_outcome = {**worker.finalize_outcome, "push": {"state": "failed", "commit_sha": "b" * 40}}
    lane.finalize_execution(execution_id=execution_id, repo_id="odysseus", host_id=HOME, commit_message="x")
    before = json.loads(_row(execution_id).finalization_json)["push"]
    worker.fail["worktree.push"] = ["worker_unreachable"]
    assert lane.push_finalized_execution(execution_id)["code"] == "worker_unreachable"
    assert json.loads(_row(execution_id).finalization_json)["push"] == before


# ---------------------------------------------------------------------
# Finalize / recovery
# ---------------------------------------------------------------------

def _succeeded(worker):
    execution_id = _admitted(worker)
    _observe(worker, execution_id, "succeeded", result={"ok": True, "output": "x"})
    return execution_id


def test_u36_finalize_refused_when_lease_reassigned(db, worker):
    execution_id = _succeeded(worker)
    with get_db_session() as s:
        s.query(ParkLease).update({"status": "released"})
    _lease("L2")                                                       # same repo/host, later lease
    calls = len(worker.calls)
    result = lane.finalize_execution(execution_id=execution_id, repo_id="odysseus", host_id=HOME,
                                     commit_message="x")
    assert result["finalized"] is False and "drift" in result["reason"]
    assert len(worker.calls) == calls


def test_u39_dirty_post_finalize_verify_leaves_the_row_unresolved(db, worker):
    execution_id = _succeeded(worker)
    worker.head = "b" * 40
    real_verify = worker._worktree_verify

    def _dirty_after_finalize(payload):
        answer = real_verify(payload)
        if "worktree.finalize" in worker.verbs():
            answer["clean"] = False
        return answer
    worker._worktree_verify = _dirty_after_finalize
    result = lane.finalize_execution(execution_id=execution_id, repo_id="odysseus", host_id=HOME,
                                     commit_message="x")
    assert result["finalized"] is False and _row(execution_id).worktree_resolution == "unresolved"


def test_u42f_row_or_lease_changed_between_precheck_and_transaction(db, worker):
    execution_id = _admitted(worker)
    _observe(worker, execution_id, "running", quiescent=False)
    _observe(worker, execution_id, "interrupted", quiescent=True)
    worker.on_call = lambda host, verb, payload: verb == "worktree.verify" and _bump_heartbeat_and_handle(
        execution_id)
    result = lane.recover_execution_lease(execution_id, lease_id="L1", host_id=HOME, repo_id="odysseus",
                                          branch="feat/x", worktree_path="/w/feat")
    assert result["recovered"] is False and result["code"] == "changed_during_recovery"
    assert _lease_status() == "active" and _row(execution_id).worktree_resolution == "unresolved"


def _bump_heartbeat_and_handle(execution_id):
    _set(execution_id, worker_handle_json=json.dumps({"pid": 1, "changed": True}))
    return True


def test_u75_paused_finalize_after_recovery_and_new_park_is_refused(db, worker):
    """A finalize authorised earlier reaches the worker only after recovery
    closed E1, a fresh park and a new execution E2 exist: the closure makes
    the worker refuse, and nothing is recorded on E1."""
    execution_id = _succeeded(worker)
    paused, go = threading.Event(), threading.Event()
    real_finalize = worker._worktree_finalize

    def _paused(payload):
        paused.set()
        go.wait(5)
        return real_finalize(payload)
    worker._worktree_finalize = _paused
    outcome = {}
    finalizer = threading.Thread(target=lambda: outcome.update(f=lane.finalize_execution(
        execution_id=execution_id, repo_id="odysseus", host_id=HOME, commit_message="late")))
    finalizer.start()
    assert paused.wait(5)
    recovered = lane.recover_execution_lease(execution_id, lease_id="L1", host_id=HOME, repo_id="odysseus",
                                             branch="feat/x", worktree_path="/w/feat")
    assert recovered["recovered"] is True
    _lease("L2")
    e2 = _dispatch()
    assert e2["dispatch"] == "new"
    go.set()
    finalizer.join(10)
    assert outcome["f"]["finalized"] is False
    assert _row(execution_id).worktree_resolution == "recovered"


# ---------------------------------------------------------------------
# Park with worktree
# ---------------------------------------------------------------------

def _assert_reservation_at_prepare(worker):
    def _check(host, verb, payload):
        if verb == "worktree.prepare":
            with get_db_session() as s:
                row = s.query(ParkLease).filter(ParkLease.id == payload["lease"]["lease_id"]).one()
                assert row.status == "preparing" and row.host_id == payload["lease"]["host_id"]
    worker.on_call = _check


def test_u50_u59_every_prepare_runs_under_a_committed_reservation_never_in_process(db, worker, monkeypatch):
    _assert_reservation_at_prepare(worker)
    from src import worktree_ops
    monkeypatch.setattr(worktree_ops, "create_or_reuse_worktree",
                        lambda *a, **k: pytest.fail("the control plane must never prepare in-process"))
    for branch in ("feat/a", "feat/b"):
        result = park_lease_ops.park_with_worktree("odysseus", LAB, branch)
        park_lease_ops.release_repo("odysseus", host_id=LAB)
    assert worker.verbs().count("worktree.prepare") == 2


def test_u51_pre_claim_refusal_releases_and_reclaimed_before_bind_is_refused(db, worker):
    worker.fail["worktree.prepare"] = ["bad_request"]
    with pytest.raises(park_lease_ops.WorktreeVerificationError):
        park_lease_ops.park_with_worktree("odysseus", LAB, "feat/y")
    with get_db_session() as s:
        assert s.query(ParkLease).filter(ParkLease.status.in_(("active", "preparing"))).count() == 0

    def _steal(host, verb, payload):
        if verb == "worktree.prepare":
            with get_db_session() as s:
                s.query(ParkLease).filter(ParkLease.id == payload["lease"]["lease_id"]).update(
                    {"status": "released"})
                s.add(ParkLease(id="OTHER", repo_id="odysseus", host_id=HOME, worktree_path="/o",
                                branch="feat/o", status="active"))
    worker.on_call = _steal
    with pytest.raises(park_lease_ops.WorktreeVerificationError, match="changed before bind"):
        park_lease_ops.park_with_worktree("odysseus", LAB, "feat/y")
    assert _lease_status("OTHER") == "active"


@pytest.mark.parametrize("state", ["fenced", "prepare_failed", "prepare_interrupted", "prepared"])
def test_u56_every_proven_terminal_state_releases_on_resolve(db, worker, state):
    worker.fail["worktree.prepare"] = ["worker_unreachable"]
    with pytest.raises(park_lease_ops.PrepareOutcomeUnresolved) as info:
        park_lease_ops.park_with_worktree("odysseus", HOME, "feat/y")
    worker.prepare_status_answer = {"state": state, "quiescent": True}
    assert park_lease_ops.resolve_preparing_reservation(info.value.lease_id)["released"] is True
    assert _lease_status(info.value.lease_id) == "released"


def test_u56_unreachable_probe_changes_nothing(db, worker):
    worker.fail["worktree.prepare"] = ["worker_unreachable"]
    with pytest.raises(park_lease_ops.PrepareOutcomeUnresolved) as info:
        park_lease_ops.park_with_worktree("odysseus", HOME, "feat/y")
    worker.fail["worktree.prepare_status"] = ["worker_unreachable"]
    assert park_lease_ops.resolve_preparing_reservation(info.value.lease_id)["reason"] == "worker_unreachable"
    assert _lease_status(info.value.lease_id) == "preparing"


# ---------------------------------------------------------------------
# HTTP: I7, I8, U55, U76, I10 client
# ---------------------------------------------------------------------

def _home_eligible(monkeypatch):
    monkeypatch.setattr(estate_router, "eligible_hosts", lambda repo_id=None: [
        {"host_id": LAB, "eligible": True, "qualified_executors": ["local", "codex-write"]},
        {"host_id": HOME, "eligible": True, "qualified_executors": ["local", "codex-write"]},
    ])


def test_i7_remote_host_park_heartbeat_release_over_http(db, worker, http, monkeypatch):
    _home_eligible(monkeypatch)
    _assert_reservation_at_prepare(worker)
    response = http.post("/api/estate/park/odysseus", params={"host": HOME, "branch": "acceptance/home"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "active" and body["host_id"] == HOME and body["worktree_path"] == worker.path
    prepare = [(h, p) for h, v, p in worker.calls if v == "worktree.prepare"]
    assert prepare[0][0] == HOME and prepare[0][1]["lease"]["lease_id"] == body["lease_id"]
    assert http.post("/api/estate/park/odysseus/heartbeat", params={"host": HOME}).status_code == 200
    released = http.post("/api/estate/park/odysseus/release", params={"host": HOME})
    assert released.status_code == 200 and _lease_status(body["lease_id"]) == "released"


def test_i7_remote_park_requires_codex_write_qualification_and_branch(db, worker, http, monkeypatch):
    monkeypatch.setattr(estate_router, "eligible_hosts", lambda repo_id=None: [
        {"host_id": HOME, "eligible": True, "qualified_executors": ["local"]}])
    assert http.post("/api/estate/park/odysseus", params={"host": HOME, "branch": "x"}).status_code == 409
    assert http.post("/api/estate/park/odysseus", params={"host": HOME}).status_code == 422
    assert "worktree.prepare" not in worker.verbs()


def test_i8_remote_prepare_not_clean_is_the_repo_not_clean_409(db, worker, http, monkeypatch):
    _home_eligible(monkeypatch)
    worker.prepare_answer = {"state": "prepared", "path": "/w", "branch": None, "head_sha": HEAD,
                             "clean": False, "quiescent": True}
    response = http.post("/api/estate/park/odysseus", params={"host": HOME, "branch": "b"})
    assert response.status_code == 409 and "not clean" in response.text
    with get_db_session() as s:
        assert s.query(ParkLease).filter(ParkLease.status.in_(("active", "preparing"))).count() == 0


@pytest.mark.parametrize("code", ["worker_unreachable", "worker_protocol_error"])
def test_u55_http_ambiguous_prepare_is_a_structured_409_keeping_the_reservation(db, worker, http,
                                                                                monkeypatch, code):
    _home_eligible(monkeypatch)
    worker.fail["worktree.prepare"] = [code]
    response = http.post("/api/estate/park/odysseus", params={"host": HOME, "branch": "b"})
    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["error"] == "prepare_outcome_unresolved" and "resolve-prepare" in detail["next_action"]["cli"]
    assert _lease_status(detail["lease_id"]) == "preparing"
    resolved = http.post("/api/estate/park/odysseus/resolve-prepare",
                         json={"lease_id": detail["lease_id"], "host_id": HOME})
    assert resolved.status_code == 200 and resolved.json()["released"] is True


def test_u76_http_push_after_closure_and_recover_route(db, worker, http):
    execution_id = _succeeded(worker)
    worker.head = "b" * 40
    worker.finalize_outcome = {**worker.finalize_outcome, "push": {"state": "failed", "commit_sha": "b" * 40}}
    assert lane.finalize_execution(execution_id=execution_id, repo_id="odysseus", host_id=HOME,
                                   commit_message="x")["finalized"] is True
    assert worker.executions[execution_id]["closed"] is True                # closed before recording
    pushed = http.post(f"/api/estate/run/{execution_id}/push")
    assert pushed.status_code == 200 and pushed.json()["pushed"] is True
    assert http.post(f"/api/estate/run/{execution_id}/push").status_code == 409    # no longer eligible


def test_i10_laptop_recover_and_execution_commands_against_the_api(db, worker, http, monkeypatch, capsys):
    import companion.laptop_client.aoteru as client
    execution_id = _admitted(worker)
    _observe(worker, execution_id, "running", quiescent=False)
    _observe(worker, execution_id, "interrupted", quiescent=True)

    def _request(cfg, method, path, body=None, timeout=30.0):
        response = http.request(method, path, json=body)
        return {"status": response.status_code, "body": response.json()}
    monkeypatch.setattr(client, "_load_config", lambda: {"url": "http://test", "token": "t"})
    monkeypatch.setattr(client, "_request", _request)
    assert client.main(["execution", execution_id, "--wait", "0"]) == 0
    assert json.loads(capsys.readouterr().out)["lifecycle_state"] == "interrupted"
    assert "start" not in [v for _h, v, _p in worker.calls[2:]]
    rc = client.main(["recover", "odysseus", "--execution", execution_id, "--lease", "L1", "--host", HOME,
                      "--branch", "feat/x", "--worktree", "/w/feat"])
    assert rc == 0 and json.loads(capsys.readouterr().out)["recovered"] is True
    assert _lease_status() == "released"


# ---------------------------------------------------------------------
# U25 telemetry
# ---------------------------------------------------------------------

@pytest.mark.parametrize("host,fail", [(LAB, None), (HOME, None), (HOME, "worker_unreachable"),
                                       (HOME, "execution_failed")])
def test_u25_routing_decision_host_equals_route_host_and_executed_host_is_route_or_null(host, fail, monkeypatch):
    import src.estate_worker_client as client
    recorded = {}
    monkeypatch.setattr(estate_router, "_update_decision_outcome",
                        lambda decision_id, **kw: recorded.update(kw))
    monkeypatch.setattr(estate_router, "resolve_route", lambda task: {
        "decision_id": "D", "route": {"host": host, "executor": "local", "concrete_model": "m",
                                      "model_alias": "local-fast"},
        "hosts_checked": [{"host_id": host, "qualified_executors": ["local"]}]})

    def _call(host_id, verb, payload, *, deadline_s):
        assert host_id == host
        if fail:
            raise client.WorkerTransportError(fail, "x")
        return {"ok": True, "result": {"ok": True, "output": "hi"}, "attestation": {"host_id": host_id}}
    monkeypatch.setattr(client, "call_worker", _call)
    result = estate_router.run_task({"objective": "hi", "requirements": {"capabilities": ["local-fast"]}})
    assert result["route"]["host"] == host
    assert recorded.get("executed_host_id") in (host, None)



def test_gate_f1_get_observation_never_issues_a_start_and_stays_in_budget(db, worker, monkeypatch):
    execution_id = _admitted(worker)
    worker.executions.pop(execution_id)                      # worker reports `unknown`
    _set(execution_id, last_observed_at=None)
    slow = {"called": 0}
    real_start = worker._start

    def _slow_start(payload):
        slow["called"] += 1
        time.sleep(5)
        return real_start(payload)
    monkeypatch.setattr(worker, "_start", _slow_start)
    starts = worker.verbs().count("start")
    began = time.monotonic()
    estate_router.get_estate_execution(execution_id, wait_s=18)
    assert worker.verbs().count("start") == starts and slow["called"] == 0
    assert time.monotonic() - began < 19


def test_u46_control_plane_keeps_pending_start_while_the_claim_is_starting(db, worker):
    execution_id = _admitted(worker)
    worker.set_state(execution_id, "starting", quiescent=None)
    for _ in range(3):
        lane._apply_view(execution_id, worker._view(execution_id))
        assert _row(execution_id).lifecycle_state == "accepted"
    worker.set_state(execution_id, "running", quiescent=False)
    lane._apply_view(execution_id, worker._view(execution_id))
    assert _row(execution_id).lifecycle_state == "running"
    assert worker.executions[execution_id].get("spawns", 1) == 1


def test_u71_control_plane_restart_between_worker_commit_and_resolution(db, worker):
    """The worker committed (finalize_result recorded) but the control plane
    'restarted' before the resolution write: a fresh finalize_execution
    call (no process state carried over) closes and records finalized."""
    execution_id = _admitted(worker)
    _observe(worker, execution_id, "succeeded", result={"ok": True, "output": "x"})
    worker.head = "b" * 40
    worker.executions[execution_id]["finalize_result"] = dict(worker.finalize_outcome)
    worker.executions[execution_id]["closed"] = True          # the first attempt had already closed
    result = lane.finalize_execution(execution_id=execution_id, repo_id="odysseus", host_id=HOME,
                                     commit_message="x")
    assert result["finalized"] is True and _row(execution_id).worktree_resolution == "finalized"
