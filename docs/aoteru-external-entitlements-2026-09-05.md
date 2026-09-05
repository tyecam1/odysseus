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
- **Google AI student entitlement** is active at zero subscription cost. Treat this as a currently unintegrated consumer capability, not as Gemini API/CLI quota and not as an execution provider. Its useful role still needs to be established without adding a second orchestration layer or forcing Antigravity into the estate.

## Routing consequence

No production route changes are authorised by this record. `config/models.yaml` remains the model/provider registry and `default_paid_provider` remains `codex` until evidence supports a governed change. No provider credential or API key belongs in Git.

Before GLM can become routing-eligible, the existing model-host routing contract requires measured evidence on representative estate work. At minimum record first-pass completion, deterministic test/validator outcome, scope violations, human correction/intervention, retry/escalation, latency and provider usage/credit consumption. Compare against the incumbent route on the same task classes, then promote only if the quality floor is maintained with a meaningful cost or capacity benefit.

Copilot requires no autonomous routing qualification because it remains outside the worker router by design.

## GLM harness integration target

Integrate GLM as a **sidecar provider on the existing Claude Code harness**, not as a second coding environment:

```text
claude      -> existing Anthropic Claude Code path, unchanged
claude-glm  -> same Claude Code executable + host-local Z.AI provider overrides
```

The `claude-glm` launcher should be host-local, reversible, and expose provider variables only to its child process. Keep the Z.AI secret under a provider-specific local name such as `ZAI_GLM_CODING_KEY`; never persist it in Git, `~/.claude/settings.json`, a repository `.env`, or global `ANTHROPIC_*` environment variables. Current provider endpoint/model mappings are implementation details of that host-local launcher and should be rechecked against live provider documentation rather than hard-coded into Odysseus routing policy.

After the sidecar command is smoke-tested, qualify GLM on representative bounded repository tasks before adding it as an eligible paid provider. Extend the existing paid-provider/Claude Code execution path rather than creating a GLM-specific router, queue, task state, or second Claude installation.

## Google integration gap

The free Google student entitlement has material potential value for long-context document/research work, independent second-provider review and Google-native research surfaces, but it is not currently available to the estate through the same direct CLI/provider path used by Codex or GLM. That creates a bounded integration need rather than a reason to add another cockpit.

Integration work should therefore determine the **minimum-overhead governed role** for this entitlement while preserving the current architecture:

1. keep Odysseus as the only runtime/model-host routing authority;
2. do not register the consumer subscription as Gemini API or Gemini CLI capacity unless a supported entitlement path is proven live;
3. prefer a human-in-the-loop research/review handoff or thin adapter over Antigravity or another parallel agent environment;
4. preserve source/provenance pointers and existing PhD authorship/evidence gates;
5. measure whether Google access adds a real capability gap closure before introducing any persistent integration surface;
6. if programmable Gemini API use is later justified, treat its separately billed API capacity as a distinct provider entitlement and qualify it independently.

Until that work is complete, Google remains `available-unintegrated` and must not appear as a routable paid/free worker in `config/models.yaml`.
