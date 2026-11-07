"""Provider cooldown is computed from executed outcomes, never admission refusals."""
import json
from itertools import product
import os
import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
import core.database as cdb
from src import estate_router as router, estate_write_lane as write_lane
from src.delegation_preflight import delegation_preflight
from tests.helpers.sqlite_db import make_temp_sqlite
from tests.test_estate_router import fixture_config  # noqa: F401

NOW = datetime(2026, 11, 5, 12, tzinfo=timezone.utc)
LIMIT = "ERROR: You've hit your usage limit. Please try again at 5:39 PM."
TASK = {"task_class": "code_review", "objective": "Review this code",
        "requirements": {"capabilities": ["reasoning-strong"]}}


@pytest.fixture
def lab(fixture_config, monkeypatch, tmp_path):
    session, engine, handle = make_temp_sqlite(cdb.Base.metadata)
    monkeypatch.setattr(cdb, "SessionLocal", session)

    class Clock(datetime):
        current = NOW

        @classmethod
        def now(cls, tz=None):
            return cls.current.astimezone(tz) if tz else cls.current.replace(tzinfo=None)

    monkeypatch.setattr(router, "datetime", Clock)
    monkeypatch.setattr(cdb, "datetime", Clock)
    monkeypatch.setattr(write_lane, "_now", lambda: Clock.current.replace(tzinfo=None))
    monkeypatch.setattr(router, "resolve_latest_codex_model", lambda _: "gpt-6.1-sol")
    monkeypatch.setattr(router, "subscription_effort", lambda: "high")
    binary, count = tmp_path / "codex", tmp_path / "calls"
    monkeypatch.setattr(router, "_codex_available", lambda: (True, str(binary)))

    def executable(text=LIMIT, stream="stderr", success=False):
        binary.write_text(f"#!{sys.executable}\nimport sys\nfrom pathlib import Path\n"
                          f"with open({str(count)!r}, 'a') as f: f.write('call\\n')\n"
                          f"print({text!r}, file=sys.{stream})\n"
                          + ("Path(sys.argv[sys.argv.index('-o') + 1]).write_text('review complete')\n"
                             if success else "sys.exit(1)\n"))
        binary.chmod(0o755)

    executable()
    import src.estate_worker_client as client

    def call(host, verb, payload, **kwargs):
        assert verb == "execute" and host == "test-lab"
        return {"result": router.execute_codex(payload["objective"]),
                "attestation": {"host_id": host}}

    monkeypatch.setattr(client, "call_worker", call)
    yield Clock, executable, count
    engine.dispose()
    os.unlink(handle.name)


def record_outcome(result):
    """Seed an externally observed outcome, independently of admission."""
    import uuid
    key = str(uuid.uuid4())
    with cdb.get_db_session() as db:
        latest = db.query(cdb.RoutingDecision).filter_by(task_class="provider_outcome").order_by(
            cdb.RoutingDecision.created_at.desc()).first()
        created = router.datetime.now(timezone.utc).replace(tzinfo=None)
        if latest:
            created = max(created, latest.created_at + timedelta(microseconds=1))
        db.add(cdb.RoutingDecision(id=key, task_class="provider_outcome", executor="codex",
            host_id="test-lab", status="complete", created_at=created,
            escalation_reason=json.dumps({"provider_health": router._provider_outcome(result)})))
    return key


def preflight():
    return delegation_preflight([{"task_class": "code_review", "objective": "Review code",
                                  "capabilities": ["reasoning-strong"]}])


def run(implementation_mode=False):
    return router.run_task({**TASK, "routing": {"allow_paid_escalation": True,
                           "mode": "implementation" if implementation_mode else "advisory"}})


