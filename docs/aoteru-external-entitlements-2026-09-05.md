---
title: Aoteru external developer entitlement update
status: observed-not-routed
as_of: 2026-09-05
owner: odysseus
scope: external coding/model entitlements relevant to model-host routing
---

# External developer entitlement update

Operator-confirmed current availability:

- **GitHub Copilot Student** is enabled. Treat it as a zero-marginal-cost, human-in-the-loop IDE/operator aid for completion, small edits and quick repository questions. It is not an Odysseus execution worker, model-routing authority or independent verifier.
- **Z.AI GLM Coding Lite** is subscribed. It is available as a candidate paid implementation worker through the existing Claude Code harness using Z.AI's Anthropic-compatible interface. Subscription availability alone does not qualify it for production routing.

## Routing consequence

No production route changes are authorised by this record. `config/models.yaml` remains the model/provider registry and `default_paid_provider` remains `codex` until evidence supports a governed change. No provider credential or API key belongs in Git.

Before GLM can become routing-eligible, the existing model-host routing contract requires measured evidence on representative estate work. At minimum record first-pass completion, deterministic test/validator outcome, scope violations, human correction/intervention, retry/escalation, latency and provider usage/credit consumption. Compare against the incumbent route on the same task classes, then promote only if the quality floor is maintained with a meaningful cost or capacity benefit.

Copilot requires no autonomous routing qualification because it remains outside the worker router by design.
