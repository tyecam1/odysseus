# Implementation ledger: operator conference and heartbeat runtime

Date: 2026-07-12  
Branch: `codex/misumi-operator-heartbeat-20260712`  
Repo: `tyecam1/odysseus`

## Inspection findings

- `README.md` identifies `dev` as the current development branch.
- `app.py` mounts the existing Misumi compatibility/control-plane route surface through `routes.misumi_routes.setup_misumi_routes(...)`.
- `routes/misumi_routes.py` already implements `/misumi/respond`, `/misumi/status`, passive memory, pending handoffs, and bounded within-request persona consultation.
- Recent commit history shows merged PR #15, `feat(misumi): bounded within-request persona consultation`.
- The current consultation implementation returns `consulted`, `capsule_id`, and `handoff_ids` fields, which the Misumi interface can render as visiting personas.
- That implementation is useful but not equivalent to a durable Operator conference. A handoff can remain pending, but there is no explicit `pending/responded/expired/cancelled` operator-response lifecycle.

## Root cause

The non-responding Operator is caused by an interaction-contract mismatch:

- Aoteru can imply the Operator is checking or conferring.
- Odysseus can create memory handoffs and synchronous persona contributions.
- The interface can animate consultations.
- But no route currently guarantees that an Operator request creates a durable pending event that the Operator window can answer.

That makes “operator status” sound live when the underlying state is only memory/status decoration.

## Changes added on this branch

- `src/misumi_operator_runtime.py`
  - append-only `OperatorConferenceStore`
  - `pending/responded/expired/cancelled` lifecycle
  - explicit timeout expiry
  - proposal-only `HeartbeatRuntime`
  - seven bounded heartbeat loop manifests
  - server-side provider metadata seam
  - no production write path

- `routes/misumi_operator_runtime_routes.py`
  - route module for operator conferences and heartbeat status/run-once/proposals
  - read scopes for API tokens
  - admin gate for Operator responses and heartbeat run-once

- `scripts/misumi_operator_runtime.py`
  - CLI for creating/listing/responding/cancelling operator events
  - CLI for heartbeat status, run-once, and proposals

- `tests/test_misumi_operator_runtime.py`
  - covers conference lifecycle
  - covers explicit timeout
  - covers loop-state truthfulness
  - covers proposal-only heartbeat output
  - rejects unknown self-mutation loop IDs

- `docs/misumi/operator-heartbeat-runtime.md`
  - documents routes, CLI, schema, provider boundary, interface requirements, and limitations

## Safety constraints preserved

- no autonomous production deployment
- no canonical persona overwrite
- no permission expansion
- no token value returned by provider status
- no browser-visible secret path
- no household write path
- no self-modifying heartbeat loop
- every heartbeat run produces a proposal requiring human ratification

## Remaining host integration

The route include must be mounted in `app.py` after the existing Misumi route include:

```python
from routes.misumi_operator_runtime_routes import setup_misumi_operator_runtime_routes
app.include_router(setup_misumi_operator_runtime_routes())
```

This was not applied through the connector because `app.py` is a large orchestrator file and connector-only whole-file rewrites are the wrong risk trade-off. Apply it in a checked-out worktree and run tests before deployment.
