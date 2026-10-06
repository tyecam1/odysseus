"""Experience-driven routing adaptation (application -07).

Covers: evidence immutability, candidate aggregation (correction vs temporary
vs durable, contradictions, repeated evidence), promotion gates, revisions and
rollback, restart persistence, learned-overlay application in the resolver
path, shadow evaluation, and the /misumi/respond integration flows.
"""

import json
import time
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes.misumi_routes import setup_misumi_routes
from services.memory.skills import SkillsManager
from src.misumi_persona_routing import resolve_auto_lead
from src.misumi_routing_adaptation import (
    RoutingAdaptationStore,
    extract_cue_term,
    keyword_variants,
    record_durable_instruction,
    record_manual_choice,
)

_SEED_YAML = (
    "version: '0.1'\n"
    "personas:\n"
    "  aoteru:\n"
    "    role: Emperor / Tower\n"
    "    routing:\n"
    "      intents:\n"
    "        - default\n"
    "  misato:\n"
    "    role: Caretaker\n"
    "    routing:\n"
    "      intents:\n"
    "        - cleaning\n"
    "        - rota\n"
    "        - chores\n"
    "  jin:\n"
    "    role: Selector\n"
    "    routing:\n"
    "      intents:\n"
    "        - music\n"
    "        - records\n"
    "  ginko:\n"
    "    role: Naturalist\n"
    "    routing:\n"
    "      intents:\n"
    "        - plants\n"
    "        - watering\n"
)


@pytest.fixture(autouse=True)
def _isolated_seed_root(tmp_path, monkeypatch):
    """Unit tests must not depend on any real knowledgebase on this machine."""
    root = tmp_path / "seed"
    (root / "docs" / "core").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "core" / "misumi-seed-order-v0.1.md").write_text("# Seed Order\n", encoding="utf-8")
    (root / "config").mkdir(exist_ok=True)
    (root / "config" / "personas.yaml").write_text(_SEED_YAML, encoding="utf-8")
    monkeypatch.setenv("MISUMI_SOURCE_ROOT", str(root))


def _store(tmp_path: Path) -> RoutingAdaptationStore:
    return RoutingAdaptationStore(tmp_path / "routing-state")


def _correction(store: RoutingAdaptationStore, **kw):
    return store.record_evidence(
        type="correction", cue=["cleaning"], previous_persona="misato",
        proposed_persona="jin", prompt="no, ask Jin about the cleaning", **kw
    )


# ---------- evidence ----------

def test_evidence_is_immutable_append(tmp_path: Path):
    store = _store(tmp_path)
    first = _correction(store, session_id="s1")["evidence"]
    second = _correction(store, session_id="s2")["evidence"]
    rows = store.list_evidence()
    assert [row["evidence_id"] for row in rows] == [first["evidence_id"], second["evidence_id"]]
    assert first["type"] == "correction" and first["prompt_sha256"]
    # append-only: nothing rewrites earlier rows
    _correction(store, session_id="s3")
    assert [row["evidence_id"] for row in store.list_evidence()].index(first["evidence_id"]) == 0


def test_unknown_evidence_type_refused(tmp_path: Path):
    store = _store(tmp_path)
    try:
        store.record_evidence(type="vibe", cue=["x"], proposed_persona="jin")
        raise AssertionError("expected refusal")
    except ValueError:
        pass


# ---------- candidates ----------

def test_single_correction_creates_shadow_only(tmp_path: Path):
    store = _store(tmp_path)
    candidate = _correction(store)["candidate"]
    assert candidate["status"] == "shadow"
    assert candidate["proposed_persona"] == "jin"
    assert candidate["base_persona"] == "misato"


def test_temporary_choice_never_becomes_eligible(tmp_path: Path):
    store = _store(tmp_path)
    for session in ("a", "b", "c", "d"):
        store.record_evidence(
            type="temporary_choice", cue=["cleaning"], previous_persona="misato",
            proposed_persona="jin", prompt=f"switch voice {session}", session_id=session,
        )
    candidate = store.get_candidate(["cleaning"])
    assert candidate["status"] == "shadow"


