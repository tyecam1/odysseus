---
title: Durable lazy usage lab persistence acceptance
status: draft
owner: odysseus
task: 2026-11-09-lazyusage-bounded-persistent-continuation
updated_at: 2026-11-10
---

# Durable lazy usage lab persistence acceptance

## Purpose and status

Extend the existing Odysseus lab service with explicitly activated, bounded,
client-independent work. **Draft until live acceptance completes.** Disposable
fixtures establish local behavior only; they do not establish deployment or
real queued-task delivery. The owning task remains ready. Do not merge this
packet as part of this implementation session.

## Packet B authority and routing

Start HEAD: `308e655c`. Live source DB read confirmed the existing admitted
execution `9714754e-d6d9-486d-9269-4c196d7f8fd8`, active lease
`c951afdd-f371-4e9a-90ee-6372eb3f68f1`, and exact packet worktree/branch
`task/lazyusage-backend-persistence`. Packet A's earlier lease was already
released and was not reused. No lease was acquired and no second implementation
was dispatched by this worker.

The absent `aoteru` executable and unconfigured bundled client prevented HTTP
preflight. The backend Python preflight ran against a fresh read-only-source DB
snapshot copied to `/tmp` for the three bounded units (client, admin surface,
acceptance/docs). It confirmed the current write lease and eligible lab worker.
New Codex admission was unavailable because this admitted execution's launch
marker had no final outcome; this was not treated as additional quota or new
dispatch authority. Implementation continued inside that already-admitted
worker. Controller retention is final acceptance only
(`nondelegation_reason: final_acceptance`).

The initializer register was checked: active `estate-queue-priority-execution@v2`
is preserved as the backend policy reference. This bounded worker packet did
not invoke a new queue-selection initializer application. No application rating,
evolution event or independent-review verdict is invented. The central paid
provider registry lists Codex and GLM, with no qualified Haiku/Terra/GLM-Flash
review route demonstrated by this session; independent review remains owed.

## What was built

Packet A: `core/database.py` (`LazyUsageRun`), `src/lazy_usage_runtime.py`,
`routes/lazy_usage_routes.py`, and the existing service lifespan loop.
See [packet A evidence](2026-11-10-lazyusage-persistence-packet-a.md).

Packet B:

- `companion/laptop_client/aoteru.py`: checkout-free `am lazy` controls,
  S6 `am finalize`, and `am provider-health show/override`; JSON on stdout,
  compact run state, budget counters and owed-review count on stderr.
- `routes/lazy_usage_routes.py`: owned run lookup by optional `run_id`.
- `routes/estate_routing_routes.py`: provider-health read/admin override and
  S6 finalization HTTP adapters; finalization derives repo/host from the
  execution row and uses the existing control-plane authority checks.
- `src/estate_router.py`: serialized, append-only operator override evidence.
- `routes/api_token_routes.py`: dedicated `estate:admin` token scope.
- `.claude/skills/lazyUsage/SKILL.md`: backend entry-point wording only.
- `tests/test_lazy_usage_acceptance.py`: disposable DB, fixture delivery,
  disconnect, restart/single-dispatch and rollback assertions.
- `tests/test_estate_provider_override.py` and laptop-client tests: scope,
  identity, validation, audit, rate limit and request contracts.

## Activate, inspect and stop

Use the existing configured Odysseus service URL and bearer token; no new
configuration or secrets are stored. Mutating lazy verbs and finalization
require `estate:execute`; status/history require `estate:read` or
`estate:execute`. Runs are owner-scoped. Start without `--repo` selects the
existing registered three-repository scope. Budgets can only lower ceilings.

```sh
am lazy start --repo odysseus --budget max_paid_calls=2 --budget max_seconds=600
am lazy status
am lazy status RUN_ID
am lazy status --all
am lazy pause RUN_ID
am lazy resume RUN_ID
am lazy stop RUN_ID
am finalize EXECUTION_ID --message-file commit-message.txt
```

Omitting RUN_ID for pause/resume/stop selects the latest owned run. History
returns the backend's bounded default page (20 rows). Terminal budget exhaustion
requires a fresh explicit activation. A second non-terminal activation is refused.
Finalization is an explicit S6 commit/push operation on the recorded execution,
not a merge or permission to finalize unrelated work. Without a message file it
uses `Finalize governed estate execution`.

Provider state inspection and operator evidence:

```sh
am provider-health show codex
am provider-health override codex --reason 'Observed live lab Codex capacity; evidence reference ...'
```

Override requires an **`estate:admin` token owned by a current administrator**,
or the existing authenticated admin-session path. `estate:execute` alone is
insufficient, even for an admin owner. The row asserts operator-observed evidence;
it does not measure or fabricate capacity, qualify a worker/model, acquire a
lease, or bypass currency/permission checks. Only registered providers are
accepted. The reason is mandatory, bounded and audited with requesting identity
and token ID (never the bearer secret). Overrides append a `provider_outcome`
RoutingDecision with `ok`, no assumed reset, and the prefix
`operator-authorized override: `. A per-owner sliding window allows five
accepted attempts per minute. The existing audit history is retained; later
admitted launches and their outcomes govern subsequent gate decisions.

## Budget ceilings

