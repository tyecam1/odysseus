---
title: Aoteru external developer entitlement update
status: observed-not-routed
as_of: 2026-09-06
owner: odysseus
scope: external coding/model entitlements relevant to model-host routing
---

# External developer entitlement update

Operator-confirmed availability:

- GitHub Copilot Student is enabled as human-in-the-loop operator assistance. It is not an Odysseus worker, router or verifier.
- Z.AI GLM Coding Lite is subscribed and the host-local `claude-glm` launcher has passed a smoke test. It invokes the same Claude Code installation with process-local Z.AI overrides. Normal `claude` remains Anthropic Claude Code.
- Google AI student entitlement is active at zero subscription cost, but remains an unintegrated consumer capability rather than Gemini API or CLI quota.

## Routing consequence

Codex remains `default_paid_provider`. GLM is registered as a real paid-provider candidate with `routing_eligible: false`; it is selectable only by an explicit candidate opt-in for controlled evaluation. This record does not qualify or promote GLM. No provider credential or API key belongs in Git.

The GLM launcher shares the normal Claude working directory, repository instructions, configuration, memory, permissions and compatible hooks. Z.AI authentication changes some claude.ai account connectors and built-in tools/skills; this limitation is part of qualification evidence. Odysseus invokes the launcher and does not manipulate Z.AI credentials, endpoint/model mappings or global `ANTHROPIC_*` state.

Qualification must compare paired representative repository tasks against the incumbent route using identical base SHA, objective, scope and validators. Record first-pass success, tests/validators, scope violations, interventions, retries/escalations, latency and reported usage/credits (or an explicit unavailable reason). Any authority or scope violation fails the safety gate. Promotion requires evidence-reviewed quality at least matching the incumbent with a meaningful cost or capacity benefit in a separate change.

Google remains outside `config/models.yaml` until a supported programmable entitlement path and governed role are established without another orchestration layer.
