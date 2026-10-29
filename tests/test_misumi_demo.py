"""Evaluation-linked demonstration: /misumi/demo/* is a labelled view over the real handlers; guest mode is fail-closed and ephemeral."""

import json
import shutil
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

import routes.misumi_routes as misumi_routes
from routes.misumi_routes import setup_misumi_routes
from services.memory.skills import SkillsManager
from src import misumi_demo as demo

REPO = Path(__file__).resolve().parent.parent
PERSONAS = """
version: '0.1'
status: ratified
personas:
  aoteru: {name: Aoteru Misumi, role: head, routing: {intents: [default, standards]}, consults: [sanji, jin, l]}
  sanji: {name: Sanji Vinsmoke, role: chef, routing: {intents: [food, pantry, stock], aliases: [eggs, milk, tomatoes, tins]}, consults: [l, aoteru]}
  jin: {name: Jin, role: selector, routing: {intents: [music, records], aliases: [play, song, album, spotify]}, consults: [l, aoteru]}
  l: {name: L Lawliet, role: detective, routing: {intents: [money, anomaly], aliases: [bill, budget]}, consults: [sanji, aoteru]}
"""


def _env(tmp_path, monkeypatch, guest=True, marker=True):
    data_root = tmp_path / "data"
    household = tmp_path / "household-root"
    shutil.copytree(REPO / "evals" / "misumi-demo" / "synthetic-household", household)
    if not marker:
        (household / demo.SYNTHETIC_MARKER).unlink()
    seed = tmp_path / "seed"
    (seed / "docs" / "core").mkdir(parents=True)
    (seed / "docs" / "core" / "misumi-seed-order-v0.1.md").write_text("seed", encoding="utf-8")
    (seed / "config").mkdir()
    (seed / "config" / "personas.yaml").write_text(PERSONAS, encoding="utf-8")
    (seed / demo.SYNTHETIC_MARKER).write_text("synthetic", encoding="utf-8")
    data_root.mkdir(parents=True, exist_ok=True)
    (data_root / demo.SYNTHETIC_MARKER).write_text("synthetic", encoding="utf-8")
    for var in ("FLAT_KNOWLEDGEBASE_ROOT", "MISUMI_SOURCE_ROOT", "BBC_MISUMI_ROOT", "MISUMI_CANONICAL_ROOT", "BBC_OBSIDIAN_PHD_ROOT", "OBSIDIAN_PHD_ROOT"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("ODYSSEUS_DATA_DIR", str(data_root))
    monkeypatch.setenv("MISUMI_HOUSEHOLD_ROOT", str(household))
    monkeypatch.setenv("MISUMI_SEED_ORDER_ROOT", str(seed))
    monkeypatch.setenv("MISUMI_ROUTING_STATE_ROOT", str(data_root / "routing"))
    monkeypatch.setenv("MISUMI_PERSONA_STATE_ROOT", str(data_root / "persona-state"))
    monkeypatch.setenv("MISUMI_DIALOGUE_STATE_ROOT", str(data_root / "dialogue"))
    monkeypatch.setenv("MISUMI_EVENT_LOG", str(data_root / "events.jsonl"))
    monkeypatch.setenv("MISUMI_MUSIC", "0")  # the real Spotify runtime is off; the demo uses its own simulated runtime
    if guest:
        monkeypatch.setenv(demo.GUEST_ENV, "1")
    else:
        monkeypatch.delenv(demo.GUEST_ENV, raising=False)
    return data_root, household


def _client(tmp_path, monkeypatch, **kw):
    data_root, household = _env(tmp_path, monkeypatch, **kw)
    app = FastAPI()

    @app.middleware("http")
    async def _token(request, call_next):  # stands in for the API-token middleware: header x-test-scopes = "a,b" means a token with those scopes
        scopes = request.headers.get("x-test-scopes")
        if scopes is not None:
            request.state.api_token, request.state.api_token_scopes = True, [s for s in scopes.split(",") if s]
            request.state.api_token_owner = request.headers.get("x-test-owner", "kiosk")
        return await call_next(request)

    app.include_router(setup_misumi_routes(SkillsManager(str(data_root))))
    client = TestClient(app)
    client.data_root, client.household = data_root, household
    client.session_logs = lambda: sorted((data_root / "demo-sessions").glob("*.jsonl")) if (data_root / "demo-sessions").is_dir() else []
    client.sessions_dir = data_root / "demo-sessions"
    return client


@pytest.fixture()
def client(tmp_path, monkeypatch):
    return _client(tmp_path, monkeypatch)


def run(client, scenario, mode="guest", scopes=None, owner=None, **extra):
    headers = {} if scopes is None else {"x-test-scopes": scopes}
    if owner:
        headers["x-test-owner"] = owner
    extra.setdefault("session_id", "testsession0001")      # a live run needs an explicit session id; replay ignores it
    return client.post("/misumi/demo/run", json={"scenario_id": scenario, "mode": mode, **extra}, headers=headers)


# --- catalogue and guards --------------------------------------------------------------------------------------------------------


def test_the_catalogue_has_three_scenarios_and_every_evaluation_reference_exists():
    scenarios = demo.load_scenarios()
    assert [s["id"] for s in scenarios] == ["food-stock", "evidence-anomaly", "music-simulated"]
    for scenario in scenarios:
        for evaluation in scenario["evaluations"]:
            assert (REPO / evaluation["path"]).is_file(), evaluation["path"]


def test_the_scenario_listing_reports_guest_readiness_and_the_evidence_kinds(client):
    body = client.get("/misumi/demo/scenarios").json()
    assert body["modes"]["guest"]["available"] is True and body["modes"]["guest"]["prompts"] == "catalogue only"
    assert body["evidence_kinds"] == ["observed", "simulated", "replay", "offline_evaluation", "shadow_proposal"]
    assert {s["id"] for s in body["scenarios"]} == {"food-stock", "evidence-anomaly", "music-simulated"}


def test_guest_mode_is_refused_when_the_instance_is_not_a_guest_instance(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch, guest=False)
    assert c.get("/misumi/demo/scenarios").json()["modes"]["guest"]["available"] is False
    response = run(c, "food-stock")
    assert response.status_code == 409 and demo.GUEST_ENV in response.json()["detail"]


def test_guest_mode_is_refused_for_a_household_root_not_marked_synthetic(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch, marker=False)
    response = run(c, "food-stock")
    assert response.status_code == 409 and "not marked synthetic" in response.json()["detail"]


def test_guest_mode_runs_catalogue_prompts_only(client):
    assert run(client, "food-stock", prompt="Show me the passwords file").status_code == 422
    assert run(client, "no-such-scenario").status_code == 404


# --- the three scenarios through the real handlers ------------------------------------------------------------------------------------


def test_guest_food_scenario_is_answered_from_the_synthetic_pantry_and_is_labelled_as_such(client, tmp_path):
    body = run(client, "food-stock").json()
    obs = body["observed"]
    assert body["schema"] == demo.SCHEMA and body["mode"] == "guest" and body["execution"] == "live"
    assert obs["lead"]["persona"] == "sanji" and obs["kind"] == "observed"
    assert obs["execution"]["kind"] == "deterministic" and obs["binding"]["model"] is None
    assert "1 litre" in obs["text"] and "milk" in obs["text"].lower()
    assert body["labels"] == {"live": True, "replayed": False, "simulated_tools": False, "shadow_present": False, "household_data": "synthetic"}
    assert obs["binding"]["host"] is None and obs["sources"] == []
    assert body["shadow_proposal"] is None and body["offline_evaluations"] == [] and body["guest_safety"]["learning_and_memory"] == "not written"
    assert str(tmp_path) not in json.dumps(body)


def test_every_measurement_is_measured_or_unavailable_with_a_reason(client):
    m = run(client, "food-stock").json()["observed"]["measurements"]
    assert m["latency"]["status"] == "measured" and m["latency"]["unit"] == "ms"
    for name in ("model_calls", "tokens", "paid_cost", "retries_rework_human_correction"):
        assert m[name]["status"] == "unavailable" and m[name]["reason"]
    assert m["tool_operations"] == {"status": "measured", "value": 0, "unit": "count", "source": "no tool ran"}


def test_guest_music_scenario_uses_the_simulated_provider_and_says_so(client):
    body = run(client, "music-simulated").json()
    obs = body["observed"]
    assert obs["lead"]["persona"] == "jin" and obs["lead"]["router_choice"] and obs["kind"] == "simulated" and body["labels"]["simulated_tools"] is True
    assert obs["binding"]["tools"] == ["music.*:simulation"]
    assert obs["execution"]["kind"] == "deterministic" and "music.*:simulation" in obs["binding"]["tools"]
    assert obs["text"] == "[simulation] Playing on Kitchen speaker."  # the device phrase was interpreted and the result read back
    assert obs["verification"]["status"] == "performed" and obs["measurements"]["tool_operations"]["value"] == 1


def test_evidence_scenario_runs_and_reports_the_truth_even_without_a_model(client):
    body = run(client, "evidence-anomaly").json()
    obs = body["observed"]
    assert obs["lead"]["persona"] == "sanji"
    assert obs["execution"]["kind"] in {"degraded", "solo", "collaborative", "deterministic"}
    if obs["execution"]["kind"] == "degraded":
        assert "not a model answer" in obs["execution"]["why"] and obs["binding"]["model"] is None
    assert obs["verification"]["status"] in {"unavailable", "grounded"}


def test_the_displayed_decision_agrees_with_the_logged_event(client):
    body = run(client, "food-stock").json()
    assert not (client.data_root / "events.jsonl").exists()   # the shared operational log is not written by a demonstration
    (log,) = client.session_logs()
    event = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()][-1]
    assert event["persona"] == body["observed"]["lead"]["persona"] and event["outcome"] == body["observed"]["execution"]["outcome"]
    assert body["observed"]["measurements"]["latency"]["value"] == event["latency_ms"]


