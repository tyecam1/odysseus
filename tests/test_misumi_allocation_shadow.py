"""Shadow persona-allocation proposal: derivation, abstention, escalation, authority independence, no live effect."""

import copy
import hashlib
import importlib.util
import re
from pathlib import Path

import pytest

from src import misumi_allocation_shadow as shadow

REPO = Path(__file__).resolve().parent.parent
ORDER = ["aoteru", "kurisu", "sanji", "l", "ginko"]


def _p(name, intents, aliases=(), consults=()):
    return {"name": name, "routing": {"intents": list(intents), "aliases": list(aliases)}, "consults": list(consults)}


PERSONAS = {  # synthetic fixture: not the ratified registry
    "aoteru": _p("Aoteru Misumi", ["default", "standards"], consults=["sanji", "l", "ginko", "kurisu"]),
    "kurisu": _p("Kurisu Makise", ["archive", "evidence"], ["notes", "minutes"], consults=["aoteru"]),
    "sanji": _p("Sanji Vinsmoke", ["food", "pantry"], ["dinner", "fridge"], consults=["l", "aoteru"]),
    "l": _p("L Lawliet", ["money", "finance"], ["bill", "budget", "bills"], consults=["sanji", "aoteru"]),
    "ginko": _p("Ginko", ["plants", "damp"], ["herbs"], consults=["l", "kurisu", "aoteru"]),
}


def propose(prompt, **kw):
    return shadow.propose(prompt, PERSONAS, policy_order=ORDER, **kw)


def test_it_has_no_live_effect_and_leaves_its_inputs_untouched():
    before = copy.deepcopy(PERSONAS)
    result = propose("Compare the grocery bill against the pantry")
    assert result["live_effect"] == "none" and result["method"] == shadow.METHOD
    assert PERSONAS == before


def test_it_is_deterministic():
    prompt = "Compare the grocery bill against the pantry"
    assert propose(prompt) == propose(prompt)


@pytest.mark.parametrize("prompt", [
    "What is in the pantry?", "Email the council about the bill", "Pay the bill now", "Skip this song", "Add milk to the pantry list",
    "Delete the notes", "Ratify the new standards", "Record what the flatmates say",
])
def test_authority_is_never_granted_by_the_proposal(prompt):
    assert propose(prompt)["authority"]["granted"] is False


@pytest.mark.parametrize("prompt", ["Pay the bill now", "Skip this song", "Add milk to the pantry list", "Email the landlord", "What is in the pantry?"])
def test_required_authority_does_not_depend_on_who_leads(prompt):
    base = propose(prompt)["authority"]["required"]
    reordered = dict(reversed(list(PERSONAS.items())))
    other = shadow.propose(prompt, reordered, policy_order=list(reversed(ORDER)))["authority"]["required"]
    assert base == other == shadow.required_authority(prompt)["required"]
    for lead in ("sanji", "l", "ginko", "aoteru"):
        assert shadow.required_authority(prompt)["required"] == base  # the function cannot even be given a persona


def test_a_persona_with_a_blocked_tool_does_not_change_what_is_required_only_what_the_ceiling_check_reports():
    plain = propose("Email the landlord about the bill")
    checked = propose("Email the landlord about the bill", blocked_tools_of=lambda persona: ["email_send"])
    assert plain["authority"]["required"] == checked["authority"]["required"] == "blocked"
    assert checked["authority"]["ceiling_check"] == "blocked-for-lead" and "ceiling_check" not in plain["authority"]
    assert checked["decision"] == plain["decision"] == "escalate"


def test_an_unreadable_policy_is_reported_not_assumed_permissive():
    def boom(_):
        raise RuntimeError("policy missing")
    assert propose("Pay the bill now", blocked_tools_of=boom)["authority"]["ceiling_check"] == "policy-unreadable"


@pytest.mark.parametrize("prompt,tool", [
    ("Email the landlord that we are withholding rent", "email_send"), ("Pay the bill from the joint account", "bank_write"),
    ("Delete all the voice notes from last month", "destructive_delete"),
    ("Turn on the hallway microphone and log what the flatmates say", "audio_capture"),
    ("Record everything the guests say in the kitchen", "audio_capture"),
])
def test_actions_beyond_any_specialist_ceiling_escalate_with_no_specialist(prompt, tool):
    result = propose(prompt)
    assert result["decision"] == "escalate" and result["supports"] == [] and result["authority"]["implied_tool"] == tool
    assert result["authority"]["owner_approval_required"] is True


def test_reserved_matters_escalate_to_the_head_even_when_a_specialist_is_named():
    result = propose("Ask Sanji and L to ratify the new household values")
    assert result["decision"] == "escalate" and result["lead"] == "aoteru" and result["supports"] == []
    assert "reserved-matter" in result["reasons"]


def test_a_negated_action_is_not_an_action():
    assert shadow.required_authority("Don't play anything, just tell me which album this is")["required"] == "none"
    assert shadow.required_authority("Play the next track")["required"] == "playback_control"
    assert shadow.required_authority("Add bread to the list")["required"] == "scoped_write"
    assert shadow.required_authority("What is in the fridge?")["required"] == "none"


