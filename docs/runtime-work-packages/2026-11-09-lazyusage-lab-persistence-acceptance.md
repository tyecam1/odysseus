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

## Live acceptance evidence (2026-11-11, post-deployment e940e4f4)

Deployment: lab service `odysseus-aoteru-lab.service` on branch `deploy/dev-20261111`
at merged dev `e940e4f4` (PR #278, squash of task/lazyusage-backend-persistence
308e655c/​cc9bf999/​7ac1d11d/​ae4b2c6c). `systemctl restart` at 2026-11-11T00:37:15Z,
`GET /api/health` → 200, `GET /api/lazy-usage/status` live (default-off: `state: null`).

Activation `ac965b02-0dac-407a-8178-56de9ce0b209` (operator, 2026-11-11T00:38:20Z,
budget overrides max_paid_calls=2, max_seconds=3600; all other ceilings default):

- **Laptop-independent execution:** the run advanced under the service's own
  lifecycle loop with no controller process attached — every observation was a
  fresh connectionless HTTP GET. It refreshed the real three-repo frontier
  (digest bf38d600…), selected real queued task
  `odysseus:ready/2026-10-02-misumi-persona-growth-background-collaboration.agent-task.md`,
  ran delegation preflight, and — with the codex provider gate recording
  `quota_exhausted` until 2026-11-13T17:03Z (verbatim provider text: "try again
  at Nov 13th, 2026 5:03 PM") — correctly refused to reroute to an unqualified
  lane, parked the task (`delegation preflight has no qualified route`), and
  scheduled a bounded recheck (00:43:37Z). Counters at park: 0 paid calls,
  2 tool calls, 1 no-delivery turn. No spin: one frontier refresh per recheck.
- **Controlled service restart mid-run:** `systemctl restart` at 00:39:11Z while
  the run was active. After restart: service active, health 200, run row and
  checkpoint byte-identical (same `recheck_at` 2026-11-11T00:43:37.846924, same
  current task and frontier digest), counters unchanged (0 paid / 2 tool),
  `in_flight_execution_id` null — no duplicate dispatch, no paid call, no
  mutation. The loop resumed from durable state on its own.
- **Bounded recheck:** the parked recheck fired after its stated time and the
  run re-evaluated the frontier (single refresh), demonstrating event-based
  recheck rather than polling.
- **Controls:** `am lazy resume` and `am lazy stop` exercised (see below);
  second-activation refusal while a non-terminal run exists is covered by
  tests (`test_..._activation_conflict`) and by the API contract.

Known limitations / owed items (truthful, not blockers to the feature):

- **Real write-lane delivery through a live activation remains owed to the
  codex provider reset (2026-11-13T17:03Z):** the only queued tasks the current
  frontier offers require codex-class routes; the run correctly parked rather
  than dispatching unqualified. Fixture-level end-to-end delivery (frontier →
  preflight → dispatch → verify → status transition) is proven in
  `tests/test_lazy_usage_acceptance.py`.
- **Sol re-review of packet D owed 2026-11-13T17:03Z** (same provider limit);
  packet D delta carries labelled same-family GLM-5.3 corroboration
  (DELTA-APPROVE, quoted evidence) per the standing fallback rule.
- **Write-lane finalize-commit defect (packet C):** the runner's `git commit`
  step fails in the production service context only (disposable live-unit
  diagnostics pass); stderr instrumentation shipped in e940e4f4 — reproduce via
  the next governed codex-write execution after the reset and fix from the
  captured evidence. Until then controller commits after S6.2 recovery remain
  the documented workaround (four occurrences, each with an `Aoteru-Execution`
  trailer).

Rollback (verified steps): `POST /api/lazy-usage/stop` terminalizes any active
run; `git revert e940e4f4` on dev redeployed via the deploy branch plus
`systemctl restart` restores pre-feature behaviour; the `lazy_usage_runs` table
is additive (no destructive migration). Deployment rollback to
`deploy/dev-20261109` was left in place as the named prior deploy branch.

## Owning-task execution, 2026-11-20 (acceptance remains incomplete)

This section supersedes any earlier implication that fixture delivery or a
finalised commit discharges the owning task's live acceptance. **Not shipped.**
The owner card stays `ready`; this writer cannot edit owner cards or approve
itself. No unrelated task was started or closed.

Authority and current state:

- Admission/source HEAD and registered `origin/dev`: `b38d3388947d46c4e93ed66183c25c9ec23dc1c9`
  (includes #294). The registered deployment checkout is
  `deploy/dev-20261119f` at that SHA. This is checkout evidence, not a fresh
  observation of the running service's loaded version. The local `dev` ref is
  stale (`75b24f72`); it was not treated as the current upstream head.
- Explicit activation `f4b6f653-be3e-4e6c-a62b-f8f117bea279`, Odysseus only;
  current admitted worker `4bdbd84c-ba79-41f8-a0f3-5aa7c4a092b4`, `codex-write`,
  lab `hz2-workstation`; matching active lease
  `c687ee33-1b3a-4d50-bc46-fed358d8a5c8` binds this worktree and admission SHA.
  These were read from production SQLite with `mode=ro`. No lease was acquired,
  changed or released by this worker.
- `aoteru preflight` was attempted (binary absent); the bundled HTTP client was
  unconfigured. Real `delegation_preflight` on a fresh read-only-source SQLite
  backup under `/tmp` confirmed the lab, deterministic lane and active write
  authority. A new Codex admission was refused because the **existing running
  worker's** launch outcome is not yet recorded. Work continued inside that
  admitted worker; no nested paid launch or substitute router was used.
- The selected active initializer is `estate-queue-priority-execution@v2`,
  unchanged. Controller retention: `nondelegation_reason: final_acceptance`.
  Remaining subscription capacity is unknown. Provider health is not remaining
  quota: the snapshot reports GLM/Claude `ok` and Codex's in-flight launch
  `unknown`, with an observation deadline, not a provider-stated reset.

### Bounded correction and deterministic evidence

The deployed runtime used `worker_finalize_attested` as a verification pass:
committing in-scope changes substituted for deterministic checks, even when
no test result existed. Three new regressions first failed against the old
code (one positive-control check passed). The correction:

- Finalisation still commits through the existing lease/worker mechanism and
  releases a resolved lease, but never establishes deterministic verification.
  Scope/finalisation failures still fail closed; a recorded passing gate is
  required separately. A failed gate cannot be overridden by a successful commit.
- A successful unverified write keeps a verification evidence gap, plus any
  independent-review debt. Its checkpoint says `verification_pending` and its
  ledger says `unverified`. The next activation excludes an unchanged card as
  `awaiting_verification`, so it does not pay to repeat implementation while
  verification of the existing execution is owed.
- The legacy `verify_attempt` helper also rejects exit-zero success prose.
  Acceptance plus an independent review still cannot make an unchecked commit
  a complete delivery.
- Provider fixture tests now use a disposable home for lane settings/login-link
  paths. Seven wider-test failures had exposed their attempt to write the real
  host's read-only lane config; no credentials were read or changed.

Final runtime, delivery, reliability, coordinator, preflight, provider-health
and finalisation selection: **319 passed, 1 warning** (77.27s).
The **four disposable acceptance tests passed**, including disconnect, recreation
of the loop over durable state, single dispatch and rollback behavior. These
remain fixture evidence. API tests required a temporary test-runner-only 50ms
selector-wait cap because this sandbox cannot wake the asyncio selector through
its socket path; repository assertions were unchanged. Interrupted preliminary
runs are not counted as passes.

### Live acceptance ledger and exact remaining work

| Required evidence | Current conclusion / next qualifying event |
| --- | --- |
| Real queued delivery with owner acceptance, tests, independent verification and trace | Still owed. This activation genuinely dispatched the owning queued task under its lease, but this worker has not completed its owner acceptance, merge or deployment. A terminal worker result is not delivery. |
| Client disconnect and existing-service restart without duplication | Historical 2026-11-11 parked-run restart evidence above remains useful. No fresh write-in-flight systemd restart or real delivery after disconnect is proven here. Recheck after controlled deployment/service access. |
| Protected gate, stale approval metadata, quota isolation, GLM write refusal, stale HEAD/lease collision, correct host | Existing deterministic tests exercise governance boundaries. The full required live demonstration remains owed; do not promote fixture results to live evidence. |
| Stop/cost, interruptions, transport loss and no orphan processes | Disposable tests cover lifecycle boundaries. Runtime child accounting also needs acceptance: `estate_worker._execution_usage` currently counts the writer and finalize/push decision files, **not all tools/model calls inside the writer**. Those values cannot establish the required total-child 150-tool/12-paid-call ceilings. Recheck on authoritative child-usage enforcement/evidence; no unlimited activation is authorised. |
| Qualified independent V3 acceptance of this delta | Owed. No independent reviewer was invoked. The central router lacks a complete approved-economy reviewer selector; Claude's configured advisory alias is Sonnet, Codex's resolver selects premium implementations, and GLM-Flash's coordinator launcher is not by itself review/currency qualification. This sandbox also cannot write the authoritative dispatch DB. Do not use premium substitution or same-family self-approval. Recheck when the controller can admit an actually qualified Haiku/Terra/GLM-Flash review with scope/identity evidence. |
| Merge, deployment, service health/version, activation state and actual outcome | Owed for this delta and required to close the owning task. HTTP to `127.0.0.1:7001` is unavailable inside this sandbox; systemd bus access returns `Operation not permitted`. These are execution-environment constraints, not proof the service is down or a new human gate. Existing release/controller authority must perform the normal finalization/review/release path. |

This worker did not stop or renew the parent activation, change host policy,
copy credentials, install a harness, restart a service or modify task authority.
The existing backend observes this same execution; do not submit a duplicate
implementation while it is unresolved. No additional billable activation is
implied by returning a worker result.

Rollback for this delta: stop an active run through the existing controls before
a governed code rollback; revert this packet's eventual commit and deploy the
previous reviewed service revision through the normal release path. No schema
migration was added. Existing `owed_reviews` and ledger entries must be retained;
older code does not enforce the new `awaiting_verification` exclusion. Code
rollback does not make unchecked commits verified. Activation rollback remains
`POST /api/lazy-usage/stop` with the existing audit/cancellation/lease protections.