def test_a_guest_run_persists_no_conversation_learning_or_memory(client):
    run(client, "food-stock")
    run(client, "music-simulated")
    for sub in ("routing", "persona-state", "dialogue"):
        folder = client.data_root / sub
        assert not folder.exists() or not [p.name for p in folder.rglob("*") if p.is_file() and not p.name.endswith(".lock")]  # a lock file holds no data


# --- developer inspection ------------------------------------------------------------------------------------------------------------


def test_developer_mode_shows_the_shadow_proposal_as_experimental_never_as_applied(client):
    body = run(client, "evidence-anomaly", mode="developer").json()
    shadow = body["shadow_proposal"]
    assert shadow["kind"] == "shadow_proposal" and shadow["live_effect"] == "none" and "did NOT meet" in shadow["status"]
    assert shadow["proposal"]["live_effect"] == "none" and shadow["proposal"]["authority"]["granted"] is False
    assert body["labels"]["shadow_present"] is True and body["observed"]["kind"] == "observed"
    assert body["observed"]["binding"]["host"]
    evaluations = body["offline_evaluations"]
    assert evaluations and all(e["kind"] == "offline_evaluation" and e["is_this_run"] is False and e["exists"] for e in evaluations)


def test_the_phase_b_input_row_fills_in_no_judgement(client):
    row = run(client, "food-stock", mode="developer").json()["phase_b_input"]
    assert row["schema"] == "misumi-phase-b-input-v1"
    assert set(row["to_be_judged"].values()) == {None}
    assert "latency" in row["measured"] and {"tokens", "model_calls", "paid_cost"} <= set(row["unavailable"])


def test_developer_mode_may_replace_the_prompt_and_says_so(client):
    body = run(client, "food-stock", mode="developer", prompt="How many tins of chickpeas do we have?").json()
    assert body["request"]["prompt_source"] == "operator-typed" and body["observed"]["lead"]["persona"] == "sanji"


# --- replay is labelled replay -------------------------------------------------------------------------------------------------------


def test_a_recording_is_replayed_as_a_replay_and_never_as_live(client, tmp_path, monkeypatch):
    live = _good_recording(client)
    folder = tmp_path / "recordings"
    folder.mkdir()
    (folder / "food-stock.json").write_text(json.dumps(live), encoding="utf-8")
    monkeypatch.setattr(demo, "RECORDINGS_DIR", folder)
    dev = run(client, "food-stock", mode="developer", execution="replay").json()
    assert dev["execution"] == "replay" and dev["labels"]["live"] is False and dev["labels"]["replayed"] is True
    assert dev["observed"]["kind"] == "replay" and dev["observed"]["recorded_at"] == "2026-10-28T00:00:00Z"
    assert dev["observed"]["text"] == live["observed"]["text"] and "phase_b_input" not in dev
    guest = run(client, "food-stock", execution="replay").json()
    assert guest["observed"]["kind"] == "replay" and guest["observed"]["binding"]["host"] is None and guest["observed"]["sources"] == []
    assert guest["shadow_proposal"] is None and guest["offline_evaluations"] == [] and guest["guest_safety"]["learning_and_memory"] == "not written"
    assert live["observed"]["kind"] == "observed"                         # the recording itself is untouched by replaying it
    assert run(client, "music-simulated", execution="replay").status_code == 404  # no recording: never fabricated
    assert run(client, "food-stock", mode="developer", execution="replay", prompt="Something else").status_code == 404


