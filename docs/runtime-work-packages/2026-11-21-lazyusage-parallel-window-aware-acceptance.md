# Parallel lazyUsage admission baseline

## Disposition

Enabling concurrency above one (plan steps 4 and 5) and the canary are blocked at the execution boundary; the WIP reservation, parked state and status work (steps 2, 3 and 6) are not (see the review below). The first two-slot canary requires advisory children that can be individually fenced or observed after a lost response or controller restart. The merged liveness design specifies this ownership, and the runtime still uses the controller PID for an advisory child. The two-write path also has a shared Codex launch constraint. The owner card remains `ready`. Runtime changes, feature acceptance, canary, merge and deployment are pending. [Owning task](../../automation/review/agent-tasks/ready/2026-11-21-lazyusage-parallel-window-aware-dispatch.agent-task.md) · [Liveness handoff](../../automation/review/2026-11-26-liveness-admission-handoff.md) · [Reviewed liveness design](2026-11-26-liveness-and-admission.md)

The task checkout, lab deployment checkout `deploy/dev-20261126c`, and lab `origin/dev` tracking ref resolved to `5498873c76c9932664c7ce18a5b006cfe3880c0e` on November 26. Local `dev` was `75b24f72`. The deployment checkout establishes a source revision. Verification of the running service's loaded build was unavailable because the sandbox could neither reach the loopback HTTP port nor query the systemd bus. The live SQLite ledger and local worker health were readable.

The backend already admitted activation `c989e02b-1355-498a-b2ed-58b55054e2c9`, with a recorded owner and all three repositories in scope. It linked the exact owner card and digest `e209b71d617423e6ed0bfe884cdd7c52a04edd557779da08ea845f6f229462e2` to execution `7609c0a7-cacd-4e63-b480-a56a220bc095`. The worker reported that ID in flight. Lease `6ef737c5-567d-494f-9b73-805a1055ee5d` bound this Odysseus worktree and branch to the Lab. The execution was running and its worktree unresolved. The task used `estate-queue-priority-execution@v2` and this already admitted Codex write lane. The exact serving model was absent from the execution's available provenance during the capture. Controller retention was for `architecture_judgement` and `final_acceptance`. [Initialiser](../initialising-prompts/estate-queue-priority-execution-v2.md) · [Worker contract](../aoteru-model-host-routing-contract.md)

`aoteru` was absent and the bundled client had no configured backend. The canonical Python preflight used live Lab worker health and a temporary projection of the live DB's routing, lease and execution metadata. It confirmed the lease and denied an additional Codex launch because `launch outcome not recorded`. This is an in-flight launch marker. Lab was eligible, and the registered Home worker transport failed DNS resolution. Preflight recommended Lab deterministic compute with no model alias. GLM-Flash had a launcher, and the registered Lab worker and current preflight denied that reviewer route as unqualified. The available estate Claude route uses Sonnet and no live route attested Haiku or Terra for this review. Independent implementation review remains owed when there is a candidate diff and a qualified cross-family lane. [Preflight](../../src/delegation_preflight.py) · [Estate host registry](../../config/estate.yaml) · [Provider registry](../../config/models.yaml) · [Review model policy](../subscription-model-currency-policy.md)

## Stage 0 observations

Three child intervals were linked to the current activation at 03:31:55 UTC. Their peak observed overlap was one. The windows below use the backend timestamps in UTC and exclude the advisory coordinator from child occupancy.

| Execution | Repository and lane | Start | End at capture | Execution and worktree |
| --- | --- | --- | --- | --- |
| `19fc4b65-c6a4-49bb-b0b1-264c5a1863a6` | Odysseus, Codex write | 02:46:51.660 | 02:56:42.695 | Succeeded, finalised |
| `4cd3896f-f55d-4cef-b3ca-2babde6ea3df` | Odysseus, Codex write | 02:57:29.791 | 03:27:05.822 | Succeeded, finalised |
| `7609c0a7-cacd-4e63-b480-a56a220bc095` | Odysseus, Codex write | 03:27:47.099 | Still running | Worktree unresolved |

From activation start at 02:46:24.153 to capture, 115.879 seconds fell outside the linked child intervals, in gaps of 27.506, 47.096 and 41.276 seconds. Those gaps may include planning, preparation, finalisation and observation. The checkpoint stores current reasons and bounded history, so the query cannot assign historical seconds to approval, quota, verification, lease conflict or lack of eligible work. Current skipped reasons were one `attempted_this_activation` and one `awaiting_owner_acceptance`. The current ledger held 13 approval, five verification, five independent-review and three owner-acceptance entries in `owed_reviews`. These count gate entries, and a card may carry several. The activation charged four paid dispatches. Two successful worker intervals establish worker progress, with owner acceptance and any required shipping gates tracked independently.