@pytest.mark.parametrize("stream", ["stderr", "stdout"])
def test_real_limit_preflight_and_repeated_read_refusal(lab, stream):
    clock, executable, count = lab
    executable(stream=stream)
    first = run()
    assert first["executed"] and not first["execution"]["ok"]
    result = preflight()
    health = result["snapshot"]["provider_health"]["codex"]
    assert health["state"] == "quota_exhausted"
    assert health["retry_after"] == "2026-11-05T17:39:00+00:00"
    assert not health["allowed"] and not result["snapshot"]["codex"]["available"]
    assert result["snapshot"]["codex"]["runtime_available"]
    assert result["units"][0]["recommended_route"] is None
    assert result["snapshot"]["eligible_hosts"][0]["eligible"]
    for _ in range(3):
        refused = run()
        assert not refused["executed"] and "provider codex: quota_exhausted" in refused["execution_error"]
    assert outcome_count() == 1
    assert count.read_text().splitlines() == ["call"]
    assert not router.resolve_route(TASK, record_decision=False)["provider_health"]["allowed"]


def test_assumed_backoff_and_successful_recovery(lab):
    clock, executable, count = lab
    executable("You've hit your usage limit; try again when refreshed")
    run()
    health = router.provider_allows_dispatch("codex")
    assert health["retry_after_assumed"]
    assert health["retry_after"] == "2026-11-05T12:15:00+00:00"
    clock.current += timedelta(minutes=16)
    assert router.provider_allows_dispatch("codex")["allowed"]
    assert router.provider_allows_dispatch("codex")["state"] == "quota_exhausted"
    executable("", success=True)
    assert run()["execution"]["ok"]
    assert router.provider_allows_dispatch("codex")["state"] == "ok"
    assert preflight()["units"][0]["recommended_route"] == "codex"
    assert len(count.read_text().splitlines()) == 2


@pytest.mark.parametrize("text,state", [("401 Unauthorized: authentication failed", "auth_failed"),
                                       ("Network connection failed: unreachable", "unreachable")])
def test_provider_failures_are_surfaced(lab, text, state):
    lab[1](text)
    run()
    assert preflight()["snapshot"]["provider_health"]["codex"]["state"] == state
    assert f"provider codex: {state}" in run()["execution_error"]


def test_unreadable_latest_and_later_valid_outcome(lab):
    run()
    with cdb.get_db_session() as db:
        row = db.query(cdb.RoutingDecision).filter_by(task_class="provider_outcome").one()
        row.escalation_reason = "{broken json"
    assert router.provider_allows_dispatch("codex")["state"] == "unknown"
    assert "unparseable" in run()["execution_error"]
    # A later externally observed valid outcome clears unknown without a latch.
    decision = record_outcome({"ok": True, "exit_code": 0, "state": "completed"})
    with cdb.get_db_session() as db:
        db.query(cdb.RoutingDecision).filter_by(id=decision).update({"created_at": NOW.replace(tzinfo=None) + timedelta(days=1)})
    assert router.provider_allows_dispatch("codex")["state"] == "ok"


def test_database_read_failure_is_provider_scoped(lab, monkeypatch):
    def fail():
        raise OSError("unreadable database")
    monkeypatch.setattr(cdb, "get_db_session", fail)
    health = router.provider_allows_dispatch("codex")
    assert not health["allowed"] and health["state"] == "unknown"
    assert "provider codex" in health["reason"]


@pytest.mark.parametrize("reset,expected,assumed", [
    ("5:39 PM.", "2026-11-05T17:39:00+00:00", False),
    ("5:39 AM.", "2026-11-06T05:39:00+00:00", False),
    ("Nov 6th, 2026 5:39 PM.", "2026-11-06T17:39:00+00:00", False),
    ("5:39 PM on November 6, 2026.", "2026-11-06T17:39:00+00:00", False),
    ("5:39 PM on 2026-11-06.", "2026-11-06T17:39:00+00:00", False),
    ("2026-11-06T17:39:00Z.", "2026-11-06T17:39:00+00:00", False),
    ("Nov 1st, 2026 5:39 PM.", "2026-11-06T17:39:00+00:00", False),
    ("2026-12-01 17:39.", "2026-11-12T12:00:00+00:00", False),
    ("nonsense", "2026-11-05T12:15:00+00:00", True),
    ("25:99 PM.", "2026-11-05T12:15:00+00:00", True),
    ("5:39 PM on an unknown date.", "2026-11-05T12:15:00+00:00", True),
])
def test_reset_wall_clock_in_lab_gmt(reset, expected, assumed):
    health = router._provider_outcome(
        {"error": "You've hit your usage limit. Please try again at " + reset}, NOW, host_tz=ZoneInfo("GMT"))
    assert health["state"] == "quota_exhausted" and health["retry_after"] == expected
    assert health["retry_after_assumed"] == assumed


