import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _load(path: str):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_core_calibration_battery_is_evidence_only():
    battery = _load("evals/misumi/persona_calibration_core.json")
    assert battery["status"] == "proposed"
    assert battery["controls_routing"] is False
    assert battery["regression_policy"]["routing_change_requires_separate_ratification"] is True


def test_core_personas_have_representative_adversarial_and_uncertainty_cases():
    battery = _load("evals/misumi/persona_calibration_core.json")
    cases = battery["cases"]
    for persona in ("aoteru", "lelouch", "kurisu"):
        kinds = {case["kind"] for case in cases if case["persona"] == persona}
        assert {"representative", "adversarial", "uncertainty"} <= kinds, persona


def test_calibration_cases_reference_declared_task_classes_and_metrics():
    spec = _load("config/misumi_persona_evaluation.json")
    battery = _load("evals/misumi/persona_calibration_core.json")
    for case in battery["cases"]:
        persona_spec = spec["personas"][case["persona"]]
        assert case["task_class"] in persona_spec["task_classes"], case["id"]
        unknown_metrics = set(case["metrics"]) - set(persona_spec["metrics"])
        assert not unknown_metrics, f"{case['id']} uses undeclared metrics: {sorted(unknown_metrics)}"


def test_regression_policy_forbids_forgetting_failures():
    policy = _load("evals/misumi/persona_calibration_core.json")["regression_policy"]
    assert policy["retain_failed_cases"] is True
    assert policy["retain_previously_fixed_cases"] is True
    assert policy["candidate_must_pass_applicable_history"] is True