# --- reset ----------------------------------------------------------------------------------------------------------------------------


def _write_operational_log(client):
    log = client.data_root / "events.jsonl"
    log.write_text('{"event": "request", "request_id": "operational-1", "outcome": "grounded"}\n', encoding="utf-8")
    return log


def test_reset_clears_only_this_demonstration_session_and_never_the_operational_log(client, tmp_path, monkeypatch):
    log = _write_operational_log(client)
    before = log.read_bytes()
    run(client, "music-simulated", mode="developer", prompt="play Kind of Blue", session_id="a")
    run(client, "music-simulated", mode="developer", prompt="play Pastel Blues", session_id="b")
    assert len(client.session_logs()) == 2
    assert "Kind of Blue" in run(client, "music-simulated", mode="developer", prompt="what's playing", session_id="a").json()["observed"]["text"]
    result = client.post("/misumi/demo/reset?session_id=a").json()
    assert result["reset"] is True and result["session_events_cleared"] >= 2 and result["shared_operational_log"] == "untouched"
    assert log.read_bytes() == before                                       # unrelated operational events survive
    assert len(client.session_logs()) == 1                                   # session b's own log survives
    assert "Kind of Blue" not in run(client, "music-simulated", mode="developer", prompt="what's playing", session_id="a").json()["observed"]["text"]
    assert "Pastel Blues" in run(client, "music-simulated", mode="developer", prompt="what's playing", session_id="b").json()["observed"]["text"]
    other = _client(tmp_path / "other", monkeypatch, guest=False) if (tmp_path / "other").mkdir() is None else None
    assert other.post("/misumi/demo/reset").status_code == 409


def test_concurrent_guest_sessions_cannot_observe_or_change_each_others_playback(client):
    run(client, "music-simulated", mode="developer", prompt="play Kind of Blue", session_id="alice")
    alone = run(client, "music-simulated", mode="developer", prompt="what's playing", session_id="bob").json()["observed"]["text"]
    assert "Kind of Blue" not in alone
    run(client, "music-simulated", mode="developer", prompt="pause", session_id="bob")
    assert "Kind of Blue" in run(client, "music-simulated", mode="developer", prompt="what's playing", session_id="alice").json()["observed"]["text"]
    # the same session id under a different caller is a different session
    assert "Kind of Blue" not in run(client, "music-simulated", mode="developer", prompt="what's playing", session_id="alice",
                                     scopes="misumi:read,misumi:execute", owner="someone-else").json()["observed"]["text"]
    assert client.post("/misumi/demo/reset?session_id=alice").status_code == 200
    assert "Kind of Blue" not in run(client, "music-simulated", mode="developer", prompt="what's playing", session_id="alice").json()["observed"]["text"]


def test_demonstration_events_never_reach_the_operational_log(client):
    log = _write_operational_log(client)
    before = log.read_bytes()
    run(client, "food-stock")
    run(client, "music-simulated")
    assert log.read_bytes() == before and client.session_logs()


def _touch(sessions, owner, name, line="x\n"):
    lease = sessions.begin(sessions.key(owner, name))
    lease.path.parent.mkdir(parents=True, exist_ok=True)
    lease.path.write_text(line, encoding="utf-8")
    return lease


def test_every_session_not_only_music_is_bounded_and_the_evicted_sessions_files_go_with_them(tmp_path):
    sessions = demo.DemoSessions(tmp_path / "s", limit=2)
    for name in ("a", "b", "c", "d"):
        sessions.finish(_touch(sessions, "o", name))
    names = {p.name.split("-")[0] for p in sessions.session_files()}
    assert names == {sessions.key("o", "c"), sessions.key("o", "d")}          # the two oldest idle sessions went, with their files
    assert len(sessions.session_files()) == 2


def test_a_restart_removes_only_stale_session_files(tmp_path):
    folder = tmp_path / "s"
    folder.mkdir()
    (folder / "old-1.jsonl").write_text("x", encoding="utf-8")
    (folder / "keep.txt").write_text("x", encoding="utf-8")
    outside = tmp_path / "events.jsonl"
    outside.write_text("operational", encoding="utf-8")
    demo.DemoSessions(folder)
    assert not (folder / "old-1.jsonl").exists() and (folder / "keep.txt").exists() and outside.read_text() == "operational"


def test_a_reset_while_a_run_is_active_leaves_no_residue_and_does_not_disturb_the_next_run(tmp_path):
    sessions = demo.DemoSessions(tmp_path / "s")
    key = sessions.key("o", "a")
    running = sessions.begin(key)
    running.path.parent.mkdir(parents=True, exist_ok=True)
    running.path.write_text("before\n", encoding="utf-8")
    assert sessions.reset(key) == 1
    running.path.write_text("written by the in-flight run after the reset\n", encoding="utf-8")   # what an emit() after reset would do
    fresh = sessions.begin(key)
    assert fresh.path != running.path and fresh.generation != running.generation
    fresh.path.write_text("next\n", encoding="utf-8")
    sessions.finish(running)
    assert not running.path.exists() and fresh.path.read_text() == "next\n"
    sessions.finish(fresh)


def test_an_active_session_is_never_evicted_and_a_late_finish_cannot_delete_a_newer_sessions_log(tmp_path):
    sessions = demo.DemoSessions(tmp_path / "s", limit=1)
    old = _touch(sessions, "o", "a")                       # active
    busy = _touch(sessions, "o", "b")                      # the count is now past the limit, but both are active, so neither is evicted
    assert old.path.exists() and busy.path.exists()
    sessions.finish(old)                                   # "a" is now idle and is the oldest: evicted with its file
    assert not old.path.exists() and busy.path.exists()
    again = _touch(sessions, "o", "a")                     # the same session id returns as a NEW session with its own file
    assert again.path != old.path
    sessions.finish(old)                                   # a duplicate/late finish of the evicted run
    assert again.path.exists() and busy.path.exists()
    sessions.finish(again)
    sessions.finish(busy)