def test_explicit_host_timezone():
    health = router._provider_outcome({"error": LIMIT}, NOW, host_tz=ZoneInfo("Asia/Tokyo"))
    assert health["state"] == "quota_exhausted" and health["retry_after"] == "2026-11-06T08:39:00+00:00"
    assert router._provider_outcome({"error": LIMIT}, NOW.replace(tzinfo=None), host_tz=ZoneInfo("GMT"))["retry_after"] == "2026-11-05T17:39:00+00:00"


def test_api_and_agent_status_report_the_same_provider_fact(lab, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from routes.estate_routing_routes import setup_estate_routing_routes
    from tests.test_agent_cli_recent_routing_decisions import load_module
    run()
    expected = router.provider_allows_dispatch("codex")
    app = FastAPI()

    @app.middleware("http")
    async def authenticated(request, call_next):
        request.state.current_user = "operator"
        return await call_next(request)

    app.include_router(setup_estate_routing_routes())
    with TestClient(app) as client:
        response = client.post("/api/estate/preflight", json={"units": [{
            "task_class": "code_review", "capabilities": ["reasoning-strong"]}]})
    assert response.status_code == 200
    assert response.json()["snapshot"]["provider_health"]["codex"] == expected
    agent = load_module()
    monkeypatch.setattr(agent, "_load_yaml", router._load_yaml)
    monkeypatch.setattr(agent, "_load_host_local", lambda: {})
    monkeypatch.setattr(agent, "_live_host_inventory", lambda: {"hostname": "THIS-HOST"})
    monkeypatch.setattr(agent, "_resolve_repos", lambda _: [])
    monkeypatch.setattr(agent, "_capabilities_on_this_host", lambda *_: [])
    emitted = {}
    monkeypatch.setattr(agent, "emit", lambda value, _: emitted.update(value))
    agent.cmd_status(None)
    assert emitted["provider_health"]["codex"] == expected


def test_qualified_local_alternative_does_not_grant_write_authority(lab, monkeypatch):
    run()
    original = router._load_yaml

    def config(name):
        result = original(name)
        if name == "models":
            result["capabilities"][1].update(binding="test-model", qualified_hosts={"test-lab": {"evidence": "test"}})
        return result

    monkeypatch.setattr(router, "_load_yaml", config)
    result = preflight()["units"][0]
    assert result["ok"] and result["recommended_route"] == "local"
    assert "eligible alternative" in result["reason"]
    result = delegation_preflight([{"task_class": "code_implementation", "repo": "odysseus",
                                    "capabilities": ["reasoning-strong"]}])["units"][0]
    assert not result["ok"] and result["recommended_route"] is None


def test_existing_timestamp_order_and_uuid_tiebreak(lab):
    with cdb.get_db_session() as db:
        for key, ok, age in (("z-random", True, 0), ("a-random", False, 0), ("zz-older", False, 1)):
            db.add(cdb.RoutingDecision(id=key, task_class="provider_outcome", host_id="test-lab",
                executor="codex", status="complete", created_at=NOW.replace(tzinfo=None) - timedelta(seconds=age),
                escalation_reason=json.dumps({"provider_health": {"state": "ok" if ok else "unknown",
                    "retry_after": None, "reason": "stored observation", "retry_after_assumed": False}})))
    assert router.provider_allows_dispatch("codex")["state"] == "ok"


@pytest.fixture
def worker_lane(lab, monkeypatch, tmp_path):
    """Real protocol + spool/controller logic; fake only units and worktree probes."""
    from src import estate_worker as worker, estate_worker_client as client
    from src.estate_worker_protocol import build_request
    from tests.helpers.fake_units import FakeUnits
    monkeypatch.setattr(worker, "_SPOOL_ROOT", tmp_path / "spool")
    monkeypatch.setattr(worker, "_PREPARE_ROOT", tmp_path / "prepare")
    monkeypatch.setattr(worker, "_DECISION_FS_PROBED", {})
    monkeypatch.setattr(worker, "_worker_version", lambda: "test")
    monkeypatch.setattr(worker, "machine_fingerprint", lambda: "test")
    monkeypatch.setattr(worker, "_worktree_verification", lambda *args: {
        "ok": True, "clean": True, "head_sha": "abc", "path": str(tmp_path)})
    units = FakeUnits(tmp_path, monkeypatch, worker)
    calls = []

    def call(host, verb, payload, *, deadline_s=60):
        calls.append(verb)
        response = worker.handle(build_request(verb, host, payload, deadline_s))
        assert response["ok"], response
        return response

    monkeypatch.setattr(client, "call_worker", call)

    def finish(execution_id):
        unit = f"aoteru-run-{execution_id}.service"
        units.enter(unit)
        worker._run_spooled(execution_id)
        units.set_populated(unit, None)
        return call("test-lab", "status", {"execution_id": execution_id})["result"]

    monkeypatch.setattr(write_lane, "_observe_worker_execution", lambda execution_id:
                        write_lane._apply_view(execution_id, finish(execution_id)))
    monkeypatch.setattr(router, "resolve_repo_path", lambda _: str(tmp_path))
    with cdb.get_db_session() as db:
        db.add(cdb.ParkLease(id="L1", repo_id="odysseus", host_id="test-lab",
                            worktree_path=str(tmp_path), branch="feature", status="active"))
    # The routed write must pass the existing qualification gate too.
    import yaml
    path = router._CONFIG_DIR / "estate.yaml"
    config = yaml.safe_load(path.read_text())
    config["hosts"][0]["worker"]["qualified_executors"].append("codex-write")
    path.write_text(yaml.safe_dump(config))
    payload = {"execution_id": "spooled", "kind": "codex-write", "objective": "change",
               "repo_id": "odysseus", "timeout_s": 1800,
               "lease": {"lease_id": "L1", "worktree_path": str(tmp_path),
                         "branch": "feature", "expected_head_sha": "abc"}}
    return worker, units, call, calls, payload, finish


def outcome_count():
    with cdb.get_db_session() as db:
        return db.query(cdb.RoutingDecision).filter_by(task_class="provider_outcome").count()


def test_outcome_commit_failure_retains_marker_after_quota(lab, monkeypatch, caplog):
    record_outcome({"ok": True, "exit_code": 0, "state": "completed"})
    session_factory = cdb.SessionLocal

    def session():
        db = session_factory()
        commit = db.commit

        def fail_update():
            if any(r.task_class == "provider_outcome" and r.status != "launching"
                   for r in list(db.dirty) + list(db.new)):
                raise OSError("disk full")
            commit()

        db.commit = fail_update
        return db

    monkeypatch.setattr(cdb, "SessionLocal", session)
    assert LIMIT in router.execute_codex("review")["error"]
    assert router.execute_codex("retry").get("executed") is False
    assert "provider outcome update failed; launch marker retained" in caplog.text
    health = router.provider_allows_dispatch("codex")
    assert not health["allowed"] and "launch outcome not recorded" in health["reason"]
    with cdb.get_db_session() as db:
        assert db.query(cdb.RoutingDecision).filter_by(status="launching").count() == 1
    assert lab[2].read_text().splitlines() == ["call"]


def test_killed_runner_blocks_until_grace_then_single_attempt(lab):
    import subprocess
    lab[1]("", success=True)
    with cdb.get_db_session() as db:
        database_url = str(db.bind.url)
    script = f"""
import os
from datetime import datetime
from src import estate_router as r
class Clock(datetime):
    @classmethod
    def now(cls, tz=None):
        return datetime.fromisoformat({NOW.isoformat()!r})
r.datetime = Clock
r._codex_available = lambda: (True, {str(lab[2].with_name('codex'))!r})
r.resolve_latest_codex_model = lambda _: 'gpt-6.1-sol'
r.subscription_effort = lambda: 'high'
r._execute_codex_with_sandbox('review', sandbox='read-only', provider='codex',
    timeout=180, on_started=lambda _: os._exit(23))
"""
    child = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True,
        env={**os.environ, "DATABASE_URL": database_url}, timeout=30)
    assert child.returncode == 23, child.stderr
    # This controller reads the durable marker left by the dead runner.
    lab[0].current = NOW + timedelta(seconds=180, minutes=15) - timedelta(microseconds=1)
    assert not router.execute_codex("retry")["executed"]
    lab[0].current += timedelta(microseconds=1)
    health = router.provider_allows_dispatch("codex")
    assert health["state"] == "unknown" and health["allowed"]
    # Leave the new attempt unfinished: expiry admits exactly one observer.
    first = router.provider_allows_dispatch("codex", launch_timeout=180)
    assert first["allowed"] and first["outcome_id"]
    assert not router.execute_codex("second retry")["executed"]
    assert outcome_count() == 2