def test_repeated_corrections_eligible_but_not_promoted(tmp_path: Path):
    store = _store(tmp_path)
    for session in ("a", "b", "c"):
        # Simulate the session state respond() would have noted: an auto
        # route to Misato just before the user manually chose Jin.
        store._last_auto_route[session] = {
            "prompt": "Check the cleaning rota", "persona": "misato",
            "reasons": ["cleaning", "rota"], "request_id": f"r-{session}", "at": time.time(),
        }
        record_manual_choice(
            store, prompt=f"ask Jin about the cleaning rota {session}", chosen_persona="jin",
            session_id=session, owner=None,
        )
    candidate = store.get_candidate(["cleaning", "rota"])
    assert candidate["status"] == "eligible"
    assert candidate["awaiting"] == "user-ratification"
    assert candidate["confidence"]["corrections"] == 3
    try:
        store.promote(candidate["candidate_id"], authorisation={"type": "confidence"})
        raise AssertionError("confidence must never authorise promotion")
    except ValueError:
        pass
    try:
        store.promote(candidate["candidate_id"], authorisation={})
        raise AssertionError("empty authorisation must never promote")
    except ValueError:
        pass


def test_contradictory_evidence_returns_to_shadow(tmp_path: Path):
    store = _store(tmp_path)
    _correction(store)
    _correction(store)
    _correction(store)
    assert store.get_candidate(["cleaning"])["status"] == "eligible"
    store.record_evidence(
        type="correction", cue=["cleaning"], previous_persona="misato",
        proposed_persona="erwin", prompt="actually ask Erwin", session_id="z",
    )
    candidate = store.get_candidate(["cleaning"])
    assert candidate["status"] == "shadow"
    assert candidate["awaiting"] == "contradicting-evidence"
    assert len(candidate["contradicting_evidence"]) == 1


def test_explicit_durable_supersedes_conflicting_inferred_corrections(tmp_path: Path):
    """Regression (found in -08b reconciliation): a durable user instruction after corrections toward a
    DIFFERENT persona used to be filed as contradicting evidence (candidate shadow, unpromotable), so the
    strongest evidence tier was silently ignored."""
    store = _store(tmp_path)
    for session in ("a", "b", "c"):
        store.record_evidence(
            type="correction", cue=["cleaning"], previous_persona="misato",
            proposed_persona="erwin", prompt=f"ask Erwin about the cleaning {session}", session_id=session,
        )
    assert store.get_candidate(["cleaning"])["status"] == "eligible"
    result = store.record_evidence(
        type="explicit_durable", cue=["cleaning"], previous_persona="misato",
        proposed_persona="jin", prompt="For cleaning questions use Jin from now on.", session_id="d",
    )
    candidate = result["candidate"]
    assert candidate["status"] == "eligible" and candidate["proposed_persona"] == "jin"
    assert candidate["superseded_proposals"][0]["persona"] == "erwin"
    assert len(store.list_evidence()) == 4  # nothing rewritten or deleted
    revision = store.promote(
        candidate["candidate_id"],
        authorisation={"type": "user_instruction", "evidence_id": result["evidence"]["evidence_id"]},
    )
    assert revision["persona"] == "jin"
    persona, provenance = store.apply_learned_overlays("who handles the cleaning?", "misato", ["cleaning"])
    assert persona == "jin" and provenance["revision_id"] == revision["revision_id"]


def test_silence_never_promotes_an_eligible_candidate(tmp_path: Path):
    """-08b(a): an eligible candidate with NO ratification act stays eligible and inert forever.

    Time passing, more unrelated traffic, further routed requests that mention the cue and process
    restarts must not promote it; only an explicit authorisation act may.
    """
    root = tmp_path / "routing-state"
    store = RoutingAdaptationStore(root)
    for session in ("a", "b", "c"):
        store._last_auto_route[session] = {
            "prompt": "Check the cleaning rota", "persona": "misato",
            "reasons": ["cleaning", "rota"], "request_id": f"r-{session}", "at": time.time(),
        }
        record_manual_choice(
            store, prompt=f"ask Jin about the cleaning rota {session}", chosen_persona="jin",
            session_id=session, owner=None,
        )
    candidate = store.get_candidate(["cleaning", "rota"])
    assert candidate["status"] == "eligible" and candidate["awaiting"] == "user-ratification"
    before = json.dumps(store.all_candidates(), sort_keys=True)
    evidence_before = len(store.list_evidence())

    for generation in range(3):  # three simulated process restarts
        revived = RoutingAdaptationStore(root)
        for _ in range(5):  # repeated auto traffic that mentions the cue, with no ratification
            persona, provenance = revived.apply_learned_overlays(
                "Check the cleaning rota", "misato", ["cleaning", "rota"]
            )
            assert persona == "misato" and provenance is None
            revived.apply_learned_overlays("what is for dinner?", "aoteru", ["fallback:aoteru"])
        assert revived.active_overlays() == [] and revived.all_revisions() == []
        assert json.dumps(revived.all_candidates(), sort_keys=True) == before, generation
        assert len(revived.list_evidence()) == evidence_before

    # still promotable by a real authorisation act, which is the only way out of "eligible"
    promoted = RoutingAdaptationStore(root).promote(
        candidate["candidate_id"],
        authorisation={"type": "operator_ratification", "principal": "test-operator", "via": "unit-test"},
    )
    assert promoted["status"] == "active"