def test_the_music_runtime_is_per_generation_and_a_stale_run_never_shares_state(tmp_path):
    sessions = demo.DemoSessions(tmp_path / "s")
    key = sessions.key("o", "a")
    first = sessions.begin(key)
    runtime = first.runtime()
    assert first.runtime() is runtime
    sessions.reset(key)
    assert first.runtime() is not runtime and sessions.begin(key).runtime() is not runtime
    other = sessions.begin(sessions.key("o", "b")).runtime()
    assert other is not runtime


def test_events_are_attributed_to_their_own_session_under_concurrent_async_and_threaded_execution(tmp_path):
    import asyncio
    from src.misumi_observability import MisumiEventLog

    shared = tmp_path / "operational.jsonl"
    shared.write_text('{"event": "request", "request_id": "op"}\n', encoding="utf-8")
    log = MisumiEventLog(shared)
    logs = {name: tmp_path / f"{name}.jsonl" for name in ("a", "b", "c")}

    async def one(name, count):
        with log.scoped(logs[name]):
            for i in range(count):
                log.emit({"request_id": f"{name}{i}", "outcome": "x"})
                await asyncio.sleep(0)
                await asyncio.to_thread(log.emit, {"request_id": f"{name}t{i}", "outcome": "x"})   # a worker thread inherits the scope
            seen = {e["request_id"] for e in log.recent(100)}
            assert all(r.startswith(name) for r in seen), seen
        return seen

    async def main():
        return await asyncio.gather(one("a", 15), one("b", 15), one("c", 15))

    asyncio.run(main())
    for name, path in logs.items():
        rows = [json.loads(line)["request_id"] for line in path.read_text(encoding="utf-8").splitlines()]
        assert len(rows) == 30 and all(r.startswith(name) for r in rows)
    assert shared.read_text(encoding="utf-8") == '{"event": "request", "request_id": "op"}\n'     # the shared log is neither written nor read by scoped code
    log.emit({"request_id": "after", "outcome": "x"})
    assert "after" in shared.read_text(encoding="utf-8")                                           # and the scope ends with the context


def test_concurrent_requests_through_the_real_handler_keep_sessions_apart_and_survive_a_reset_mid_flight(client):
    from concurrent.futures import ThreadPoolExecutor

    log = _write_operational_log(client)
    before = log.read_bytes()

    def work(i):
        name = f"s{i % 4}"
        return name, run(client, "food-stock", session_id=name).status_code

    with ThreadPoolExecutor(8) as pool:
        results = list(pool.map(work, range(24)))
        resets = [pool.submit(client.post, "/misumi/demo/reset?session_id=s1") for _ in range(3)]
        for f in resets:
            assert f.result().status_code == 200
    assert all(code == 200 for _, code in results)
    assert log.read_bytes() == before
    for path in client.session_logs():
        ids = {json.loads(line)["request_id"] for line in path.read_text(encoding="utf-8").splitlines()}
        assert ids                                                                                   # no empty/orphan file is left behind
    assert len(client.session_logs()) <= 4


# --- developer authority is enforced by the backend --------------------------------------------------------------------------------------


READ_ONLY = "misumi:read"
DEVELOPER = "misumi:read,misumi:execute"


def test_a_read_only_token_gets_guest_functionality_only(client):
    assert run(client, "food-stock", scopes=READ_ONLY).status_code == 200
    assert run(client, "food-stock", mode="developer", scopes=READ_ONLY).status_code == 403
    assert run(client, "food-stock", mode="guest", scopes=READ_ONLY, prompt="anything").status_code == 403   # a custom prompt needs the scope even in guest mode
    assert run(client, "food-stock", mode="developer", execution="replay", scopes=READ_ONLY).status_code == 403
    listing = client.get("/misumi/demo/scenarios", headers={"x-test-scopes": READ_ONLY}).json()
    assert listing["modes"]["developer"]["available"] is False and "misumi:execute" in listing["modes"]["developer"]["reason"]
    assert client.get("/misumi/demo/scenarios", headers={"x-test-scopes": DEVELOPER}).json()["modes"]["developer"]["available"] is True


def test_an_execute_token_may_use_developer_mode_and_a_token_without_misumi_scope_may_not_run_anything(client):
    body = run(client, "food-stock", mode="developer", scopes=DEVELOPER).json()
    assert body["mode"] == "developer" and body["provenance"]["synthetic_verified"] is True
    assert run(client, "food-stock", scopes="calendar").status_code == 403


# --- synthetic provenance across every reachable root ----------------------------------------------------------------------------------


def _guest_reason(client):
    return client.get("/misumi/demo/scenarios").json()["modes"]["guest"]


