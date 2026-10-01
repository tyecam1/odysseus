from src.prompt_evolution import (
    calculated_overall,
    derive_targets,
    graph_edges_for_plan,
    plan_evolution,
    validate_child_metadata,
)


def _trace(**overrides):
    base = {
        "application_id": "app-1",
        "prompt_id": "p",
        "prompt_version": 1,
        "failure_tags": [],
        "rating": {
            "goal_progress": 5,
            "correctness_verification": 5,
            "authority_scope_discipline": 5,
            "routing_resource_efficiency": 5,
            "continuity_handoff_quality": 5,
            "agent_overall": 5.0,
            "operator_overall": None,
            "operator_note": None,
        },
    }
    base.update(overrides)
    return base


def test_clean_trace_reinforces_instead_of_version_churn():
    plan = plan_evolution(_trace())
    assert plan.decision == "reinforce"
    assert plan.next_version is None
    assert graph_edges_for_plan(plan)[-1]["type"] == "reinforced"


def test_failure_tags_and_low_dimensions_create_child_plan():
    trace = _trace(
        failure_tags=["long_horizon_early_return", "rabby_public_fulltext_route_missed"],
        rating={
            "goal_progress": 4,
            "correctness_verification": 4,
            "authority_scope_discipline": 3,
            "routing_resource_efficiency": 4,
            "continuity_handoff_quality": 3,
            "agent_overall": 3.6,
            "operator_overall": None,
            "operator_note": None,
        },
    )
    plan = plan_evolution(trace)
    assert plan.decision == "evolve"
    assert plan.next_version == 2
    assert any("checkpoint" in x for x in plan.targets)
    assert any("public-full-text" in x for x in plan.targets)
    assert any("authority/scope" in x for x in plan.targets)
    assert any("continuity" in x for x in plan.targets)


def test_operator_note_becomes_evolution_evidence():
    trace = _trace()
    trace["rating"]["operator_note"] = "make the prompt identify its own version"
    assert any("operator feedback" in x for x in derive_targets(trace))


def test_overall_is_mean_of_five_dimensions():
    trace = _trace()
    trace["rating"].update({
        "goal_progress": 4,
        "correctness_verification": 4,
        "authority_scope_discipline": 3,
        "routing_resource_efficiency": 4,
        "continuity_handoff_quality": 3,
        "agent_overall": 3.6,
    })
    assert calculated_overall(trace) == 3.6


def test_child_metadata_must_bind_parent_and_application():
    good = {
        "prompt_id": "p",
        "version": 2,
        "parent_version": 1,
        "derived_from_applications": ["app-1"],
    }
    assert validate_child_metadata("p", 1, "app-1", good) == []
    bad = dict(good, version=3, parent_version=2, derived_from_applications=[])
    errors = validate_child_metadata("p", 1, "app-1", bad)
    assert len(errors) == 3