# ---------- explicit durable preference: promotion ----------

def test_explicit_durable_promotes_and_changes_overlay(tmp_path: Path):
    store = _store(tmp_path)
    outcome = record_durable_instruction(
        store, prompt="For cleaning rota questions, use Misato from now on.",
        named_persona="misato", session_id="s1", owner=None,
    )
    # "cleaning" cue extracted; candidate eligible; promotion authorised.
    assert outcome["state"] == "active"
    assert outcome["promotion"]["authorised_by"] == "user_instruction"
    overlays = store.active_overlays()
    assert len(overlays) == 1 and overlays[0]["cue"] == outcome["cue"]

    persona, provenance = store.apply_learned_overlays(
        "who handles the cleaning schedule?", "aoteru", ["fallback:aoteru"]
    )
    assert persona == "misato"
    assert provenance["learned"] is True and provenance["revision_id"]

    # rollback restores previous behaviour, keeps evidence and candidate
    rollback = store.rollback_revision(outcome["promotion"]["revision_id"], "operator request")
    assert rollback["status"] == "rolled_back"
    assert store.active_overlays() == []
    persona, provenance = store.apply_learned_overlays(
        "who handles the cleaning schedule?", "aoteru", ["fallback:aoteru"]
    )
    assert persona == "aoteru" and provenance is None
    assert store.list_evidence()  # history preserved
    assert store.get_candidate(outcome["cue"]) is not None


def test_reserved_matters_cannot_be_captured_by_learned_state(tmp_path: Path):
    store = _store(tmp_path)
    record_durable_instruction(
        store, prompt="For cleaning standards use Jin from now on.",
        named_persona="jin", session_id="s", owner=None,
    )
    # The cue extracted is "cleaning"; a prompt about cleaning *standards*
    # must still stay with Aoteru (reserved guard outranks learned overlays).
    persona, provenance = store.apply_learned_overlays(
        "Set the household cleaning standard", "aoteru", ["reserved:aoteru"]
    )
    assert persona == "aoteru" and provenance is None


# ---------- restart persistence ----------

def test_state_survives_restart(tmp_path: Path):
    root = tmp_path / "routing-state"
    store = RoutingAdaptationStore(root)
    outcome = record_durable_instruction(
        store, prompt="For watering questions use Ginko from now on.",
        named_persona="ginko", session_id="s", owner=None,
    )
    revision_id = outcome["promotion"]["revision_id"]
    # A new instance = a restarted process reading the same files.
    revived = RoutingAdaptationStore(root)
    assert revived.active_overlays()[0]["revision_id"] == revision_id
    assert revived.get_candidate(outcome["cue"])["status"] == "active"
    assert len(revived.list_evidence()) == 1
    persona, _ = revived.apply_learned_overlays("a watering question", "aoteru", ["fallback:aoteru"])
    assert persona == "ginko"


# ---------- shadow evaluation ----------

def test_shadow_evaluation_buckets_and_spillover(tmp_path: Path):
    store = _store(tmp_path)
    outcome = record_durable_instruction(
        store, prompt="For cleaning questions use Misato from now on.",
        named_persona="misato", session_id="s", owner=None,
    )
    store.rollback_revision(outcome["promotion"]["revision_id"], "demo")
    candidate = store.get_candidate(["cleaning"])

    evaluation = store.evaluate_candidate(
        candidate,
        lambda prompt: resolve_auto_lead(prompt, {
            "aoteru": {"routing": {"intents": ["default"]}},
            "misato": {"routing": {"intents": ["cleaning", "chores", "rota"]}},
            "jin": {"routing": {"intents": ["music", "records"]}},
        }),
        probe_prompts=[
            "Check the cleaning rota",          # target class
            "add chores to my list",             # nearby (chores)
            "suggest some music",                # nearby, must not change
            "set a household cleaning standard", # reserved
        ],
    )
    assert evaluation["shadow_only"] is True
    assert any(row["with_candidate"] == "misato" for row in evaluation["target_prompts"])
    assert evaluation["spillover_count"] == 0
    assert evaluation["reserved_prompts"]
    assert evaluation["verdict"] == "acceptable"


