"""Deterministic lead-persona routing (Aoteru routing contract v0.1)."""

import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes.misumi_routes import setup_misumi_routes
from services.memory.skills import SkillsManager
from src.misumi_persona_routing import load_personas, resolve_auto_lead

_PERSONAS = {
    "aoteru": {
        "role": "Emperor / Tower",
        "routing": {"intents": ["default", "standards", "coherence", "boundaries", "integration"]},
    },
    "erwin": {
        "role": "Deputy General",
        "routing": {"intents": ["priorities", "planning", "risk", "strategy", "recovery"]},
    },
    "misato": {
        "role": "Caretaker",
        "routing": {"intents": ["cleaning", "chores", "rota"]},
    },
    "sanji": {
        "role": "Chef",
        "routing": {"intents": ["food", "recipes", "meals", "shopping", "food stock"]},
    },
}


def _test_resolve(prompt: str) -> tuple[str, dict]:
    return resolve_auto_lead(prompt, _PERSONAS)


def test_keyword_match_routes_to_best_persona():
    persona, provenance = _test_resolve("Check the cleaning rota")
    assert persona == "misato"
    assert provenance["method"] == "routing-contract-v0.1"
    assert provenance["selected"] == "misato"
    assert sorted(provenance["reasons"]) == ["cleaning", "rota"]


def test_multiword_intent_matches_as_phrase():
    persona, provenance = _test_resolve("How much food stock is left?")
    assert persona == "sanji"
    assert "food stock" in provenance["reasons"]


def test_unmatched_request_falls_back_to_aoteru():
    persona, provenance = _test_resolve("Please help me think this through")
    assert persona == "aoteru"
    assert provenance["reasons"] == ["fallback:aoteru"]


def test_reserved_matters_stay_with_aoteru():
    persona, provenance = _test_resolve("Set a Level 5 food standard")
    assert persona == "aoteru"
    assert provenance["reasons"] == ["reserved:aoteru"]

    persona, provenance = _test_resolve("Review our household boundaries around food shopping")
    assert persona == "aoteru"
    assert provenance["reasons"] == ["reserved:aoteru"]


def test_manifest_order_breaks_score_ties():
    tied = {
        "erwin": {"routing": {"intents": ["review"]}},
        "lelouch": {"routing": {"intents": ["review", "workflow"]}},
    }
    persona, _ = resolve_auto_lead("Review this workflow", tied)
    # lelouch scores 2 vs erwin 1, so lelouch must win on score alone even
    # though erwin comes first in the manifest.
    assert persona == "lelouch"

    tied = {
        "erwin": {"routing": {"intents": ["review"]}},
        "lelouch": {"routing": {"intents": ["review"]}},
    }
    persona, _ = resolve_auto_lead("Review this", tied)
    assert persona == "erwin"


def test_missing_manifest_degrades_to_aoteru():
    persona, provenance = resolve_auto_lead("Check the cleaning rota", None)
    assert persona == "aoteru"
    assert provenance["reasons"] == ["fallback:aoteru"]


def test_load_personas_reads_seed_root(tmp_path: Path):
    config = tmp_path / "config" / "personas.yaml"
    config.parent.mkdir(parents=True)
    config.write_text(
        "version: '0.1'\npersonas:\n  aoteru:\n    role: Emperor / Tower\n"
        "    routing:\n      intents:\n        - default\n",
        encoding="utf-8",
    )
    personas = load_personas(str(tmp_path))
    assert personas is not None and "aoteru" in personas


def _household(tmp_path: Path) -> Path:
    root = tmp_path / "household-repo"
    (root / "docs" / "core").mkdir(parents=True)
    (root / "docs" / "core" / "misumi-seed-order-v0.1.md").write_text(
        "# Misumi Seed Order v0.1\n", encoding="utf-8"
    )
    (root / "config").mkdir()
    (root / "config" / "personas.yaml").write_text(
        "version: '0.1'\n"
        "personas:\n"
        "  aoteru:\n"
        "    role: Emperor / Tower\n"
        "    routing:\n"
        "      intents:\n"
        "        - default\n"
        "        - standards\n"
        "  erwin:\n"
        "    role: Deputy General\n"
        "    routing:\n"
        "      intents:\n"
        "        - planning\n"
        "        - risk\n"
        "  misato:\n"
        "    role: Caretaker\n"
        "    routing:\n"
        "      intents:\n"
        "        - cleaning\n"
        "        - rota\n"
        "  sanji:\n"
        "    role: Chef\n"
        "    routing:\n"
        "      intents:\n"
        "        - food\n"
        "        - meals\n",
        encoding="utf-8",
    )
    (root / "household" / "food").mkdir(parents=True)
    (root / "household" / "food" / "shopping-list.md").write_text(
        "# Shopping list\n- [ ] miso\n", encoding="utf-8"
    )
    return root


def _client(tmp_path, monkeypatch):
    root = _household(tmp_path)
    monkeypatch.setenv("MISUMI_HOUSEHOLD_ROOT", str(root))
    monkeypatch.setenv("MISUMI_SOURCE_ROOT", str(root))
    monkeypatch.setenv("MISUMI_EVENT_LOG", str(tmp_path / "events.jsonl"))
    app = FastAPI()
    app.include_router(setup_misumi_routes(SkillsManager(str(tmp_path / "data"))))
    return TestClient(app), tmp_path / "events.jsonl"


def test_respond_auto_routes_lead_persona(tmp_path, monkeypatch):
    client, event_log = _client(tmp_path, monkeypatch)
    body = client.post(
        "/misumi/respond", json={"prompt": "Check the cleaning rota", "persona": "auto"}
    ).json()
    assert body["persona"] == "misato"
    assert body["persona_source"] == "auto"
    assert body["routing"]["method"] == "routing-contract-v0.1"
    assert "cleaning" in body["routing"]["reasons"]

    record = json.loads(event_log.read_text(encoding="utf-8").splitlines()[-1])
    assert record["persona"] == "misato"
    assert record["persona_source"] == "auto"
    assert record["routing"]["selected"] == "misato"


def test_respond_auto_reserved_guard_keeps_aoteru(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)
    body = client.post(
        "/misumi/respond", json={"prompt": "Set a Level 5 food standard", "persona": "auto"}
    ).json()
    assert body["persona"] == "aoteru"
    assert body["persona_source"] == "auto"
    assert body["routing"]["reasons"] == ["reserved:aoteru"]


def test_respond_explicit_persona_is_not_rerouted(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)
    body = client.post(
        "/misumi/respond",
        json={"prompt": "what is on the shopping list?", "persona": "sanji"},
    ).json()
    assert body["persona"] == "sanji"
    assert body["persona_source"] == "requested"
    assert "routing" not in body


def test_respond_default_persona_counts_as_requested(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)
    body = client.post(
        "/misumi/respond", json={"prompt": "Explain runtime in plain language"}
    ).json()
    assert body["persona"] == "aoteru"
    assert body["persona_source"] == "requested"
    assert "routing" not in body
