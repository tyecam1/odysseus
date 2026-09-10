---
artifact_type: agent-task
task_schema: agent-task/v1
task_id: 2026-09-10-aoteru-model-effort-routing
title: "Add model effort to central routing"
status: ready
priority: high
task_type: bounded-routing-extension
created_by: chatgpt
created_at: 2026-09-10T23:00:00+01:00
executor: claude-sonnet
execution_mode: autonomous-until-acceptance
resource_profile: medium
risk_level: low
approval_required: false
source_traceability_required: true
requires_local_model: false
requires_remote_compute: false
requires_web: false
repo: tyecam1/odysseus
branch: chatgpt/model-effort-routing-20260910
inputs:
  - docs/aoteru-model-host-routing-contract.md
  - config/routing.yaml
  - config/models.yaml
outputs:
  - route object can carry model reasoning effort
  - complexity provides default effort
  - supported providers receive effort without changing authority or verification
---

# Add model effort to central routing

## Mission

Make the smallest extension to the existing Odysseus router so model selection and reasoning effort are resolved together.

Do not create a new router, task taxonomy, benchmark framework, quota manager, or PhD-specific duplicate policy.

Target behaviour:

```text
task -> existing capability/authority routing -> cheapest adequate model + lowest adequate effort -> existing verification/escalation
```

## Required change

1. Find the current canonical route/result object used by the live router.
2. Add one optional `effort` field.
3. Reuse the existing task `complexity` values as the default effort signal:

```text
trivial  -> low
routine  -> medium
hard     -> high
frontier -> highest available
```

4. Allow an explicit task effort override where the existing task envelope can naturally carry it.
5. Pass effort to a provider only when that provider supports configurable reasoning effort; otherwise leave provider behaviour unchanged/default.
6. Effort never widens model authority, verification authority, write authority, or task eligibility.
7. Preserve all existing model selection, host selection, fallback, verification, quota and escalation logic.
8. Update the routing contract/config only where required to keep them truthful.
9. Add or adjust only the smallest relevant tests proving default mapping, explicit override, unsupported-provider fallback, and unchanged authority behaviour.
10. Commit only the required files.

## Model distribution

Do not add special-case routing logic for individual vendors in this task. The generic router should support the existing/current model lanes through their normal capability/provider registration.

The governing rule is:

```text
cheapest adequate authorised model + lowest adequate effort
```

If GLM-5.3-Flash is already executable through an existing provider/launcher path, it may be registered through that existing mechanism with the smallest configuration change. Do not build a new provider adapter or launcher solely for Flash. If it is not already executable, leave it as a follow-up rather than expanding this task.

## Acceptance

The task is complete when:

- a routed model job can resolve an optional effort alongside its model;
- complexity supplies the default effort;
- explicit effort override works;
- providers without effort support continue to work unchanged;
- no authority/verification behaviour changes;
- relevant tests pass;
- no duplicate routing subsystem is introduced.

Report: files changed, final model+effort rule, tests, any Flash blocker/follow-up, and commit SHA.