# ---------- cue helpers ----------

def test_keyword_variants_and_cue_extraction():
    assert "cleaning" in keyword_variants("cleaning")
    assert "plants" in keyword_variants("plants") or "plant" in keyword_variants("plants")
    assert extract_cue_term("use Jin for music please", ["music", "records"]) == "music"
    assert extract_cue_term("use Jin for scheduling please", ["music", "records"]) == "scheduling"
    assert extract_cue_term("just do it", []) is None or extract_cue_term("just do it", [])


# ---------- /misumi/respond integration ----------

def _household(tmp_path: Path) -> Path:
    root = tmp_path / "household-repo"
    (root / "docs" / "core").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "core" / "misumi-seed-order-v0.1.md").write_text("# Seed Order\n", encoding="utf-8")
    (root / "config").mkdir(exist_ok=True)
    (root / "config" / "personas.yaml").write_text(_SEED_YAML, encoding="utf-8")
    (root / "household" / "food").mkdir(parents=True, exist_ok=True)
    (root / "household" / "food" / "shopping-list.md").write_text("# Shopping list\n", encoding="utf-8")
    return root


def _client(tmp_path, monkeypatch, *, adaptation=True):
    root = _household(tmp_path)
    monkeypatch.setenv("MISUMI_HOUSEHOLD_ROOT", str(root))
    monkeypatch.setenv("MISUMI_SOURCE_ROOT", str(root))
    monkeypatch.setenv("MISUMI_ROUTING_STATE_ROOT", str(tmp_path / "routing-state"))
    monkeypatch.setenv("MISUMI_EVENT_LOG", str(tmp_path / "events.jsonl"))
    if not adaptation:
        monkeypatch.setenv("MISUMI_ROUTING_ADAPTATION", "0")
    app = FastAPI()
    app.include_router(setup_misumi_routes(SkillsManager(str(tmp_path / "data"))))
    return TestClient(app)


