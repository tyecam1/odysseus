---
title: Estate agent-task backlog execution contract
status: proposed-execution-contract
owner: odysseus
as_of: 2026-09-28
scope: registered repository agent-task queues
initializer: estate-backlog-loop v1
---

# Estate agent-task backlog execution contract

## Purpose

Continuously reduce the **existing, authorised** agent-task backlog across registered repositories. A Sonnet-class coordinator at medium effort selects and reconciles bounded work; cheaper qualified tools and workers perform it. Sol and Opus provide complementary, independent planning/review when actually reachable and justified.

This is a **session operating contract**, not a new scheduler, queue, router, lease, state database, or permission grant. It does not make cloud sessions into a qualified Odysseus worker merely by naming them. The existing [routing contract](aoteru-model-host-routing-contract.md), [estate execution contract](aoteru-estate-execution-contract.md), repository instructions, task gates, and live runtime take precedence. The matching immutable launch prompt is registered under `estate-backlog-loop` in `config/initialising-prompts.yaml`.

## Authority and startup

1. Resolve the registered initialiser by ID/version. Read live `AGENTS.md`, per-repo `CLAUDE.md`/`AGENTS.md`, task queue rules, branch/HEAD, open PRs, implementation and evidence before acting. Use `config/repositories.yaml` to discover repositories; do not infer a domain queue from registration alone.
2. Call `aoteru preflight "<bounded task>" --repo <repo-id>` or the authenticated `POST /api/estate/preflight` **before every substantive unit**. Follow the live route recommendation. A GitHub connection or hosted Claude checkout does not establish access to the private Odysseus backend, host tools, Sol CLI, write lease or local experiment files. If preflight cannot be reached, perform only non-mutating reconnaissance and prepare a precise handoff; never fabricate an approval or route.
3. Odysseus owns shared execution/routing/leases/task backend; each domain owns its research/household/ROS task content. In particular, `obsidian-PhD` owns PhD task and scientific state, `misumi` owns personal policy, and `s2-e1-ros2-measurement-spine` owns executable ROS software. Never transplant these authorities.
4. A general instruction to exhaust the backlog does **not** override an individual task's `approval_required`, `verification_route`, denied paths, clinical/research/physical/human-only gates, protected-branch policy, or existing claims. No direct canonical writes, PR merges, destructive actions, credentials/SSO, purchases, hardware operation, or deployment without the exact applicable authority.
5. Reconcile migrated/stale task paths with the **current** canonical owner and live code. Record contradictions as a proposed bounded correction; do not treat historical output paths as permission to recreate old backend capabilities in the PhD vault.

## Coordination and consultation