def test_intent_commit_failure_refuses_launch(lab, monkeypatch):
    record_outcome({"ok": True, "exit_code": 0, "state": "completed"})
    session_factory = cdb.SessionLocal

    def session():
        db = session_factory()
        commit = db.commit

        def fail_insert():
            if db.new:
                raise OSError("disk full")
            commit()

        db.commit = fail_insert
        return db

    monkeypatch.setattr(cdb, "SessionLocal", session)
    monkeypatch.setattr(router, "_codex_available", lambda: pytest.fail("Codex setup invoked"))
    result = router.execute_codex("review")
    assert not result["ok"] and result["executed"] is False
    assert "launch intent not committed" in result["error"]
    assert not lab[2].exists() and outcome_count() == 1


@pytest.mark.parametrize("success", [True, False])
def test_final_result_updates_same_row_and_fresh_marker_blocks(lab, success):
    lab[1]("" if success else LIMIT, success=success)
    observed = []

    def started(_):
        with cdb.get_db_session() as db:
            row = db.query(cdb.RoutingDecision).filter_by(task_class="provider_outcome").one()
            observed.append(row.id)
            health = json.loads(row.escalation_reason)["provider_health"]
            assert health["state"] == "launching" and health["launched_at"] == NOW.isoformat()
        assert not router.execute_codex("concurrent")["executed"]

    result = router._execute_codex_with_sandbox("review", sandbox="read-only",
        provider="codex", on_started=started)
    assert result["ok"] == success
    with cdb.get_db_session() as db:
        row = db.query(cdb.RoutingDecision).filter_by(task_class="provider_outcome").one()
        assert row.id == observed[0] and row.status == ("complete" if success else "failed")
    health = router.provider_allows_dispatch("codex")
    assert health["state"] == ("ok" if success else "quota_exhausted")
    assert health["allowed"] == success
    if not success:
        lab[0].current = NOW.replace(hour=17, minute=38)
        assert not router.provider_allows_dispatch("codex")["allowed"]
        lab[0].current += timedelta(minutes=1)
        assert router.provider_allows_dispatch("codex")["allowed"]
    assert lab[2].read_text().splitlines() == ["call"]