def test_respond_correction_stays_shadow_and_routing_unchanged(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    first = client.post(
        "/misumi/respond",
        json={"prompt": "Check the cleaning rota", "persona": "auto", "session_id": "sess-1"},
    ).json()
    assert first["persona"] == "misato" and first["persona_source"] == "auto"

    second = client.post(
        "/misumi/respond",
        json={"prompt": "Check the cleaning rota, actually play some music instead",
              "persona": "jin", "session_id": "sess-1"},
    ).json()
    note = second["routing_adaptation"]
    assert note["evidence_type"] == "correction"
    assert note["state"] == "shadow-only"
    assert note["base_persona"] == "misato" and note["proposed_persona"] == "jin"

    third = client.post(
        "/misumi/respond",
        json={"prompt": "Check the cleaning rota", "persona": "auto", "session_id": "sess-1"},
    ).json()
    # Shadow candidate must NOT change active routing.
    assert third["persona"] == "misato"
    assert "routing_adaptation" not in third


def test_respond_temporary_choice_not_correction(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    client.post(
        "/misumi/respond",
        json={"prompt": "Check the cleaning rota", "persona": "auto", "session_id": "sess-2"},
    )
    other = client.post(
        "/misumi/respond",
        json={"prompt": "Recommend some music for tonight", "persona": "jin", "session_id": "sess-2"},
    ).json()
    note = other["routing_adaptation"]
    assert note["evidence_type"] == "temporary_choice"
    assert note["state"] == "shadow-only"


def test_respond_durable_preference_promotes_and_reroutes(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    before = client.post(
        "/misumi/respond",
        json={"prompt": "something about music please", "persona": "auto", "session_id": "sess-3"},
    ).json()
    assert before["persona"] == "jin"  # baseline already routes music to jin

    # A durable instruction moving a class that currently falls back to Aoteru.
    instruction = client.post(
        "/misumi/respond",
        json={
            "prompt": "For cleaning questions, from now on use Jin.",
            "persona": "auto",
            "session_id": "sess-3",
        },
    ).json()
    note = instruction["routing_adaptation"]
    assert note["evidence_type"] == "explicit_durable"
    assert note["state"] == "active"
    assert note["promotion"]["authorised_by"] == "user_instruction"

    after = client.post(
        "/misumi/respond",
        json={"prompt": "the cleaning rota needs updating", "persona": "auto", "session_id": "sess-3"},
    ).json()
    assert after["persona"] == "jin"
    assert after["routing"]["method"] == "routing-contract-v0.1+learned-revision"
    assert after["routing"]["learned"]["revision_id"] == note["promotion"]["revision_id"]
    assert after["routing"]["base_selected"] == "misato"

    # New process, same state root: the learned route survives restart.
    restarted = _client(tmp_path, monkeypatch)
    persisted = restarted.post(
        "/misumi/respond",
        json={"prompt": "cleaning roster for next week", "persona": "auto", "session_id": "sess-4"},
    ).json()
    assert persisted["persona"] == "jin"
    assert persisted["routing"]["learned"]["revision_id"] == note["promotion"]["revision_id"]

    # Rollback restores base routing; evidence and candidate stay on disk.
    state_root = tmp_path / "routing-state"
    store = RoutingAdaptationStore(state_root)
    store.rollback_revision(note["promotion"]["revision_id"], "stage demonstration rollback")
    rolled = client.post(
        "/misumi/respond",
        json={"prompt": "the cleaning rota needs updating", "persona": "auto", "session_id": "sess-3"},
    ).json()
    assert rolled["persona"] == "misato"
    assert len(store.list_evidence()) >= 1  # history preserved


def test_respond_incognito_records_no_evidence(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    client.post(
        "/misumi/respond",
        json={"prompt": "Check the cleaning rota", "persona": "auto",
              "session_id": "sess-5", "persist_turn": False},
    )
    out = client.post(
        "/misumi/respond",
        json={"prompt": "Check the cleaning rota again", "persona": "jin",
              "session_id": "sess-5", "persist_turn": False},
    ).json()
    assert "routing_adaptation" not in out
    store = RoutingAdaptationStore(tmp_path / "routing-state")
    assert store.list_evidence() == []


def test_adaptation_kill_switch(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch, adaptation=False)
    first = client.post(
        "/misumi/respond",
        json={"prompt": "Check the cleaning rota", "persona": "auto", "session_id": "sess-6"},
    ).json()
    second = client.post(
        "/misumi/respond",
        json={"prompt": "Check the cleaning rota again", "persona": "jin", "session_id": "sess-6"},
    ).json()
    assert first["persona"] == "misato"
    assert "routing_adaptation" not in second
    assert RoutingAdaptationStore(tmp_path / "routing-state").list_evidence() == []


# ---------- ratification surface (application -08, P1) ----------

def test_operator_ratification_promotes_repetition_eligible_candidate(tmp_path: Path):
    store = _store(tmp_path)
    for session in ("a", "b", "c"):
        store._last_auto_route[session] = {
            "prompt": "Check the cleaning rota", "persona": "misato",
            "reasons": ["cleaning", "rota"], "request_id": f"r-{session}", "at": time.time(),
        }
        record_manual_choice(
            store, prompt=f"ask Jin about the cleaning rota {session}", chosen_persona="jin",
            session_id=session, owner=None,
        )
    candidate = store.get_candidate(["cleaning", "rota"])
    assert candidate["status"] == "eligible"
    revision = store.promote(candidate["candidate_id"], authorisation={
        "type": "operator_ratification", "via": "api", "principal": "operator",
    })
    assert revision["status"] == "active"
    assert revision["authorisation"]["type"] == "operator_ratification"
    persona, provenance = store.apply_learned_overlays(
        "check the cleaning rota", "misato", ["cleaning", "rota"]
    )
    assert persona == "jin" and provenance["learned"]


def test_operator_ratification_requires_principal(tmp_path: Path):
    store = _store(tmp_path)
    record_durable_instruction(
        store, prompt="For watering questions use Ginko from now on.",
        named_persona="ginko", session_id="s", owner=None,
    )
    candidate = store.get_candidate(["watering"])
    try:
        store.promote(candidate["candidate_id"], authorisation={"type": "operator_ratification"})
        raise AssertionError("principal required")
    except ValueError:
        pass


def test_reject_is_terminal_and_preserves_history(tmp_path: Path):
    store = _store(tmp_path)
    candidate = _correction(store)["candidate"]
    rejected = store.reject(candidate["candidate_id"], "not wanted")
    assert rejected["status"] == "rejected"
    try:
        store.reject(candidate["candidate_id"], "again")
        raise AssertionError("re-rejecting a rejected candidate must fail")
    except ValueError:
        pass
    try:
        store.promote(candidate["candidate_id"], authorisation={"type": "operator_ratification", "principal": "x"})
        raise AssertionError("rejected candidates must not promote")
    except ValueError:
        pass
    assert len(store.list_evidence()) == 1  # history preserved


def test_reject_active_candidate_refused(tmp_path: Path):
    store = _store(tmp_path)
    outcome = record_durable_instruction(
        store, prompt="For watering questions use Ginko from now on.",
        named_persona="ginko", session_id="s", owner=None,
    )
    assert outcome["state"] == "active"
    candidate = store.get_candidate(outcome["cue"])
    try:
        store.reject(candidate["candidate_id"], "no")
        raise AssertionError("active candidates roll back, they are not rejected")
    except ValueError:
        pass


def test_routing_api_inspect_promote_rollback(tmp_path, monkeypatch):
    # Simulate an authenticated operator: the ratification endpoint records the
    # token owner as the ratifying principal.
    monkeypatch.setattr("routes.misumi_routes._owner", lambda request: "test-operator")
    client = _client(tmp_path, monkeypatch)
    # Seed an eligible candidate through the real interaction path.
    client.post("/misumi/respond", json={
        "prompt": "Check the cleaning rota", "persona": "auto", "session_id": "ra-1"})
    client.post("/misumi/respond", json={
        "prompt": "no, ask Jin about the cleaning rota", "persona": "jin", "session_id": "ra-1"})

    listed = client.get("/misumi/routing/candidates").json()
    ids = {c["candidate_id"]: c for c in listed["candidates"]}
    assert listed["active_revisions"] == []
    target = next(c for c in ids.values() if c["status"] == "shadow")

    # A shadow candidate cannot be promoted through the API (gate).
    refused = client.post(f"/misumi/routing/candidates/{target['candidate_id']}/promote")
    assert refused.status_code == 409

    # Drive it to eligible and ratify through the API.
    store = RoutingAdaptationStore(tmp_path / "routing-state")
    for session in ("x", "y", "z"):
        store._last_auto_route[session] = {
            "prompt": "Check the cleaning rota", "persona": "misato",
            "reasons": ["cleaning", "rota"], "request_id": f"r-{session}", "at": time.time()}
        record_manual_choice(store, prompt=f"ask Jin about the cleaning {session}",
                             chosen_persona="jin", session_id=session, owner=None)
    eligible = store.get_candidate(["cleaning", "rota"])
    assert eligible["status"] == "eligible"

    promoted = client.post(
        f"/misumi/routing/candidates/{eligible['candidate_id']}/promote")
    assert promoted.status_code == 200
    revision_id = promoted.json()["revision"]["revision_id"]

    rerouted = client.post("/misumi/respond", json={
        "prompt": "the cleaning rota needs updating", "persona": "auto", "session_id": "ra-2"}).json()
    assert rerouted["persona"] == "jin"
    assert rerouted["routing"]["learned"]["revision_id"] == revision_id

    rolled = client.post(
        f"/misumi/routing/revisions/{revision_id}/rollback",
        json={"reason": "operator rollback via API"})
    assert rolled.status_code == 200
    restored = client.post("/misumi/respond", json={
        "prompt": "the cleaning rota needs updating", "persona": "auto", "session_id": "ra-2"}).json()
    assert restored["persona"] == "misato"

    rejected = client.post(
        f"/misumi/routing/candidates/{target['candidate_id']}/reject",
        json={"reason": "not wanted"})
    assert rejected.status_code == 200
    final = client.get("/misumi/routing/candidates").json()
    statuses = {c["candidate_id"]: c["status"] for c in final["candidates"]}
    assert statuses[target["candidate_id"]] == "rejected"


def test_routing_api_unknown_ids_404(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    assert client.get("/misumi/routing/candidates").status_code == 200
    assert client.post("/misumi/routing/candidates/aff-nonexistent/promote").status_code == 404
    assert client.post("/misumi/routing/candidates/aff-nonexistent/reject").status_code == 404
    assert client.post("/misumi/routing/revisions/rr-nonexistent/rollback").status_code == 404


def test_routing_api_disabled_503(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch, adaptation=False)
    assert client.get("/misumi/routing/candidates").status_code == 503