Over the preceding seven days, 18 recorded activations reported 45 paid dispatches in total. Twelve ended on a ceiling, five were stopped by the operator, and one was running. The ceiling reasons were `max_paid_calls` (7), `max_seconds` (2), `max_no_delivery_turns` (1), `max_repeat_failures` (1) and `max_tool_calls` (1). Historical skipped-state timestamps and eligible idle time were unavailable. The latest routing rows exposed a Codex launch marker and earlier successful Claude and GLM outcomes. At capture the single active lease was Odysseus's, with no current lease collision visible. The evidence does not establish a historical collision or provider refusal rate.

The Lab's three registered checkouts were available. Their Git metadata showed 25 Odysseus `ready` cards, 11 Misumi cards in its five execution and review buckets at `4e25918542ef6a11161c71b489e876273d2fbb0d`, and 24 PhD `running`, `ready` or `review` cards at `e5f3c282a5e4c63e2eba189c990cd2e540c09a23`. These are file counts. The backend supplied the live claim for the selected Odysseus card. Accepted backlog totals for the other owner queues remain unverified. [Repository registry](../../config/repositories.yaml) · [Queue layout](../../scripts/agentic_portfolio.py)

At 03:29:49 UTC, the trusted Codex usage reader returned unknown. Its non-billable CLI read closed the stream and the authorised rollout reader found no recent events. The Codex launch marker had an observation deadline of 04:12:47.920 UTC, which came from router bookkeeping. Claude and GLM published no headless allowance in the existing readers. All three therefore had unknown remaining five-hour and weekly allowance and unknown provider-stated reset in this capture. `glm` and `glm-flash` share the router's GLM reservation. No paid usage probe was run. [Usage reader](../../src/provider_usage.py) · [Provider launch admission](../../src/estate_router.py#L185)

### Read-only query provenance

The SQLite connection used `mode=ro`, with the capture window and activation ID bound as parameters. The query set used for the baseline follows. The interval query filters inherited execution references by the activation's start time. Its start and end timestamps measure worker occupancy where those timestamps exist.

```sql
SELECT id, state, started_at, json_extract(checkpoint, '$.phase'),
       json_extract(checkpoint, '$.in_flight_execution_id'),
       json_extract(counters, '$.paid_calls')
FROM lazy_usage_runs
WHERE state NOT IN ('completed', 'stopped', 'failed', 'budget_exhausted');

WITH ids(id) AS (
  SELECT json_extract(checkpoint, '$.in_flight_execution_id')
  FROM lazy_usage_runs WHERE id = :run_id
  UNION
  SELECT json_extract(j.value, '$.execution_id')
  FROM lazy_usage_runs r, json_each(r.checkpoint, '$.ledger') j
  WHERE r.id = :run_id
)
SELECT e.id, e.repo_id, e.provider, e.executor, e.lifecycle_state,
       e.started_at, e.finished_at, e.worktree_resolution
FROM ids JOIN estate_executions e USING (id)
WHERE e.submitted_at >= (SELECT started_at FROM lazy_usage_runs WHERE id = :run_id)
ORDER BY e.submitted_at;

SELECT j.value AS reason, count(*)
FROM lazy_usage_runs r, json_each(r.checkpoint, '$.skipped') j
WHERE r.id = :run_id GROUP BY reason;

SELECT json_extract(j.value, '$.gate') AS gate, count(*)
FROM lazy_usage_runs r, json_each(r.checkpoint, '$.owed_reviews') j
WHERE r.id = :run_id GROUP BY gate;

SELECT state, terminal_reason, count(*), sum(json_extract(counters, '$.paid_calls'))
FROM lazy_usage_runs
WHERE started_at >= datetime(:capture, '-7 days')
GROUP BY state, terminal_reason;

SELECT e.id, e.lifecycle_state, e.worktree_resolution, e.admission_head_sha,
       p.id, p.status, p.host_id, p.heartbeat_at,
       json_extract(r.checkpoint, '$.task_ref'), json_extract(r.checkpoint, '$.task_revision')
FROM estate_executions e JOIN park_leases p ON p.id = e.lease_id
JOIN lazy_usage_runs r ON json_extract(r.checkpoint, '$.in_flight_execution_id') = e.id
WHERE e.worktree_path = :worktree;

WITH ranked AS (
  SELECT executor, created_at, escalation_reason,
         row_number() OVER (PARTITION BY executor ORDER BY created_at DESC, id DESC) AS rank
  FROM routing_decisions WHERE task_class = 'provider_outcome'
)
SELECT executor, created_at, json_extract(escalation_reason, '$.provider_health.state'),
       json_extract(escalation_reason, '$.provider_health.retry_after'),
       json_extract(escalation_reason, '$.provider_health.retry_after_assumed')
FROM ranked WHERE rank = 1;
```