def test_simultaneous_admissions_reserve_only_one_attempt(lab):
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=2) as pool:
        claims = list(pool.map(lambda _: router.provider_allows_dispatch(
            "codex", launch_timeout=180), range(2)))
    assert sum(claim["allowed"] for claim in claims) == 1
    assert outcome_count() == 1


@pytest.mark.parametrize("result,state", [
    ({"ok": True, "error": LIMIT, "exit_code": 1}, "quota_exhausted"),
    ({"ok": True, "exit_code": 1}, "unknown"),
    ({"ok": True, "exit_code": 0, "output": LIMIT}, "quota_exhausted"),
    ({"ok": True, "exit_code": 0, "error": "401 Unauthorized"}, "auth_failed"),
    ({"ok": True, "exit_code": 0, "stderr": "connection failed"}, "unreachable"),
    ({"ok": True, "exit_code": 0, "state": "completed", "output": "done"}, "ok"),
    ({"ok": True, "exit_code": 0}, "unknown"),
    ({"ok": True, "state": "completed"}, "unknown"),
])
def test_failure_first_fresh_and_recorded_outcomes(lab, result, state):
    assert router._provider_outcome(result)["state"] == state
    intent = router.provider_allows_dispatch("codex", launch_timeout=180)["outcome_id"]
    router._record_provider_outcome({**result, "provider_health": {"state": "ok"}}, intent)
    health = router.provider_allows_dispatch("codex")
    assert health["state"] == state and health["allowed"] == (state == "ok")


