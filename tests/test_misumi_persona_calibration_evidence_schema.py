import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _load(path: str):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_evidence_schema_is_proposed_and_non_routing():
    schema = _load("evals/misumi/persona_calibration_evidence_schema.json")
    assert schema["status"] == "proposed"
    assert schema["controls_routing"] is False
    assert schema["routing_boundary"]["evaluation_record_may_change_routing"] is False
    assert schema["routing_boundary"]["routing_change_requires_separate_evidence_review"] is True
    assert schema["routing_boundary"]["persona_promotion_must_remain_interactive"] is True


def test_evidence_schema_requires_provenance_freshness_and_runtime_identity():
    schema = _load("evals/misumi/persona_calibration_evidence_schema.json")
    required = set(schema["required_fields"])
    assert {
        "fixture_provenance",
        "capability_alias",
        "resolved_model",
        "model_configuration",
        "source_commit",
        "observed_at",
        "freshness",
        "status",
    } <= required
    assert schema["provenance"]["required"] is True
    assert schema["freshness"]["required"] is True
    assert schema["freshness"]["fail_closed_when_stale_for_routing_review"] is True


def test_evidence_schema_maps_required_improvement_graph_entities():
    schema = _load("evals/misumi/persona_calibration_evidence_schema.json")
    nodes = set(schema["graph_mapping"]["nodes"])
    assert {
        "Persona",
        "TaskClass",
        "CapabilityAlias",
        "ConcreteModel",
        "Evaluation",
        "Metric",
        "FailureMode",
        "Validator",
        "Regression",
        "Evidence",
    } <= nodes


def test_evidence_schema_uses_ratified_status_vocabulary():
    schema = _load("evals/misumi/persona_calibration_evidence_schema.json")
    assert "proposed" in schema["allowed_statuses"]
    assert "ratified" in schema["allowed_statuses"]
    assert "rejected" in schema["allowed_statuses"]
    assert "archived" in schema["allowed_statuses"]
