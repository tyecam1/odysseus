"""Baseline generalisation/adversarial suite for the deterministic router.

Mirrors fixtures/persona-routing/generalisation.yaml in the misumi knowledgebase
(keep the manifest and prompts in sync with it). Purpose: pin the CURRENT
deterministic baseline (weaknesses included, marked known_weakness there) so
that later routing changes - learned or otherwise - are visible differences,
and so "router weakness" can be told apart from "genuine learned preference".
"""

from src.misumi_routing_adaptation import (
    RoutingAdaptationStore,
    keyword_present,
)
from src.misumi_persona_routing import resolve_auto_lead

# The LIVE manifest's routing.intents (tyecam1/misumi config/personas.yaml @ main 0d5bdb6aec), in manifest order -
# order is the contract's tie-break. Correction 2026-10-06: this table originally carried a drifted copy (e.g. l had
# budget/bills, misato chores, ichigo deadline/blocked), so g13 pinned a route production never takes.
MANIFEST = {
    pid: {"routing": {"intents": intents}}
    for pid, intents in {
        "aoteru": ["default", "standards", "coherence", "boundaries", "integration"],
        "erwin": ["priorities", "planning", "risk", "strategy", "recovery"],
        "lelouch": ["workflows", "protocols", "tasks", "process", "implementation"],
        "misato": ["cleaning", "rota", "care", "rest", "wellbeing"],
        "kurisu": ["capture", "memory", "archive", "evidence", "transcript"],
        "l": ["money", "finance", "anomaly", "waste", "diagnostics"],
        "ginko": ["plants", "damp", "pests", "environment", "watering"],
        "sanji": ["food", "meals", "shopping", "stock", "recipes"],
        "jin": ["records", "music", "gigs", "wantlist", "listening"],
        "ichigo": ["overdue", "urgent", "closure", "safety", "stalled"],
        "giorno": ["ideas", "evolution", "experiments", "opportunities", "repurpose"],
        "kino": ["phd", "vault", "profile", "personal", "exports", "context"],
    }.items()
}

# (id, category, prompt, expected baseline persona)
SUITE = [
    ("g01", "paraphrase", "Who should I ask about sorting out the cleaning schedule?", "misato"),
    ("g02", "paraphrase", "What can I cook with what's in the fridge?", "aoteru"),  # known_weakness
    ("g03", "indirect", "The bins weren't taken out again and the kitchen is a mess.", "aoteru"),  # known_weakness
    ("g04", "underspecified", "What about the shopping?", "sanji"),
    ("g05", "underspecified", "Can you deal with it before Friday?", "aoteru"),  # known_weakness
    ("g06", "mixed-domain", "Plan the cleaning budget and the food shopping this week.", "sanji"),
    ("g07", "competing-cues", "This urgent finance problem needs someone on it now.", "l"),
    ("g08", "negation", "I don't need any help with food this week.", "sanji"),  # known_weakness
    ("g09", "correction", "Not the cleaning, I meant the rota for next week.", "misato"),
    ("g10", "follow-up", "and what about tomorrow?", "aoteru"),  # known_weakness
    ("g11", "novel-wording", "bin rotation is slipping again", "aoteru"),  # known_weakness
    ("g12", "paraphrase", "Which records should I put on tonight?", "jin"),
    ("g13", "mixed-domain", "Water the plants while reviewing the bills.", "ginko"),  # was "l" under the drifted table
    ("g14", "competing-cues", "Draft a recovery plan for the stalled garden project.", "erwin"),
    ("g15", "negation", "Stop reminding me about the rota.", "misato"),  # known_weakness
]


def _baseline(prompt: str):
    return resolve_auto_lead(prompt, MANIFEST)


def test_deterministic_baseline_is_pinned():
    for gid, category, prompt, expected in SUITE:
        persona, provenance = _baseline(prompt)
        assert persona == expected, f"{gid} ({category}): {prompt!r} -> {persona}, expected {expected}"
        assert provenance["method"] == "routing-contract-v0.1"


def test_baseline_is_repeatable():
    for prompt in {row[2] for row in SUITE}:
        assert _baseline(prompt) == _baseline(prompt)


def test_reserved_matters_survive_every_category():
    for suffix in ("", " please", " as an experiment"):
        persona, provenance = resolve_auto_lead(
            f"Set a Level 5 boundary about the cleaning rota{suffix}", MANIFEST
        )
        assert persona == "aoteru"
        assert provenance["reasons"] == ["reserved:aoteru"]


def test_learned_overlay_changes_only_its_class(tmp_path):
    """With an active learned revision cue=cleaning -> jin, only prompts that
    mention the cue move; every other generalisation prompt is untouched.
    This is the distinction between a learned preference and router drift."""
    store = RoutingAdaptationStore(tmp_path / "routing-state")
    store.record_evidence(
        type="explicit_durable", cue=["cleaning"], previous_persona="misato",
        proposed_persona="jin", prompt="For cleaning questions use Jin from now on.",
        session_id="s", owner=None,
    )
    candidate = store.get_candidate(["cleaning"])
    store.promote(
        candidate["candidate_id"],
        authorisation={"type": "user_instruction", "evidence_id": candidate["supporting_evidence"][0]},
    )

    def routed(prompt: str) -> str:
        persona, reasons = _baseline(prompt)
        persona, _ = store.apply_learned_overlays(prompt, persona, reasons)
        return persona

    moved, unmoved = [], []
    for gid, category, prompt, expected in SUITE:
        if keyword_present(prompt, "cleaning"):
            moved.append(gid)
            assert routed(prompt) == "jin", f"{gid} should follow the learned cue"
        else:
            unmoved.append(gid)
            assert routed(prompt) == expected, f"{gid} must not be affected by the learned cue"
    # The learned cue moves exactly the cleaning-mentioning prompts; negation
    # cases without the cue word stay as the baseline routed them (the learned
    # state inherits the router's cue detection, it does not fix it).
    assert set(moved) == {"g01", "g06", "g09"}
    assert len(unmoved) == len(SUITE) - len(moved)