- **Coordinator:** Sonnet-class, medium effort where selectable. It handles intent, frontier ordering, bounded task packets, dependency reconciliation, independent-review dispatch, conflict resolution, and compact handoffs; it should not consume its whole context doing deterministic scans or routine edits.
- **Workers:** deterministic scripts/tests first; qualified local/low-cost models for bounded extraction, inventory and mechanical analysis; Codex/other qualified implementation lanes for code when eligible. Choose from **live** router evidence, not assumed provider rankings. One implementation owner per task/worktree. Parallelise only independently readable units or isolated writes with separate authorised leases and verification.
- **Initial complementary consultations:** after reconstructing the estate frontier, request *one short, independent* Sol pass on dependency ordering, verification/authority risks and research-boundary implications, and *one short, independent* Opus pass on long-horizon decomposition, architectural collisions and omissions **when both have genuine authorised callable routes and the value warrants the cost**. Supply the same concise evidence manifest but distinct questions; do not share either answer with the other until both are captured. Sonnet reconciles conclusions against primary evidence; disagreement is not a vote.
- **Later consultations are triggered, not ceremonial.** Sol is a candidate for difficult engineering, rigorous review and consequential source/construct adjudication where the owning domain contract requires it. Opus is a candidate for frontier architectural uncertainty, long-horizon synthesis, or an explicitly required independent critique. Use whichever **qualified** model matches the decision; consult both again only if independent perspectives materially change a high-consequence outcome. Domain-specific rules (e.g. J1's Sol/Opus scientific gates) supersede these generic role suggestions.
- Discover invocation/identity from the real installed integration before dispatch. Sol is **not inherently callable inside Anthropic Claude Cloud**. A Claude-model label, GLM harness, or assistant claim does not establish an independent native Sol/Opus execution. If a required reviewer is unavailable, record its exact gate and continue other eligible units; do not let Sonnet self-adjudicate it.

## Continuous frontier loop

At startup and after each substantive outcome, rebuild a **compact live frontier** from each actual queue's `ready`, `inbox`, `running`, `review`, `blocked`, `done` and `rejected` records, plus associated issues/PRs, current branches and evidence. These remain the source of truth; no additional estate backlog file or score system is created.

For each work item:

1. Check exact task ID, current owner, canonical scope, duplicates/supersessions, existing PR/implementation, acceptance evidence, dependencies, current claim/lease and available host/data. An `inbox` item is not automatically approved or dependency-ready; a `ready` label does not establish cloud eligibility. Do not count a draft PR as completion.
2. Separate `executable`, `needs-triage`, `in-review`, `blocked`, `human/physical-only`, `already-complete-but-stale-state` and `closed` **as a derived view only**. Propose source-record corrections through its governed workflow. Preserve blocked items with named unblock conditions.
3. Prioritise actual external deadlines and the current PhD critical path, then dependency-unlocking work, then other high-priority verified-ready tasks; prefer an already started review/repair over a duplicate implementation. Respect the owner's priorities and stage restrictions. Do not invent a global score to overrule them.
4. Select the **smallest highest-value dependency-ready unit** and run its preflight. Verify credentials, tool/host eligibility, read/write scope, cost, qualification and exact approval. Acquire the existing ParkLease before any applicable repo mutation; cloud isolation is not a replacement lease. If authority is unavailable, do not write; produce a scoped patch/handoff or select another unit.
5. Execute bounded work, deterministic tests/source checks, then the required independent verification. Fix evidenced defects within the approved scope. If a route blocks, record its failure class, freshness and unblock/retry condition; choose a genuinely different permitted route or another independent ready unit. Do not repeatedly attempt unchanged 403/quota/lease failures or silently downgrade capability. Use the existing blocked-route recovery implementation if qualified; otherwise follow this discipline manually without claiming it is shipped.
6. Record actual result and evidence in the owning task/result/PR surfaces. Commit/push **only** under the permitted task branch and existing lease/approval policy; open a draft PR when permitted. Do not merge, mark a V2/V3 human gate passed, or promote scientific evidence on a worker's assertion. Release leases after worktree resolution and preserve recovery state after ambiguous outcomes.
7. Re-read affected source state and rerank the frontier; proceed to the next independent unit without waiting for the operator merely because one task is blocked, one commit was made, or a PR is open.

Use one owner for each mutable file/branch. An ambiguous remote process or execution result must be observed through the existing `EstateExecution` status path, **not** by issuing another `ask` as a pseudo-poll. Never fabricate concurrency, worktree cleanliness, test output or paid-model identity.

## Resource and credit discipline

This programme may use the user's confirmed **$100 promotional-credit balance only where the provider actually makes it eligible**. Check the account-specific credit scope, expiry and observed decrement; never assume that subscription usage, API credit and cloud-session usage are interchangeable. Do not auto-reload, permit paid spillover past the grant, or put credentials in Git.

- First perform one small useful pilot and verify the meter before opening many sessions. If an attributable remaining balance/cost signal is unavailable, record `budget_unknown` and pause **further paid expansion** for operator confirmation, while continuing deterministic/otherwise-authorised work.
- Treat $100 as an overall ceiling, retain approximately $10 for verification/recovery, and require a fresh operator decision before exceeding the usable balance or launching a large unexplained paid run. These are operational targets, **not a claim of provider-side enforcement**.
- Prefer a single Sonnet medium coordinator with compact task packets. Batch initial Sol/Opus strategic review once, not once per task; cap consultation scope and return concise verdicts. Reuse completed evidence and source pointers instead of replaying whole transcripts. Use tool/deterministic verification before paid review.
- Check resource consumption after the pilot and at each substantive checkpoint using whatever legitimate meter is actually accessible. Do not spend tokens merely to exhaust an allowance.

## Checkpoint, continuation and stopping

After each task and before any context/session limit, leave a concise resumption record in the **existing** owning progress/task/PR surfaces, not a new shadow queue:

`repo/ref/HEAD | task ID | current claim/lease | outcome/verification | actual files/PR | blocker/unblock trigger | observed usage | next executable unit`.

For the registered initializer, append its required session application trace and prompt-evolution event in Odysseus at closeout; preserve exact prompt version and do not invent an operator rating. If Odysseus write access is unavailable, return the trace as a proposed handoff rather than claim it was persisted.

Continue until there is **no safe, approved, dependency-ready executable unit**, the verified credit/resource ceiling is reached, a session/runtime limit demands a resumable handoff, or a genuine policy/credential/human/physical gate prevents further progress. Before voluntarily stopping, scan other registered queues for independent work. An individual completed stage, commit, PR, or blocked route is not a stop condition.

Report precisely one of: `all in-scope tasks verified closed`, `executable frontier exhausted; N blocked/review/human items remain`, `budget exhausted/unknown`, or `session paused with resumable next unit`. Never describe an exhausted executable frontier as the **entire backlog completed** while open or gated records remain.

## Cloud launch

Use the registered immutable `docs/initialising-prompts/estate-backlog-loop-v1.md` in an authenticated, GitHub-connected Claude Code cloud session with Sonnet/medium selected when supported. The launch prompt activates this contract but does not prove that local `aoteru`, Sol, host, or private APIs are available in the hosted runtime. A cloud worker may conduct read-only assessment and submit reviewable proposals when those prerequisites are missing.