## Consequences for the implementation

- **Execution and stop.** `advance()` returns to observe one checkpointed execution and `_choose()` returns one feasible card. For a governed write, the lease transaction and activation guard run before the durable worker start. The status fence can abort a start the worker has yet to see, then observe the writer and finalisation units. An advisory row has `worker_pid=os.getpid()` and no durable worker handle. `_stop()` can only observe its synchronous caller. A restart or lost return may leave uncertainty about the paid child, and that PID supplies no proof of the child's quiescence. The first canary needs the reviewed handoff's durable per-advisory identity, launch fence and stop/restart observation. Recheck when that exact dependency has runtime and fault-test evidence. [Advance and advisory dispatch](../../src/lazy_usage_runtime.py#L1674) · [Current stop fence](../../src/lazy_usage_runtime.py#L1599) · [Governing write lane](../../src/estate_write_lane.py) · [Liveness review conditions](2026-11-26-liveness-and-admission.md#cross-family-design-review-2026-11-26)
- **Provider occupancy.** Codex read-only and Codex write share `_execute_codex_with_sandbox`. That function atomically reserves a provider launch outcome and clears it on an observed result. The next launch is refused while that outcome is pending, even when the new child has a different repository lease. The current qualified write lane is Codex only. Another repository, a second lease or a favourable window reading cannot establish capacity for the two-write test. Enable that phase only with qualified capacity and an independently verified change at the existing admission authority. [Shared provider reservation](../../src/estate_router.py#L185) · [Shared launch path](../../src/estate_router.py#L1503) · [Feasibility gate](../../src/lazy_usage_runtime.py#L788)
- **Owner WIP.** `/api/lazy-usage/start` resolves the request owner and `LazyUsageRun.created_by` persists it across clients. Opt-in requires a real authenticated owner because the shared route helper can return the `api-token` placeholder. Current `EstateExecution` rows lack a durable principal and canonical card binding. A generic estate run authorises a caller but its envelope lacks card identity. The cap needs a transactional reservation at the existing owner-card admission boundary, with compatibility checks for other authorised task clients that advance those same cards. A review debt row, a bucket move, or a generic `acceptance_evidence` entry is insufficient by itself to release a WIP reservation. Use exact-revision worker and owner evidence and require any merge or deployment evidence called for by that card. Establish a protected wait from recorded owner authority before allowing a parked item to free an active slot. No parking inference was made from the observed 26 debts. [Authenticated start and status](../../routes/lazy_usage_routes.py) · [Scope owner](../../routes/estate_routing_routes.py#L80) · [Durable execution and activation models](../../core/database.py#L958) · [Acceptance stages](../../src/lazy_usage_runtime.py#L1070)
- **Usage and status.** Activation accounting, advisor checkpoints, owner-ledger approvals, `ungrounded_local_executor` and repository lease protections already exist. The provider-stated window check is called by `advance()` immediately before dispatch. The router independently enforces launch health and the shared provider reservation. Concurrency must reserve headroom for each child and settle it once, including unknown-usage fences. The existing status response is displayed as JSON by `am lazy status`, so an owner-scoped backend status field can surface the cap, parked count, per-item stage and denial reason through the current client. [Window check](../../src/lazy_usage_runtime.py#L1830) · [Advisor](../../src/lazy_usage_advisor.py) · [Owner ledger](../../src/owner_ledger.py) · [Status client](../../companion/laptop_client/aoteru.py#L558)

## Acceptance and rollout debt

In a disposable SQLite fixture at HEAD, an `after_commit` hook invoked `stop_run()` from a separate session immediately after the advisory row became durable. The row had the controller PID and no worker handle. The recorded sequence was `stop committed: stopping`, then `router called: stopping`. Both the router call and worker observation were stubbed. This demonstrates an existing launch window after the committed stop. Widening advisory occupancy would carry that gap into both slots. [Advisory dispatch](../../src/lazy_usage_runtime.py#L1870) · [Stop](../../src/lazy_usage_runtime.py#L1599)

The November 21 review gate was rechecked against exact commit `129540ec5f6f4a55c061fffc3937eecc5a442a64`. That change removed the isolated `CLAUDE_CONFIG_DIR` with `disableAllHooks`, substituted `--safe-mode --restricted` and changed its test to require those flags. Historical CI reported 9,843 passing tests, and independent GLM-5.3 review rejected the change. The commit is outside `origin/dev` ancestry. HEAD still has the isolation and the assertion. This is historical independent evidence, and any implementation for this card will require its own head-pinned independent review. [Reliability acceptance record](2026-11-19-lazyusage-reliability-acceptance.md#activation-fda677a6-2026-11-21-a-delivery-the-independent-review-rejected) · [Current guard](../../src/estate_router.py#L1884) · [Guard test](../../tests/test_provider_usage.py#L294)

An isolated call to `evidence_stages()` with that exact rejecting review, a deterministic pass, successful finalisation and synthetic owner acceptance still returned `complete=false`. Eighteen focused baseline tests passed for stop, restart, activation races, provider launch reservation, accounting, Claude isolation and evidence gates. The 62 provider-window tests also passed in isolation. All seven SQL queries executed against the read-only backend and the relative source paths resolved. Full-suite and two-child verification are pending. This sandbox denies local socket-pair sends used by asyncio, and the live ledger shows an active writer on the Lab. [Runtime tests](../../tests/test_lazy_usage_runtime.py) · [Reliability tests](../../tests/test_lazy_usage_reliability.py) · [Provider window tests](../../tests/test_provider_usage_live.py) · [Suite isolation incident](2026-11-19-lazyusage-reliability-acceptance.md#controller-mistakes-and-learnings-2026-11-19-to-2026-11-21)

After the advisory ownership dependency is verified, compare equivalent disposable or read-only cards at concurrency one and two. Require two unique overlapping child IDs, at most two active owner cards, independent sibling settlement, and worker or process evidence for every abandoned or cancelled child. Exercise restart and stop with both occupied and verify no paid call replays. Record provider pool observations, elapsed time, false collisions, unresolved children and exact evidence debts. Advance to distinct-repo low-risk writes only with qualified provider capacity, passing deterministic checks, independent review and the normal owner gates. Rollback for an implemented canary lowers concurrency to one for new admissions and lets existing child IDs reconcile under their original fences before any code revert.

## Cross-family review (2026-11-26)

Reviewer: claude-opus-5-5 (Claude family; the author is Codex, GPT family, so the review is independent). Verdict: **APPROVE_WITH_CONDITIONS**. The baseline is an honest, well-evidenced document that states its own limits; the conditions below correct its disposition and set the next dispatch:

1. The disposition is corrected: only enabling concurrency above 1 (plan steps 4-5) and the canary are blocked at the execution boundary, because each advisory child holds only the controller PID and has no worker handle (the liveness design, merged and reviewed, specifies the fix). The WIP reservation, the durable parked state and the status surface (plan steps 2, 3 and 6) do not touch advisory launch or stop and are useful with one execution at a time, so they are NOT blocked.
2. The shared Codex launch reservation rules out the two-write phase of the canary while Codex is the only qualified write lane. Rewrite the canary's write phase so it requires either a second qualified write lane or a separately reviewed per-child Codex reservation.
3. Evidence nits to fix when the document is next touched: state the timestamp precision used (displayed gaps subtract to 27.507 and 41.277, sum 115.878, not 115.879); explain why four paid dispatches were charged for three children; record the author's actual model (step 7 and the latest-model rule); file the launch-after-stop window seen in the document's own fixture test as a defect against the liveness work.
4. NEXT DISPATCH of this card: implement plan steps 2, 3 and 6 with the cap OFF by default. A transactional reservation keyed on `LazyUsageRun.created_by` plus canonical `repo_id/task_id`, taken at the existing card-admission boundary before the lease transaction; refuse opt-in when the principal is the `api-token` placeholder; release a slot only when `evidence_stages()` is complete at the exact revision; add the plan's tests and a status field. Leave steps 4-5 until advisory ownership has runtime and fault-test evidence.

Controller verification of this document commit (`ddb8226c`): the one changed file is inside the card's allowed paths, is Markdown only, and every relative link resolves at HEAD. This verifies the document only; no runtime behaviour changed.