def test_a_request_no_domain_covers_abstains_and_invents_no_expertise():
    result = propose("Translate this paragraph into French")
    assert result["decision"] == "abstain" and result["lead"] == "aoteru" and result["supports"] == []
    assert result["reasons"] == ["no-registered-domain"] and result["overhead"]["expected_extra_model_calls"] == 0


def test_one_domain_is_solo_and_a_cross_check_inside_it_adds_no_specialist():
    solo = propose("What is left in the pantry?")
    assert solo["decision"] == "solo" and solo["lead"] == "sanji" and solo["reasons"] == ["single-domain"]
    inside = propose("Cross-check the pantry against the fridge")
    assert inside["decision"] == "solo" and "cross-check-within-one-domain" in inside["reasons"]


def test_a_cross_domain_check_along_a_consult_edge_proposes_one_support_with_a_named_reason():
    result = propose("Compare the grocery bill against the pantry")
    assert result["decision"] == "team"
    assert [(s["persona"], s["benefit"]) for s in result["supports"]] == [("sanji" if result["lead"] == "l" else "l", "cross_domain_verification")]
    support = result["supports"][0]
    assert support["expected_benefit_status"] == "unproven" and support["competence_evidence"] == "routing-cues-only" and support["edge"] is True
    assert result["overhead"]["expected_extra_model_calls"] == 1 and result["adequacy"]["solo_adequate"] is False


def test_a_second_domain_that_is_not_a_consult_edge_is_excluded_and_explained():
    result = propose("Reconcile the archive notes with the dinner plan")  # kurisu leads or sanji; neither consults the other
    assert result["lead"] in ("kurisu", "sanji")
    if result["lead"] == "kurisu":
        assert result["decision"] == "solo" and result["excluded"] == [{"persona": "sanji", "reason": "not-a-consult-edge-of-lead"}]
        assert "second-domain-is-not-a-consult-edge" in result["reasons"]


def test_two_domains_without_a_cross_check_or_a_named_persona_stay_solo():
    result = propose("What is in the pantry and what is the budget?")
    assert result["decision"] == "solo" and result["supports"] == []


def test_a_user_named_second_persona_is_a_justified_support():
    result = propose("Ask Sanji and L to look at the dinner bill")
    assert result["decision"] == "team" and {s["benefit"] for s in result["supports"]} == {"user_named"}


def test_a_follow_up_carries_the_lead_and_recruits_no_one():
    result = propose("And the day after?", prior_lead="sanji")
    assert result["decision"] == "solo" and result["lead"] == "sanji" and result["supports"] == []


def test_the_head_never_appears_as_a_support_and_supports_are_capped():
    personas = {**PERSONAS, "ginko": _p("Ginko", ["plants", "damp"], ["herbs"], consults=["l", "kurisu", "aoteru", "sanji"])}
    result = shadow.propose("Cross-check the damp herbs against the dinner budget notes", personas, policy_order=ORDER)
    assert len(result["supports"]) <= shadow.MAX_SUPPORT and all(s["persona"] != "aoteru" for s in result["supports"])


def test_the_production_plan_is_recorded_for_comparison_only():
    plan = {"decision": "solo", "supports": []}
    result = propose("Compare the grocery bill against the pantry", production_plan=plan)
    assert result["production"] == {"decision": "solo", "supports": [], "supports_agree": False}


def test_limitations_state_that_cues_are_not_competence_and_benefit_is_unproven():
    text = " ".join(propose("What is in the pantry?")["limitations"])
    assert "not evidence of competence" in text and "unproven" in text


# --- the evaluation's frozen inputs ---------------------------------------------------------------------------------------------


def test_the_held_out_corpus_matches_the_hash_recorded_in_the_preregistration():
    folder = REPO / "evals" / "misumi-allocation"
    recorded = re.search(r"corpus-heldout-v1\.yaml` SHA-256: ([0-9a-f]{64})", (folder / "PREREGISTRATION.md").read_text(encoding="utf-8")).group(1)
    assert hashlib.sha256((folder / "corpus-heldout-v1.yaml").read_bytes()).hexdigest() == recorded


def test_runner_scores_by_the_documented_rule():
    spec = importlib.util.spec_from_file_location("alloc_run", REPO / "evals" / "misumi-allocation" / "run_eval.py")
    run = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(run)
    case = {"expect": {"decision": "team", "lead": ["sanji", "l"], "supports": ["l"]}}
    assert run.score(case, {"decision": "team", "lead": "sanji", "supports": ["l"]}) == {"decision": True, "team_axis": True, "lead": True}
    assert run.score(case, {"decision": "team", "lead": "sanji", "supports": ["kurisu"]})["decision"] is False
    assert run.score(case, {"decision": "solo", "lead": "ginko", "supports": []}) == {"decision": False, "team_axis": False, "lead": False}