def test_quota_beyond_clip_limit_keeps_authoritative_reset(lab):
    # Persistence used to retain the early connection token and clip quota.
    lab[1]("connection recovered " + "x" * 3000 + LIMIT, stream="stdout", success=False)  # a real limit exits non-zero
    run()
    health = router.provider_allows_dispatch("codex")
    assert health["state"] == "quota_exhausted"
    assert health["retry_after"] == "2026-11-05T17:39:00+00:00"
    lab[0].current = NOW + timedelta(minutes=16)
    assert not router.provider_allows_dispatch("codex")["allowed"]


@pytest.mark.parametrize("terminal", [{}, {"state": "completed"}])
def test_incoming_truncated_success_stays_unknown(lab, terminal):
    intent = router.provider_allows_dispatch("codex", launch_timeout=180)["outcome_id"]
    router._record_provider_outcome({"ok": True, "exit_code": 0, "output": "done",
                                   "evidence_truncated": True, **terminal}, intent)
    health = router.provider_allows_dispatch("codex")
    assert health["state"] == "unknown" and not health["allowed"]


def test_refused_retry_preserves_reset_at_1216(lab):
    run()  # provider reports exhaustion until 17:39 at 12:00
    lab[0].current = NOW + timedelta(minutes=1)
    assert not run()["executed"]
    lab[0].current = NOW + timedelta(minutes=16)
    health = router.provider_allows_dispatch("codex")
    assert health["state"] == "quota_exhausted" and not health["allowed"]
    assert health["retry_after"] == "2026-11-05T17:39:00+00:00"
    assert outcome_count() == 1


def test_failure_first_property_table():
    for ok, code, error, quota, terminal in product(
            (False, True), (0, 1), ("", "tool exception"), ("", LIMIT), ("succeeded", "failed")):
        result = {"ok": ok, "exit_code": code, "error": error, "output": quota, "state": terminal}
        state = router._provider_outcome(result)["state"]
        # Structural success (ok, exit 0, no error, accepted state) is ok whatever text the transcript holds; any other
        # run is explained by its text, so quota text in a failed run still wins.
        assert (state == "ok") == (ok and code == 0 and not error and terminal == "succeeded"), result
        if not (ok and code == 0 and not error and terminal == "succeeded") and quota:
            assert state == "quota_exhausted", result


def test_reader_trusts_stored_health_without_reclassifying(lab, monkeypatch):
    key = record_outcome({"ok": False, "error": LIMIT})
    with cdb.get_db_session() as db:
        row = db.get(cdb.RoutingDecision, key)
        row.created_at = NOW.replace(tzinfo=None) - timedelta(days=30)
        row.escalation_reason = row.escalation_reason[:-1] + ' ,"provider_result":{"ok":true}}'
    def no_reclassification(*args, **kwargs):
        pytest.fail("reader reclassified an old outcome")
    monkeypatch.setattr(router, "_provider_outcome", no_reclassification)
    lab[0].current = NOW + timedelta(minutes=16)
    health = router.provider_allows_dispatch("codex")
    assert health["state"] == "quota_exhausted" and not health["allowed"]
    assert health["retry_after"] == "2026-11-05T17:39:00+00:00"


