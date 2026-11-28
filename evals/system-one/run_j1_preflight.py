"""Replay existing J1 decisions against the shipping configuration without inference."""
import os
from pathlib import Path

import yaml

if __name__ == "__main__" and os.environ.get("DATABASE_URL") != "sqlite:///:memory:":
    raise SystemExit("The development replay requires DATABASE_URL=sqlite:///:memory:")

from src import estate_router
from src.system_one import Decision


def replay(cases):
    if any(provider["enabled"] for provider in estate_router.research_decision_providers().values()):
        raise ValueError("The development preflight requires all adapters disabled")
    outcomes = []
    for case in cases:
        make = getattr(Decision, case["primitive"])
        args = case["state"], case["question"]
        if case["primitive"] == "noul":
            decision = make(*args)
        elif case["primitive"] == "rank":
            decision = make(case["state"], case["candidates"], question=case["question"])
        else:
            decision = make(*args, case["candidates"])
        if case["expected"] not in decision.keys:
            raise ValueError("Historical label must be within the stated candidate space")
        for profile in ("contribution", "red-team", "consolidation"):
            result = estate_router.research_decision(
                case["task_class"], decision, profile=profile, parent_run_id="j1-development-preflight",
                high_consequence=case.get("requires_governance", False),
            )
            outcomes.append((case["id"], profile, result))
    return outcomes


if __name__ == "__main__":
    from collections import Counter
    import json

    cases = yaml.safe_load(Path(__file__).with_name("j1-replay-candidates.yaml").read_text())["cases"]
    outcomes = replay(cases)
    print(json.dumps(Counter(result["escalation_reason"] for _, _, result in outcomes), indent=2))
    if any(result["selected"] is not None for _, _, result in outcomes):
        raise SystemExit("The development replay must never select an action with all adapters disabled")
    if not all(result["telemetry_persisted"] for _, _, result in outcomes):
        raise SystemExit("The development replay must retain its telemetry in the temporary database")