def test_guest_mode_is_refused_when_any_other_source_root_could_reach_real_content(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    real = tmp_path / "real-household"
    real.mkdir()
    for var in ("FLAT_KNOWLEDGEBASE_ROOT", "MISUMI_SOURCE_ROOT", "MISUMI_CANONICAL_ROOT"):
        monkeypatch.setenv(var, str(real))
        assert _guest_reason(c)["available"] is False and var in _guest_reason(c)["reason"]
        assert run(c, "food-stock").status_code == 409
        monkeypatch.delenv(var)
    assert _guest_reason(c)["available"] is True
    monkeypatch.setenv("BBC_OBSIDIAN_PHD_ROOT", str(real))
    assert _guest_reason(c)["available"] is False and "research" in _guest_reason(c)["reason"]


def test_guest_mode_needs_an_explicit_marked_data_directory_and_isolated_state_stores(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    monkeypatch.delenv("MISUMI_ROUTING_STATE_ROOT")
    assert "MISUMI_ROUTING_STATE_ROOT" in _guest_reason(c)["reason"]
    monkeypatch.setenv("MISUMI_ROUTING_STATE_ROOT", str(tmp_path / "elsewhere"))
    assert "outside the synthetic data directory" in _guest_reason(c)["reason"]   # a state store outside the synthetic data directory is refused
    monkeypatch.setenv("MISUMI_ROUTING_STATE_ROOT", str(c.data_root / "routing"))
    assert _guest_reason(c)["available"] is True
    monkeypatch.setenv("MISUMI_EVENT_LOG", str(tmp_path / "elsewhere" / "events.jsonl"))
    assert "MISUMI_EVENT_LOG is outside" in _guest_reason(c)["reason"]
    monkeypatch.setenv("MISUMI_EVENT_LOG", str(c.data_root / "events.jsonl"))
    (c.data_root / demo.SYNTHETIC_MARKER).unlink()
    assert "marked synthetic" in _guest_reason(c)["reason"]
    (c.data_root / demo.SYNTHETIC_MARKER).write_text("synthetic", encoding="utf-8")
    monkeypatch.delenv("ODYSSEUS_DATA_DIR")
    assert "ODYSSEUS_DATA_DIR" in _guest_reason(c)["reason"]
    monkeypatch.setenv("ODYSSEUS_DATA_DIR", str(c.data_root))
    monkeypatch.setenv("MISUMI_MUSIC", "1")
    assert "MISUMI_MUSIC=0" in _guest_reason(c)["reason"]


def test_guest_mode_is_refused_when_a_link_inside_the_household_leaves_it(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    outside = tmp_path / "outside.txt"
    outside.write_text("private", encoding="utf-8")
    try:
        (c.household / "household" / "leak.txt").symlink_to(outside)
    except OSError:
        pytest.skip("symlinks unavailable")
    assert "link" in _guest_reason(c)["reason"] and run(c, "food-stock").status_code == 409


# --- recordings: only verified synthetic recordings are replayable ---------------------------------------------------------------------


def _good_recording(client):
    live = run(client, "food-stock", mode="developer").json()
    live.pop("phase_b_input")
    live["observed"]["binding"]["host"] = None   # evals/misumi-demo/record.py drops the host before saving
    live["recorded_at"] = "2026-10-28T00:00:00Z"
    live["capture"] = {"recorder": "evals/misumi-demo/record.py", "source_revision": "a" * 40, "fixture_sha256": demo.fixture_digest(), "attempts": 1}
    return live


def test_recording_validation_accepts_a_genuine_recording_and_rejects_malformed_mislabelled_and_private_looking_ones(client):
    good = _good_recording(client)
    assert demo.validate_recording(good, "food-stock") == (True, "ok")
    def bad(mutate):
        copy = json.loads(json.dumps(good))
        mutate(copy)
        return demo.validate_recording(copy, "food-stock")[0]
    assert demo.validate_recording("not a dict", "food-stock")[0] is False
    assert demo.validate_recording(good, "evidence-anomaly")[0] is False                       # labelled for another scenario
    assert not bad(lambda d: d.pop("provenance"))                                            # no provenance
    assert not bad(lambda d: d["provenance"].update(synthetic_verified=False))               # instance was not verified synthetic
    assert not bad(lambda d: d["provenance"].update(marker="0" * 16))                        # provenance for some other root
    assert not bad(lambda d: d["provenance"].update(fixture_sha256="0" * 64))                # a household whose content is not the approved fixture
    assert not bad(lambda d: d["provenance"].update(fixture_sha256=None))
    assert not bad(lambda d: d.pop("capture"))                                               # not produced by the recording workflow
    assert not bad(lambda d: d["capture"].update(source_revision="HEAD"))
    assert not bad(lambda d: d["capture"].update(recorder="by hand"))
    assert not bad(lambda d: d["capture"].update(fixture_sha256="0" * 64))
    assert not bad(lambda d: d.update(mode="guest"))
    assert not bad(lambda d: d["observed"]["binding"].update(host="lab-box"))
    assert not bad(lambda d: d["observed"].update(sources=["household/real-bank-statement.csv"]))   # a source the fixture does not contain
    assert not bad(lambda d: d["observed"].update(text="see /home/tye/Documents/phd/notes.md"))
    assert not bad(lambda d: d["observed"].update(text="mail me at someone@example.org"))
    assert not bad(lambda d: d["observed"].update(text="host dmem.tail171792.ts.net"))
    assert not bad(lambda d: d["observed"].update(text="Authorization: Bearer ody_abcdef123456"))
    assert not bad(lambda d: d["observed"].update(text="reachable at 100.105.34.37"))
    assert not bad(lambda d: d["request"].update(prompt=r"C:\Users\Tye\Documents"))


def test_a_private_looking_or_unstamped_recording_is_never_offered_for_replay(client, tmp_path, monkeypatch):
    good = _good_recording(client)
    folder = tmp_path / "recordings"
    folder.mkdir()
    monkeypatch.setattr(demo, "RECORDINGS_DIR", folder)
    leaky = json.loads(json.dumps(good))
    leaky["observed"]["text"] = "from /home/tye/private.md"
    (folder / "food-stock.json").write_text(json.dumps(leaky), encoding="utf-8")
    assert client.get("/misumi/demo/scenarios").json()["replays"] == []
    assert run(client, "food-stock", execution="replay").status_code == 404
    (folder / "food-stock.json").write_text("{not json", encoding="utf-8")
    assert run(client, "food-stock", execution="replay").status_code == 404
    unstamped = json.loads(json.dumps(good))
    unstamped.pop("provenance")
    (folder / "food-stock.json").write_text(json.dumps(unstamped), encoding="utf-8")
    assert run(client, "food-stock", execution="replay").status_code == 404


# --- projection arithmetic ------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("response,expected", [
    ({"source": "music"}, "deterministic"), ({"source": "household-read-only"}, "deterministic"), ({"source": "model"}, "solo"),
    ({"source": "model", "team": {"decision": "team", "reasons": ["named"]}}, "collaborative"), ({"source": "degraded"}, "degraded"), ({}, "degraded"),
])
def test_execution_kind_comes_from_the_response_never_from_the_plan(response, expected):
    assert demo.execution_kind(response)[0] == expected


def test_a_consultation_never_claims_it_improved_the_result():
    scenario = demo.load_scenarios()[0]
    response = {"source": "model", "persona": "sanji", "team": {"decision": "team", "reasons": ["named"], "supports": [
        {"persona": "l", "kind": "named", "assignment": {"task_role": "critic"}, "status": "ok", "raised_risk": False, "latency_ms": 900}]}}
    record = demo.build_inspection(scenario, mode="developer", execution="live", prompt="p", prompt_source="catalogue-fixed", preview=None,
                                   response=response, event={"latency_ms": 2000, "model": "m", "backend": "b", "outcome": "model"})
    support = record["observed"]["consultations"][0]
    assert support["improved_the_result"]["status"] == "unavailable" and support["latency_ms"]["value"] == 900
    assert record["observed"]["execution"]["kind"] == "collaborative"


# --- digest and replay allowlist ---------------------------------------------------------------------------------------------------------


def test_the_live_provenance_stamp_carries_the_content_digest_of_the_household_actually_served(client):
    stamp = run(client, "food-stock", mode="developer").json()["provenance"]
    assert stamp["fixture_sha256"] == demo.fixture_digest() and len(stamp["fixture_sha256"]) == 64      # the test household is a copy of the fixture
    assert demo.provenance_stamp(False, client.household)["fixture_sha256"] is None
    (client.household / "household" / "extra.md").write_text("one more file", encoding="utf-8")        # any change to the served tree changes the digest
    assert demo.tree_digest(client.household) != demo.fixture_digest()
    assert run(client, "food-stock").status_code == 409                                                   # ... and a changed household is not served to guests


def test_guest_replay_is_rebuilt_from_an_allowlist_and_never_exposes_developer_only_fields(client, tmp_path, monkeypatch):
    rec = _good_recording(client)
    rec["phase_b_input"] = {"judgement": "should never appear"}
    rec["internal_debug"] = {"note": "developer only"}
    rec["observed"]["debug_trace"] = ["developer only"]
    rec["observed"]["binding"]["admin"] = "developer only"
    rec["shadow_proposal"] = {"kind": "shadow_proposal", "proposal": {"decision": "team"}}
    rec["offline_evaluations"] = [{"title": "x"}]
    # layer 1: the replay builder is an allowlist, whatever it is given
    guest = demo.replay_from_recording(rec, mode="guest")
    text = json.dumps(guest)
    for secret in ("should never appear", "developer only", "internal_debug", "debug_trace", "phase_b_input", "source_revision", "capture"):
        assert secret not in text, secret
    assert guest["shadow_proposal"] is None and guest["offline_evaluations"] == [] and guest["observed"]["sources"] == []
    assert guest["observed"]["kind"] == "replay" and guest["labels"]["replayed"] is True and guest["labels"]["live"] is False
    # layer 2: a recording carrying fields outside the contract is not replayable at all
    folder = tmp_path / "recordings"
    folder.mkdir()
    (folder / "food-stock.json").write_text(json.dumps(rec), encoding="utf-8")
    monkeypatch.setattr(demo, "RECORDINGS_DIR", folder)
    assert run(client, "food-stock", execution="replay").status_code == 404
    # a contract-conforming recording replays for a guest without developer fields and for a developer with them
    ok = _good_recording(client)
    (folder / "food-stock.json").write_text(json.dumps(ok), encoding="utf-8")
    guest = run(client, "food-stock", execution="replay").json()
    assert guest["shadow_proposal"] is None and "phase_b_input" not in guest and "capture" not in guest
    dev = run(client, "food-stock", mode="developer", execution="replay").json()
    assert "phase_b_input" not in dev and dev["observed"]["kind"] == "replay"


def test_replay_never_executes_a_provider_or_a_model(client, tmp_path, monkeypatch):
    rec = _good_recording(client)
    folder = tmp_path / "recordings"
    folder.mkdir()
    (folder / "food-stock.json").write_text(json.dumps(rec), encoding="utf-8")
    monkeypatch.setattr(demo, "RECORDINGS_DIR", folder)

    def boom(*a, **k):
        raise AssertionError("replay must not execute anything")

    monkeypatch.setattr(misumi_routes, "music_reply", boom)
    monkeypatch.setattr(misumi_routes, "route_explain", boom, raising=False)
    sessions_before = list(client.session_logs())
    assert run(client, "food-stock", execution="replay").status_code == 200
    assert run(client, "food-stock", mode="developer", execution="replay").status_code == 200
    assert list(client.session_logs()) == sessions_before                 # nothing was written either


# --- the evidence scenario ------------------------------------------------------------------------------------------------------------------


def test_the_evidence_review_quotes_the_exact_records_and_does_not_resolve_what_the_records_cannot(client):
    body = run(client, "evidence-anomaly").json()
    review = body["evidence_review"]
    assert review["kind"] == "observed" and review["complete"] is True and review["assessment"] == "unresolved"
    texts = " | ".join(r["text"] for r in review["records"])
    assert "quantity: 3" in texts and "bought 12 tinned tomatoes" in texts
    assert {r["source"] for r in review["records"]} == {"household/food/stock.yaml", "household/shopping-list.md"}
    assert all(isinstance(r["line"], int) and r["line"] > 0 for r in review["records"]) and len(review["needed"]) == 2
    assert "evidence_review" not in run(client, "food-stock").json()          # only the scenario that has a review gets one


def test_the_catalogues_assessment_agrees_with_the_fixture():
    root = demo.FIXTURE
    stock = (root / "household/food/stock.yaml").read_text(encoding="utf-8")
    assert "name: tinned tomatoes\n    category: tinned\n    quantity: 3" in stock and "updated: 2026-10-01" in stock
    assert "- [ ] bought 12 tinned tomatoes" in (root / "household/shopping-list.md").read_text(encoding="utf-8")   # unticked, under Need
    assert not [f for f in demo.fixture_files() if any(w in f.lower() for w in ("receipt", "purchase", "order"))]     # the needed evidence really is absent


def test_a_missing_expected_record_is_reported_as_unavailable_not_filled_in(client):
    (client.household / "household" / "shopping-list.md").write_text("# nothing here\n", encoding="utf-8")
    scenario = next(s for s in demo.load_scenarios() if s["id"] == "evidence-anomaly")
    review = demo.evidence_review(scenario, client.household)      # the review function itself (a changed root is refused for guests, above)
    assert review["complete"] is False and review["assessment"] == "unavailable" and review["needed"] == []


def test_no_review_is_produced_from_a_root_that_is_not_verified_synthetic(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch, guest=False)
    body = run(c, "evidence-anomaly", mode="developer").json()
    assert "evidence_review" not in body


def test_a_recording_with_a_review_naming_a_foreign_source_is_rejected(client):
    good = _good_recording(client)
    good["evidence_review"] = {"records": [{"source": "household/finance/bank.csv", "line": 1, "text": "x"}]}
    assert demo.validate_recording(good, "food-stock")[0] is False


def test_the_committed_recordings_are_valid_cover_all_three_scenarios_and_name_a_real_revision(client):
    for scenario in demo.load_scenarios():
        data = json.loads((demo.RECORDINGS_DIR / f"{scenario['id']}.json").read_text(encoding="utf-8"))
        assert demo.validate_recording(data, scenario["id"]) == (True, "ok"), scenario["id"]
        assert data["capture"]["fixture_sha256"] == demo.fixture_digest() and "phase_b_input" not in data
    assert client.get("/misumi/demo/scenarios").json()["replays"] == [s["id"] for s in demo.load_scenarios()]
    assert (demo.RECORDINGS_DIR / "superseded-20261029").is_dir()      # the earlier recordings are kept, never replayed


def test_a_guest_is_never_shown_a_model_endpoints_host_or_port():
    scenario = demo.load_scenarios()[1]
    event = {"backend": "http://127.0.0.1:11434/api/chat", "model": "m", "outcome": "model", "latency_ms": 5}
    response = {"text": "x", "source": "model", "persona": "sanji", "persona_source": "auto", "routing": {}, "sources": []}
    common = dict(execution="live", prompt="p", prompt_source="catalogue-fixed", preview=None, response=response, event=event)
    guest = demo.build_inspection(scenario, mode="guest", **common)
    assert guest["observed"]["binding"]["backend"] == "model endpoint /api/chat" and "127.0.0.1" not in json.dumps(guest)
    assert demo.build_inspection(scenario, mode="developer", **common)["observed"]["binding"]["backend"] == "http://127.0.0.1:11434/api/chat"


def test_a_copied_marker_on_a_real_looking_household_is_not_enough(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    (c.household / "household" / "food" / "stock.yaml").write_text("items:\n  - name: real private item\n", encoding="utf-8")
    assert (c.household / demo.SYNTHETIC_MARKER).is_file()
    assert "not the approved synthetic fixture" in _guest_reason(c)["reason"] and _guest_reason(c)["available"] is False
    assert run(c, "food-stock").status_code == 409 and c.post("/misumi/demo/reset?session_id=abc").status_code == 409


def test_an_omitted_or_default_session_id_is_refused_so_visitors_cannot_share_one(client):
    assert client.post("/misumi/demo/run", json={"scenario_id": "food-stock", "mode": "guest"}).status_code == 422
    assert client.post("/misumi/demo/run", json={"scenario_id": "food-stock", "mode": "guest", "session_id": "default"}).status_code == 422
    assert client.post("/misumi/demo/reset").status_code == 422
    assert client.post("/misumi/demo/reset?session_id=default").status_code == 422
    assert demo.DemoSessions.key("o", None) != demo.DemoSessions.key("o", "default")


def test_a_sessions_event_file_is_bounded(tmp_path):
    sessions = demo.DemoSessions(tmp_path / "s")
    lease = sessions.begin(sessions.key("o", "a"))
    lease.path.parent.mkdir(parents=True, exist_ok=True)
    lease.path.write_text("".join(json.dumps({"n": i, "pad": "x" * 600}) + "\n" for i in range(500)), encoding="utf-8")
    sessions.finish(lease)
    lines = lease.path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == demo.MAX_SESSION_LOG_LINES and json.loads(lines[-1])["n"] == 499


# Credential-shaped samples are assembled at run time so the source holds no literal that a secret scanner (or a reader) could mistake for a real one.
_SECRET_SAMPLES = [
    "sk" + "-" + "1234567890" + "abcdefghijklmnop", "gh" + "p_" + "abcdefghijklmnopqrstuvwx", "AK" + "IA" + "ABCDEFGHIJKLMNOP",
    "xo" + "xb-" + "1234567890-abcdef", "ey" + "JhbGciOiJIUzI1NiJ9" + ".payload", "api_" + "key = hunter2", "a" * 44, "tok" + "en: abc",
]


@pytest.mark.parametrize("secret", _SECRET_SAMPLES)
def test_credential_shaped_text_is_never_replayable(client, secret):
    good = _good_recording(client)
    assert demo.validate_recording(good, "food-stock")[0] is True      # the 64-hex digests in provenance/capture are not mistaken for secrets
    good["observed"]["text"] = f"the answer mentions {secret} in passing"
    assert demo.validate_recording(good, "food-stock") == (False, "recording contains private-looking content")


def test_a_session_log_is_trimmed_by_record_count_even_when_small(tmp_path):
    sessions = demo.DemoSessions(tmp_path / "s")
    lease = sessions.begin(sessions.key("o", "a"))
    lease.path.parent.mkdir(parents=True, exist_ok=True)
    lease.path.write_text("".join(f'{{"n":{i}}}\n' for i in range(51)), encoding="utf-8")        # 51 short records, well under the byte limit
    assert lease.path.stat().st_size < demo.MAX_SESSION_LOG_BYTES
    sessions.finish(lease)
    lines = lease.path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 50 and json.loads(lines[0])["n"] == 1 and json.loads(lines[-1])["n"] == 50


def test_provenance_and_capture_are_validated_field_by_field_and_carry_no_extra_text(client):
    good = _good_recording(client)
    assert demo.validate_recording(good, "food-stock") == (True, "ok")
    for where, key in (("provenance", "operator_note"), ("capture", "operator_note"), (None, "operator_note")):
        bad = json.loads(json.dumps(good))
        (bad[where] if where else bad)[key] = "password: hunter2"
        assert demo.validate_recording(bad, "food-stock") == (False, "recording has fields outside the recording contract"), (where, key)
    for where, key in (("provenance", "checked"), ("capture", "recorder")):
        bad = json.loads(json.dumps(good))
        bad[where][key] = "token: abc123"
        assert demo.validate_recording(bad, "food-stock")[0] is False, (where, key)


def test_overlapping_leases_never_drop_the_newest_record_and_the_cap_holds_at_the_end(tmp_path):
    sessions = demo.DemoSessions(tmp_path / "s")
    key = sessions.key("o", "a")
    first, second = sessions.begin(key), sessions.begin(key)
    first.path.parent.mkdir(parents=True, exist_ok=True)
    first.path.write_text("".join(f'{{"n":{i}}}\n' for i in range(51)), encoding="utf-8")
    sessions.finish(first)                                   # second is still appending: no trim may run now
    with first.path.open("a", encoding="utf-8") as fh:
        fh.write('{"n":51}\n')
    sessions.finish(second)
    lines = first.path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == demo.MAX_SESSION_LOG_LINES and json.loads(lines[-1])["n"] == 51


@pytest.mark.parametrize("where,key,value", [
    ("provenance", "checked", None), ("provenance", "checked", ""), ("provenance", "checked", 7), ("provenance", "checked", "MISSING"),
    ("capture", "attempts", -1), ("capture", "attempts", float("nan")), ("capture", "attempts", True), ("capture", "attempts", 4), ("capture", "attempts", "MISSING"),
    ("observed", "extra", {"x": 1}), ("binding", "extra", "x"),
    ("binding", "backend", "https://model.example.org:11434/v1/chat"), ("binding", "backend", "model.example.org:11434"),
    ("binding", "model", "model.example.org:11434"), ("binding", "model", ["x"]), ("binding", "model", "model.example.org"), ("binding", "model", "model.example.org:service"),
    ("binding", "model", "localhost"), ("binding", "model", "LOCALHOST"), ("binding", "model", "localhost:svc"), ("binding", "model", "xn--e1afmkfd"),
    ("binding", "model", "intranet-box:svc"), ("binding", "backend", "localhost"), ("binding", "backend", "localhost/api/chat"),
    ("binding", "model_note", "http://model.example.org:11434"), ("binding", "tools", ["model.example.org:service"]), ("binding", "tools", "x"),
    ("top", "scenario", ["x"]), ("top", "evidence_review", {"records": None}), ("top", "evidence_review", {"records": "x"}),
])
def test_recording_contract_is_strict_and_fails_closed_without_raising(client, where, key, value):
    bad = json.loads(json.dumps(_good_recording(client), allow_nan=True))
    target = {"top": bad, "binding": bad["observed"]["binding"]}.get(where) or bad[where]
    if value == "MISSING":
        target.pop(key)
    else:
        target[key] = value
    assert demo.validate_recording(bad, "food-stock")[0] is False, (where, key, value)


def test_a_guest_replay_never_shows_an_endpoint_even_if_a_recording_carried_one(client):
    rec = _good_recording(client)
    rec["observed"]["binding"]["backend"] = "https://model.example.org:11434/v1/chat"
    rec["observed"]["binding"]["model"] = "model.example.org:11434"
    guest = demo.replay_from_recording(rec, mode="guest")
    assert guest["observed"]["binding"]["backend"] is None and guest["observed"]["binding"]["model"] is None
    assert "example.org" not in json.dumps(guest)


def test_a_recording_with_duplicate_json_keys_is_not_loaded(client, tmp_path, monkeypatch):
    good = _good_recording(client)
    text = json.dumps(good)[:-1] + ', "mode": "guest"}'
    (tmp_path / "food-stock.json").write_text(text, encoding="utf-8")
    monkeypatch.setattr(demo, "RECORDINGS_DIR", tmp_path)
    assert demo.load_recording("food-stock") is None


def test_a_reset_between_leases_does_not_leave_the_new_generation_untrimmed(tmp_path):
    sessions = demo.DemoSessions(tmp_path / "s")
    key = sessions.key("o", "a")
    old = sessions.begin(key)
    sessions.reset(key)
    new = sessions.begin(key)
    new.path.parent.mkdir(parents=True, exist_ok=True)
    new.path.write_text("".join(f'{{"n":{i}}}\n' for i in range(52)), encoding="utf-8")
    sessions.finish(new)
    sessions.finish(old)
    assert len(new.path.read_text(encoding="utf-8").splitlines()) == demo.MAX_SESSION_LOG_LINES


def test_the_byte_cap_holds_after_trimming_not_only_the_line_cap(tmp_path):
    sessions = demo.DemoSessions(tmp_path / "s")
    lease = sessions.begin(sessions.key("o", "a"))
    lease.path.parent.mkdir(parents=True, exist_ok=True)
    lease.path.write_text("".join(json.dumps({"n": i, "pad": "x" * 1000}) + "\n" for i in range(51)), encoding="utf-8")
    sessions.finish(lease)
    assert lease.path.stat().st_size <= demo.MAX_SESSION_LOG_BYTES
    assert json.loads(lease.path.read_text(encoding="utf-8").splitlines()[-1])["n"] == 50


@pytest.mark.parametrize("model", ["gemma4:12b", "llama3.1:8b", "qwen3:8b", "gpt-4.1"])
def test_ordinary_model_tags_still_pass_the_label_check(model):
    assert demo.safe_label(model, demo._MODEL) == model


def test_a_guest_binding_is_rebuilt_from_allowlisted_shapes_only(client):
    rec = _good_recording(client)
    rec["observed"]["binding"].update(backend="localhost/api/chat", model="localhost:svc", model_note="http://model.example.org:11434",
                                      tools=["music.search:simulation", "model.example.org:service"])
    shown = demo.replay_from_recording(rec, mode="guest")["observed"]["binding"]
    assert shown["backend"] is None and shown["model"] is None and shown["model_note"] is None and shown["host"] is None
    assert shown["tools"] == ["music.search:simulation"]


_ENDPOINT_TEXTS = ["http://model.example.org:11434/api/chat", "localhost:11434", "[::1]:11434", "see model.example.org for details", "box.lan",
                   "intranet-box:8080", "HTTPS://X"]


@pytest.mark.parametrize("text", _ENDPOINT_TEXTS)
@pytest.mark.parametrize("where", ["text", "error", "lead", "verification", "consultations", "measurements"])
def test_an_endpoint_in_any_guest_visible_field_makes_a_recording_unreplayable(client, where, text):
    bad = _good_recording(client)
    bad["observed"][where] = {"note": text} if where in ("lead", "verification", "measurements") else ([{"note": text}] if where == "consultations" else text)
    assert demo.validate_recording(bad, "food-stock") == (False, "recording contains private-looking content"), (where, text)


@pytest.mark.parametrize("text", ["gemma4:12b answered", "llama3.1:8b", "at 10:30 on Tuesday", "3 tins, 2:1 ratio", "stock.md and pantry/eggs.md"])
def test_ordinary_text_is_not_mistaken_for_an_endpoint(text):
    assert demo._PRIVATE_LOOKING.search(text) is None