@pytest.mark.parametrize("unreadable", [False, True])
def test_worker_execute_refuses_exhausted_or_unreadable(lab, worker_lane, unreadable):
    decision = record_outcome({"ok": False, "error": LIMIT})
    if unreadable:
        with cdb.get_db_session() as db:
            db.get(cdb.RoutingDecision, decision).escalation_reason = "broken"
    lab[1]("", success=True)
    result = worker_lane[2]("test-lab", "execute", {
        "kind": "codex-readonly", "objective": "review"})["result"]
    assert not result["ok"] and result["executed"] is False
    assert "provider codex: " + ("unknown" if unreadable else "quota_exhausted") in result["error"]
    assert not lab[2].exists()


def test_spooled_runner_rechecks_health_after_start(lab, worker_lane):
    worker, units, call, _, payload, finish = worker_lane
    # Start has already been claimed, but the detached runner has not run yet.
    units.write_spool(payload["execution_id"], request=payload)
    record_outcome({"ok": False, "error": LIMIT})
    lab[1]("", success=True)
    units.enter("aoteru-run-spooled.service")
    assert worker._run_spooled("spooled") == 0
    result = worker._json_read(worker._SPOOL_ROOT / "spooled" / "result.json")
    assert not result["ok"] and "provider codex: quota_exhausted" in result["error"]
    assert not lab[2].exists()


def test_crash_recovery_refuses_then_recovers_after_reset(lab, worker_lane, monkeypatch):
    worker, units, call, calls, payload, finish = worker_lane

    class Crash(Exception):
        pass

    def crash(_):
        raise Crash("controller crashed before start")

    with monkeypatch.context() as patch:
        patch.setattr(write_lane, "_dispatch_start", crash)
        with pytest.raises(Crash):
            write_lane.execute_write_via_worker("change", repo_id="odysseus", host_id="test-lab")
    with cdb.get_db_session() as db:
        row = db.query(cdb.EstateExecution).one()
        execution_id = row.id
        assert row.lifecycle_state == "accepted"
    assert "start" not in calls
    record_outcome({"ok": False, "error": LIMIT})  # another execution exhausts Codex before restart
    lab[1]("", success=True)
    assert call("test-lab", "status", {"execution_id": execution_id})["result"]["state"] == "unknown"
    with cdb.get_db_session() as db:
        write_lane.reconcile_stale_estate_executions(db, cdb.EstateExecution)
    write_lane._apply_view(execution_id, finish(execution_id))
    row = write_lane._load_row(execution_id)
    assert calls.count("start") == 1 and row.lifecycle_state == "failed"
    assert "provider codex: quota_exhausted" in json.loads(row.result_json)["error"]
    assert not lab[2].exists()
    # Preserve the existing recovery/lease gates before trying a new write.
    recovered = write_lane.recover_execution_lease(execution_id, lease_id="L1", host_id="test-lab",
        repo_id="odysseus", branch="feature", worktree_path=payload["lease"]["worktree_path"])
    assert recovered["recovered"], recovered
    lab[0].current = NOW + timedelta(hours=6)
    assert router.provider_allows_dispatch("codex")["allowed"]
    assert run()["execution"]["ok"]  # valid ok observation, not just cooldown expiry
    assert router.provider_allows_dispatch("codex")["state"] == "ok"
    with cdb.get_db_session() as db:
        db.add(cdb.ParkLease(id="L2", repo_id="odysseus", host_id="test-lab", status="active",
                            worktree_path=payload["lease"]["worktree_path"], branch="feature"))
    retry = write_lane.execute_write_via_worker("change", repo_id="odysseus", host_id="test-lab")
    assert retry["lifecycle_state"] == "succeeded", retry
    assert lab[2].read_text().splitlines() == ["call", "call"]


@pytest.mark.parametrize("kind", ["codex", "codex-readonly", "codex-write", "durable-write",
                                 "routed-read", "routed-write", "shared-read", "shared-write"])