| Budget key | Ceiling per activation |
| --- | --- |
| `max_seconds` | 14,400 seconds (4 hours) |
| `max_paid_calls` | 12 |
| `max_tool_calls` | 150 |
| `max_no_delivery_turns` | 8 consecutive turns |
| `max_repeat_failures` | 3 repeats |

Counters and deadlines survive restarts. Child usage must be reported; unknown
usage fences further dispatch rather than resetting spent-call accounting.
The initializer remains `estate-queue-priority-execution@v2` unchanged.

## Acceptance evidence

### Local scaffolding

Verified locally:

| Selection | Result |
| --- | --- |
| Separate `-m lazy_usage_acceptance tests/test_lazy_usage_acceptance.py` | 4 passed in 3.16s |
| Estate/laptop regression selection below | 427 passed in 76.12s |
| Final admin/auth selection after audit-identity hardening | 78 passed in 23.98s |
| Python syntax parsing and `git diff --check` | passed |

The regression command selected:

```sh
pytest -q tests/test_estate_provider_override.py tests/test_laptop_client.py \
  tests/test_lazy_usage_runtime.py tests/test_estate_routing_routes.py \
  tests/test_estate_router.py tests/test_estate_stage6_control.py \
  tests/test_provider_quota_health.py tests/test_delegation_preflight.py \
  tests/test_api_token_routes.py tests/test_api_token_user_route_gate.py
```

The final admin/auth rerun selected `test_estate_provider_override.py`,
`test_estate_routing_routes.py`, `test_api_token_routes.py` and
`test_api_token_user_route_gate.py`. Initial finalization-fixture failures
(missing required executor/provider fields) were corrected and rerun; no
test was skipped or deselected in these selections. Only existing SQLAlchemy
and Starlette deprecation warnings remain.

Execution used `/tmp/odysseus-glm-fallback-venv/bin/python`, explicit
`DATABASE_URL=sqlite:///:memory:` and isolated `ODYSSEUS_DATA_DIR` roots under
`/tmp`. As in packet A, sandbox socketpair writes prevent cross-thread asyncio
wakeup. The process-local launcher `/tmp/lazyusage-packet-b-pytest.py` caps
`selectors.EpollSelector.select` waits at 50ms before calling `pytest.main`;
application code and repository test policy are unchanged. The exact launcher
logic is:

```python
import selectors, sys, pytest
original_select = selectors.EpollSelector.select
def bounded_select(self, timeout=None):
    return original_select(self, 0.05 if timeout is None else min(timeout, 0.05))
selectors.EpollSelector.select = bounded_select
raise SystemExit(pytest.main(sys.argv[1:]))
```

The acceptance marker is `lazy_usage_acceptance`, run separately; no slow
designation is claimed without duration evidence. Fixture work really creates
and checks a disposable artifact and transitions its owner card. Its mocked
provider/host route is not production qualification. Restart coverage creates a
new service-loop task over the same DB, retaining one execution and cumulative
budgets. Live acceptance remains entirely outstanding below.

### Live results — required before accepting deployment

- TODO(live-delivery): real eligible low-risk owner task, preflight, lease,
  exact dispatch/model route, deterministic/independent verification, owner
  status transition and prompt-application trace.
- TODO(live-disconnect): client disconnect timestamps, independent continuation
  and actual delivered or advanced work/checkpoint.
- TODO(live-restart): controlled service restart, recovered checkpoint, retained
  budgets and proof of no duplicate mutation/tool/paid dispatch.
- TODO(live-governance): protected gate, stale approval metadata, unavailable
  reviewer while independent work proceeds, unqualified GLM write refusal,
  stale HEAD/lease collision rejection and correct provider/host selection.
- TODO(live-stop-cost): pause/resume, stop/cancel, all ceilings, empty frontier,
  repeating failure, process/transport interruption and no orphan workers.
- TODO(live-override): authenticated admin evidence, named-provider isolation,
  durable audit and renewed gate state; do not infer capacity from this doc.
- TODO(independent-review): qualified independent reviewer identity and verdict.
- TODO(deployment): normal release evidence, deployed commit/service version,
  health, activation state, actual worker route and task result.

## Rollback

Activation rollback: `POST /api/lazy-usage/stop` with `{"run_id":"RUN_ID"}`
(or `am lazy stop RUN_ID`), then observe status until the run row is terminal.
Keep the existing bounded cancellation, audit and unresolved-lease protections.

Code rollback: through the normal release process, `git revert -m 1 <merge-commit>`
for the merge commit, then `systemctl restart odysseus-aoteru-lab.service`.
Stop the activation and confirm its terminal run row before reverting code.
These are the activation and code rollback steps; no table deletion, record
rewrites, credential changes, forced lease release or second daemon is needed.

## Limitations and remaining debt

This packet is local implementation and acceptance scaffolding, unmerged and
undeployed. Mocked providers cannot prove real service restart safety, capacity,
independent review or live delivery. Loop recreation over the same disposable
DB simulates restart; it does not restart systemd. The existing service remains
opt-in, with no new daemon. Existing protected gates, qualification, write leases,
model currency, repository ownership and external publication gates still apply.

Commit finalization is an execution-environment dependency: `git add` was
refused with `Unable to create .../index.lock: Read-only file system` because
the sandbox exposes shared Git metadata read-only. Source changes are retained
in the packet worktree for the existing S6 controller finalization after this
execution is terminal. No branch ref, merge or deployment was changed here.
