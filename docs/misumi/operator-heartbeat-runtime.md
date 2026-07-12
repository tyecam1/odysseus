# Misumi operator conference and heartbeat runtime

Status: implementation scaffold, proposal-only by default  
Scope: Odysseus backend runtime for Misumi/Aoteru operator truthfulness

## Root cause fixed by this contract

The current Misumi/Odysseus behaviour can surface persona consultations and memory handoffs, but that is not the same thing as a durable Operator conference. If Aoteru says the Operator is checking running loops, there must be an event with a lifecycle. Otherwise the system is roleplaying an affordance.

This runtime introduces that missing lifecycle:

1. Aoteru or another persona creates an operator conference event.
2. The event is stored in append-only JSONL with `pending` status.
3. The interface or CLI can list the pending event.
4. The Operator responds through a route or CLI command.
5. The event becomes `responded`, or explicitly `expired`/`cancelled`.
6. Aoteru must report timeout honestly if no response exists.

## Operator conference schema

Stored under `data/misumi/runtime/operator_conferences.jsonl`.

Required fields:

- `event_id` / `id`
- `requesting_persona`
- `reason`
- `context_summary`
- `urgency`
- `created_at`
- `updated_at`
- `status`: `pending`, `responded`, `expired`, or `cancelled`
- `timeout_seconds`
- `expires_at`
- `session_id`
- `correlation_id`
- `response`
- `response_payload`
- `responder`
- `writes_allowed: false`

## Heartbeat runtime

The heartbeat is a bounded loop registry, not a free-running self-modifier. Every loop is proposal-only by default and produces artifacts under:

`data/misumi/runtime/heartbeat/proposals/`

Registered loops:

- `interaction_friction_loop`
- `persona_contract_loop`
- `operator_handoff_loop`
- `usability_improvement_loop`
- `persona_function_loop`
- `regression_guard_loop`
- `proposal_consolidation_loop`

Each loop has:

- owner persona
- interval seconds
- timeout seconds
- max budget tokens
- enabled flag
- permission mode
- lock file
- last successful run
- last failed run
- last output artifact
- backend/provider status

The default environment value is safe:

```text
MISUMI_HEARTBEAT_ENABLED=0
```

Setting it to `1`, `true`, `yes`, or `on` only marks loops enabled in status. It does not grant production write authority.

## ASI/backend provider boundary

The runtime records provider metadata through server-side environment only:

- `MISUMI_HEARTBEAT_PROVIDER`
- `MISUMI_HEARTBEAT_MODEL`
- `MISUMI_HEARTBEAT_URL`
- `MISUMI_HEARTBEAT_TOKEN_ENV`

The token value is never stored, returned, or browser-exposed. The current implementation has a deterministic proposal generator and a provider-status seam. ASI/model proposal generation should attach behind this seam only after tests prove no canonical files or production permissions are mutated.

## Routes

Mount the route module in `app.py`:

```python
from routes.misumi_operator_runtime_routes import setup_misumi_operator_runtime_routes
app.include_router(setup_misumi_operator_runtime_routes())
```

Suggested placement: immediately after the existing `setup_misumi_routes(...)` include.

Routes:

```text
GET  /misumi/operator-conferences?status=pending
POST /misumi/operator-conferences
GET  /misumi/operator-conferences/{event_id}
POST /misumi/operator-conferences/{event_id}/respond
POST /misumi/operator-conferences/{event_id}/cancel
GET  /misumi/operator-conferences/metrics/summary
GET  /misumi/heartbeat/status
POST /misumi/heartbeat/run-once
GET  /misumi/heartbeat/proposals
```

Read routes accept normal authenticated sessions and API tokens with `misumi:read` or `chat`. Mutating operator responses and heartbeat run-once are admin-gated.

## CLI

```bash
python scripts/misumi_operator_runtime.py conferences create \
  --reason "Aoteru needs Operator confirmation before claiming loop status" \
  --context-summary "User asked what loops are running; no durable event existed."

python scripts/misumi_operator_runtime.py conferences list --status pending
python scripts/misumi_operator_runtime.py conferences respond <event_id> --response "No loop is running until heartbeat is started."

python scripts/misumi_operator_runtime.py heartbeat status
python scripts/misumi_operator_runtime.py heartbeat run-once operator_handoff_loop \
  --input-summary "Aoteru claimed operator status without event_id."
python scripts/misumi_operator_runtime.py heartbeat proposals
```

## Required interface behaviour

The Misumi interface should poll `/misumi/operator-conferences?status=pending` and `/misumi/heartbeat/status` through its existing authenticated/proxied Odysseus path.

When a pending event exists, show a large, readable Operator panel at 1024×768:

- requesting persona
- reason
- timeout
- response field
- respond/cancel controls

Do not show “Operator status” unless a real event is pending or responded.

## Safety constraints

The runtime enforces or records:

- no household writes
- no automatic deployment
- no silent persona overwrite
- no automatic permission expansion
- no token exposure to browser config
- no self-modifying code path
- every heartbeat artifact requires human ratification

## Known limitation

The connector-created branch adds the module, route surface, CLI, tests, and docs. The route include in `app.py` still needs to be applied in a checked-out working tree or by a small follow-up patch because connector-only whole-file rewrites of `app.py` are too risky for this large orchestrator file.