def test_all_paid_launch_paths_refuse_exhaustion(lab, worker_lane, kind):
    record_outcome({"ok": False, "error": LIMIT})
    lab[1]("", success=True)
    worker, units, call, _, payload, finish = worker_lane
    if kind == "codex":
        result = router.execute_codex("review")
    elif kind == "codex-readonly":
        result = call("test-lab", "execute", {"kind": kind, "objective": "review"})["result"]
    elif kind == "codex-write":
        call("test-lab", "start", payload)
        result = finish(payload["execution_id"])["result"]
    elif kind == "durable-write":
        result = router.execute_codex_write_durable("change", repo_id="odysseus", host_id="test-lab")["result"]
    elif kind.startswith("routed-"):
        response = router.run_task({**TASK, "repo": "odysseus", "routing": {
            "allow_paid_escalation": True, "mode": "implementation" if kind.endswith("write") else "advisory"}})
        result = response.get("execution") or {"ok": False, "error": response.get("execution_error")}
        if kind.endswith("write") and "result" in result:
            result = result["result"]
    else:
        result = router._execute_codex_with_sandbox("change", provider="codex",
            sandbox="workspace-write" if kind.endswith("write") else "read-only")
    assert not result["ok"] and "provider codex: quota_exhausted" in result["error"]
    assert not lab[2].exists()
    assert outcome_count() == 1


def test_launch_requires_explicit_authoritative_database(lab, monkeypatch):
    lab[1]("", success=True)
    monkeypatch.delenv("DATABASE_URL")
    result = router.execute_codex("review")
    assert not result["ok"] and "provider codex: unknown: authoritative DATABASE_URL required" in result["error"]
    assert not lab[2].exists()
    assert outcome_count() == 0


def test_separate_executor_process_reads_authoritative_health(lab):
    import subprocess
    record_outcome({"ok": False, "error": LIMIT})
    lab[1]("", success=True)
    with cdb.get_db_session() as db:
        database_url = str(db.bind.url)
    script = f"""
import json
from datetime import datetime
from src import estate_router as r
class Clock(datetime):
    @classmethod
    def now(cls, tz=None):
        now = datetime.fromisoformat({NOW.isoformat()!r})
        return now.astimezone(tz) if tz else now.replace(tzinfo=None)
r.datetime = Clock
r._codex_available = lambda: (True, {str(lab[2].with_name('codex'))!r})
r.resolve_latest_codex_model = lambda _: 'gpt-6.1-sol'
print(json.dumps(r.execute_codex('review')))
"""
    child = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True,
                           env={**os.environ, "DATABASE_URL": database_url}, timeout=30, check=True)
    result = json.loads(child.stdout.splitlines()[-1])
    assert not result["ok"] and "provider codex: quota_exhausted" in result["error"]
    assert not lab[2].exists()


def test_clean_success_is_ok_whatever_its_transcript_quotes():
    quoted = "\n".join(["from x import y  # noqa: F401", "timeout = 30", "retry the network connection on timeout; DNS unreachable?",
                        "ERROR: You've hit your usage limit. Please try again at 11:59 PM.", "error: 401 Unauthorized, failed twice"])
    ok = {"ok": True, "status": "succeeded", "exit_code": 0, "output": quoted, "stdout": quoted, "stderr": quoted}
    assert router._provider_outcome(ok) == {"state": "ok", "retry_after": None, "reason": "no provider error", "retry_after_assumed": False}


def test_a_failed_run_is_still_explained_by_its_whole_text_including_continuation_lines():
    stderr = "ERROR: You've hit your usage limit.\nPlease try again at 5:39 PM.\n" + "x" * 3000
    health = router._provider_outcome({"ok": False, "exit_code": 1, "error": "codex exec exited 1: " + stderr[:40], "stderr": stderr},
                                      now=datetime(2026, 11, 5, 12, 0, tzinfo=timezone.utc), host_tz=timezone.utc)
    assert health["state"] == "quota_exhausted" and health["retry_after"] == "2026-11-05T17:39:00+00:00"


def test_word_boundaries_stop_a_lint_code_reading_as_an_auth_failure():
    assert router._provider_outcome({"ok": False, "exit_code": 1, "stderr": "ruff: # noqa: F401 on line 3"})["state"] == "unknown"
    assert router._provider_outcome({"ok": False, "exit_code": 1, "stderr": "HTTP 401 from upstream"})["state"] == "auth_failed"
