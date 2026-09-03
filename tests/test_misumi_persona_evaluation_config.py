import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def _load_json(path: str):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def _model_aliases():
    data = yaml.safe_load((ROOT / "config/models.yaml").read_text(encoding="utf-8"))
    return {item["alias"] for item in data["capabilities"]}


def test_evaluation_spec_covers_every_persona_policy_entry():
    policy = _load_json("config/misumi_persona_policy.json")
    spec = _load_json("config/misumi_persona_evaluation.json")
    assert set(spec["personas"]) == set(policy)


def test_evaluation_spec_is_non_routing_proposal():
    spec = _load_json("config/misumi_persona_evaluation.json")
    assert spec["status"] == "proposed"
    assert spec["controls_routing"] is False


def test_every_persona_has_task_classes_metrics_and_valid_capability_aliases():
    spec = _load_json("config/misumi_persona_evaluation.json")
    aliases = _model_aliases()

    for persona, entry in spec["personas"].items():
        assert entry["task_classes"], persona
        assert entry["metrics"], persona
        assert entry["candidate_capabilities"], persona
        unknown = set(entry["candidate_capabilities"]) - aliases
        assert not unknown, f"{persona} references unknown capabilities: {sorted(unknown)}"


def test_no_persona_evaluation_entry_hardcodes_concrete_model_names():
    spec = _load_json("config/misumi_persona_evaluation.json")
    concrete_models = {
        item.get("binding")
        for item in yaml.safe_load((ROOT / "config/models.yaml").read_text(encoding="utf-8"))["capabilities"]
        if item.get("binding")
    }
    serialized = json.dumps(spec)
    for model in concrete_models:
        assert model not in serialized
