# Persistent lazy usage: packet A implementation evidence

Status: core candidate; **not shipped or deployed**. The owning task remains
ready pending independent verification and its required live acceptance.

## Authority and implementation

Implementation used the existing admitted execution
`9ae16cbf-c605-4771-b590-c375b120c573`, under active repo lease
`f74969f3-4d05-4328-b56f-8cc84b23a74b`, bound to
`task/lazyusage-backend-persistence`. No second implementation dispatch or
lease was acquired. Start HEAD: `eeb8da2a298b9853b836e9e3fee276cab6c3091c`.
Controller retention is limited to final acceptance
(`nondelegation_reason: final_acceptance`).

The `aoteru` executable was absent, the bundled client had no configured
backend, and this sandbox denied HTTP/socket access and systemd bus access.
The existing Python preflight was exercised using a read-only source DB
snapshot copied to `/tmp`, with the deployed Python environment. It confirmed
the exact worktree's existing write authority, a healthy qualified lab worker,
and the existing Codex launch marker (provider state unknown while this
already-admitted execution was running). That snapshot is not a new dispatch
authorization or a claim of spare quota. No credentials were read or changed.

The additive `LazyUsageRun` model is created by the same `init_db()` /
`Base.metadata.create_all()` path as `EstateExecution`. Its partial unique
index prevents simultaneous non-terminal activations, including paused runs.
There is no destructive schema migration.

The runtime calls the existing portfolio functions locally, central routing
and preflight, ParkLease preparation/renewal/release, the write admission lane,
execution polling/reconciliation, and the worker's status/fence/cancel verbs.
The reserved execution ID is checkpointed before dispatch. Write admission
rechecks the activation in the existing serialized admission transaction.
Ambiguous dispatches are observed or quarantined, never replayed with a new ID.
Stop fences an unstarted spool before cancellation and preserves unresolved
worktree authority. Ordinary release is constrained to the exact owned lease.

Checkpoints contain task/criterion references, state, counters, review debt,
frontier/contract digests and next actions. Task bodies and model output remain
outside the run checkpoint. Provider quota diagnostics retain the original
error and reset/cooldown provenance. A successful model response alone never
moves an owning task to done.

## API and lifecycle

- `POST /api/lazy-usage/start`: `estate:execute`; accepts `repo_scope` and
  `budget_overrides`. Only registered frontier repo IDs are accepted; budgets
  are clamped to the specified ceilings. A concurrent activation returns 409.
- `GET /api/lazy-usage/status` and `/history`: `estate:read` or
  `estate:execute`, restricted to the caller's runs.
- `POST /api/lazy-usage/stop`, `/pause`, `/resume`: `estate:execute`, body
  `{"run_id": "..."}`; owner and legal-state checks apply. Terminal rows cannot
  resume or renew their budgets.

The existing app startup starts a 25-second observer when
`ODYSSEUS_LAZY_USAGE_OBSERVER` is unset/on. An empty run table performs no
frontier scan, model call or task dispatch. Only a persisted explicit activation
permits work. No new run is automatically created. No-progress runs park with
a five-minute condition recheck, while operator pauses require explicit resume.
Shutdown cancels the observer without erasing durable execution state.

Wall time is measured from persisted activation time, including pauses and
service restarts. Existing read-worker timeouts and durable write deadlines
are clamped to that wall-clock budget; existing bounded cancellation/cleanup
grace still applies. Paid/tool reservations are committed before admission;
reported child/restart totals are charged once. Provider quota errors park
dependent review debt while other eligible work can continue. Verified Codex
quota failover uses only a GLM read route qualified by the central router.

## Essential remaining dependency: child usage evidence

The current paid worker result does **not** expose authoritative aggregate
child paid/tool-call totals. The core records `usage_accounting_pending` and
parks further dispatch when those totals are absent; it never treats unknown
child usage as zero. Once the existing EstateExecution carries validated
`usage.paid_calls` and `usage.tool_calls` totals, a due recheck or explicit
resume accounts them before another attempt. This behavior has regression
coverage, including restarts and exactly-once accounting.

This does not certify a hard tool-call or nested-paid-call bound *inside* an
unmetered worker invocation. Existing worker-boundary metering/enforcement is
an essential delivery dependency under the task's no-new-harness constraint.
Do not advertise unattended bounded multi-task paid continuation until that
boundary is qualified. Review routes also require an actually qualified
approved reviewer identity; provider credentials or aliases do not qualify one.
Required independent review and owner acceptance remain visible as owed debt.

## Verification and outstanding live gates

Tests cover DB singleton activation and racing starts, ceiling clamps, all
five exhaustion conditions, terminal immutability, owner/scope authorization,
restart observation without redispatch, competing advances, stop before and
after admission, spool fencing, exact lease release/protection, quota debt and
qualified GLM read failover, missing child accounting, bounded frontier
rechecks, stale approval assessment, worker deadlines and observer cancellation.

The initial complete estate/portfolio/park/preflight selection returned
844 passed, 21 skipped and one failure: the pre-existing
`test_local_transport_subprocess_round_trip_against_fake_ollama` cannot create
its `127.0.0.1` HTTPServer in this socket-denied sandbox. Tests were not changed
to suppress that failure. A subsequent combined run with that single test
explicitly deselected returned 878 passed, 21 skipped, one deselected; further
runtime/router/control checks returned 195 passed. The final combined run on
the finished Python changes returned **883 passed, 21 skipped, one deselected**
in 175.82 seconds. `git diff --check` and syntax parsing of all changed Python
files also passed.

The sandbox also denies socketpair writes used for cross-thread asyncio
wakeup. API tests were run with a process-local selector timeout capped at
50 ms in the test launcher, allowing already-queued callbacks to run without
socket writes. Application code and repository test policy were unchanged.
Test DB/data roots were explicitly isolated under `/tmp` or in memory.

Not performed: qualified independent implementation review, live API start,
real owner-task delivery/merge/deploy, client disconnect demonstration, service
restart demonstration, or live cancellation/quota/lease-collision acceptance.
No live run was activated and no service/deployment policy was changed.

Rollback: disable the observer with `ODYSSEUS_LAZY_USAGE_OBSERVER=0` through
the existing release process, use stop to cancel an active activation through
the existing worker lane, and revert this packet's code through that release
process. Retain run/execution/lease records for audit; do not drop tables or
force-release unresolved worktrees. Deployment and rollback have not been
exercised by this packet.
