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
    app.include_router(setup_misumi_routes(SkillsManager(str(data_root))))
    client = TestClient(app)
    client.data_root, client.household = data_root, household
    return client


@pytest.fixture()
def client(tmp_path, monkeypatch):
    return _client(tmp_path, monkeypatch)


def run(client, scenario, mode="guest", **extra):
    return client.post("/misumi/demo/run", json={"scenario_id": scenario, "mode": mode, **extra})


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
    assert body["shadow_proposal"] is None and body["offline_evaluations"] == [] and body["guest_safety"]["persisted"] is False
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
    events = [json.loads(line) for line in (client.data_root / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    event = events[-1]
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
    live = run(client, "food-stock", mode="developer").json()
    live.pop("phase_b_input")
    live["recorded_at"] = "2026-10-28T00:00:00Z"
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
    assert guest["shadow_proposal"] is None and guest["offline_evaluations"] == [] and guest["guest_safety"]["persisted"] is False
    assert live["observed"]["kind"] == "observed"                         # the recording itself is untouched by replaying it
    assert run(client, "music-simulated", execution="replay").status_code == 404  # no recording: never fabricated
    assert run(client, "food-stock", mode="developer", execution="replay", prompt="Something else").status_code == 404


# --- reset ----------------------------------------------------------------------------------------------------------------------------


def test_reset_clears_guest_state_and_refuses_a_non_guest_instance(client, tmp_path, monkeypatch):
    run(client, "music-simulated", mode="developer")
    assert "Kind of Blue" in run(client, "music-simulated", mode="developer", prompt="what's playing").json()["observed"]["text"]
    assert (client.data_root / "events.jsonl").is_file()
    result = client.post("/misumi/demo/reset").json()
    assert result["reset"] is True and result["events_cleared"] >= 2 and result["persisted_guest_state"] == "none"
    assert not (client.data_root / "events.jsonl").exists()
    after = run(client, "music-simulated", mode="developer", prompt="what's playing").json()["observed"]["text"]
    assert "Kind of Blue" not in after
    other = _client(tmp_path / "other", monkeypatch, guest=False) if (tmp_path / "other").mkdir() is None else None
    assert other.post("/misumi/demo/reset").status_code == 409


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
