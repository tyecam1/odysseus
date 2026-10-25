"""Keep the declarative memory allowlist parseable and its boundaries intact."""

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_memory_sources_register_prompts_without_widening_policy():
    config = yaml.safe_load(
        (ROOT / "config" / "memory-sources.yaml").read_text(encoding="utf-8")
    )
    sources = config["sources"]
    assert isinstance(sources, list)
    assert all(isinstance(source, dict) for source in sources)
    ids = [source["id"] for source in sources]
    assert all(isinstance(source_id, str) and source_id for source_id in ids)
    assert len(ids) == len(set(ids)), "memory source IDs must be unique"

    prompts = next(source for source in sources if source["id"] == "initialising-prompt-register")
    assert prompts["domain"] == "neutral"
    assert prompts["status"] == "active"
    assert prompts["path"] == "config/initialising-prompts.yaml"
    assert config["sensitivity_rules"]["default"] == "domain-scoped"
    assert config["sensitivity_rules"]["cross_domain_write"] == "deny"
