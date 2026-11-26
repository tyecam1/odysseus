---
artifact_type: agent-task
task_schema: agent-task/v2
task_id: 2026-11-26-read-only-liveness-and-dispatch-admission
title: "Read-only liveness timeouts and admission control instead of fixed deadlines and one-at-a-time dispatch"
status: ready
priority: high
task_type: design-and-staged-implementation
created_by: operator-directed-claude-code
created_at: 2026-11-26T01:30:00+00:00
executor: claude_subscription
execution_mode: staged-design-then-opt-in-implementation
architecture: single-plus-verifier
architecture_rationale: "One implementing worker with deterministic tests, then independent cross-family review."
single_agent_baseline: "One qualified worker implements and tests against live repository evidence."
execution_host: lab
context_budget: medium
requires_remote_compute: false
requires_local_model: false
requires_zotero: false
requires_mcp: false
requires_web: false
verification_route: V3_INDEPENDENT_MODEL_ADJUDICATION
risk_level: medium
approval_required: false
source_traceability_required: true
repo: tyecam1/odysseus
branch: ""
allowed_paths:
  - src/**
  - routes/**
  - companion/**
  - tests/**
  - docs/**
  - automation/review/**
denied_paths:
  - "**/.env"
  - "**/secrets/**"
  - "**/*credential*"
  - "**/*token*"
  - "**/*password*"
inputs:
  - AGENTS.md
  - docs/aoteru-model-host-routing-contract.md
result_path: docs/runtime-work-packages/2026-11-26-liveness-and-admission.md
verification_evidence:
  - result: pass
    commit_sha: 14d2e1901b88f90852d5e0492b57373f149097e5
    ref: "automation/review/2026-11-26-liveness-admission-handoff.md + docs/runtime-work-packages/2026-11-26-liveness-and-admission.md (design commit; controller check of 2026-11-26: files within allowed paths, Markdown only, all relative links resolve)"
    verified_by: "controller (claude-sonnet-5-5), deterministic link and scope check on the lab"
review_evidence:
  - verdict: approve
    reviewer_provider: claude-opus-5-5
    ref: "cross-family design review 2026-11-26, APPROVE_WITH_CONDITIONS; conditions recorded in docs/runtime-work-packages/2026-11-26-liveness-and-admission.md and below"
---

## Plan (written 2026-11-26 by the controller; step 0 is to verify it against HEAD)
**Goal in one line.** Replace the fixed read-only deadline with an inactivity timeout plus a ceiling that every layer agrees on, and settle advisory rows safely; admission control stays with the parallel-dispatch card.
**Already done / do not redo:** Write leases, host admission, provider pacing (src/provider_usage.py), `max_paid_calls`, failure backoff and stall detection already exist and stay. A raise to 900 s was reverted after review because it conflicted with the HTTP watchdog, the CLI default and transport headroom, and could leave advisory rows `running`. Do not repeat it. Admission control belongs to the ready card `2026-11-21-lazyusage-parallel-window-aware-dispatch`.
**Steps:**
0. Grep src/, routes/ and companion/ for the 180/210/240 s values, transport headroom, activation deadline, advisory-row persistence, replay fence and stall detection. Read the reverted change and check the 2026-11-21 card. Correct this plan.
1. Design (in the result doc): the inactivity window N, the absolute ceiling and each layer's bound. The layers are the HTTP watchdog (or a durable execution id the client polls), the CLI default, worker headroom including setup and cleanup, and the activation deadline recomputed after setup. Keep client bound > worker bound > setup + ceiling + cleanup. Get a cross-family design review before writing code.
2. One function derives all bounds from N and the ceiling, behind a switch that defaults off. Tests: the invariant holds across configurations; with the switch off, current values are unchanged.
3. Inactivity timer: backend output resets it, and the ceiling still applies. Fault tests (fake clock): a long read with continuous output completes past 180 s; a silent hang is killed after N.
4. Advisory rows: make ownership explicit. Settle a row only once the backend PID is proven gone, including after exceptions before terminal persistence, and keep the replay fence. Fault tests: a killed worker leaves no `running` row; replay is still refused.
5. Admission control (leases, per-host memory/GPU admission, provider pacing, failure backoff): write a design note under automation/review/ for the 2026-11-21 card; no implementation here.
6. Write docs/runtime-work-packages/2026-11-26-liveness-and-admission.md (findings, design, fault-test output, actual model). Run full pytest and stop with the switch off.
**Done when:**
- The card's four fault tests and the switch-off regression test pass.
- No admission-control code duplicates the 2026-11-21 card.
- Full suite green.
**Risks and stops:**
- If the HTTP layer cannot be bounded consistently, use the durable-id poll and stop for review; never ship bounds that disagree.
- Remove none of the safety limits that are not deadlines; touch no approval or delegation code.
- If the 2026-11-21 card is already in progress, coordinate with it rather than fork it.
**Ordering note:** Needs nothing first. The 2026-11-21 card should follow it, because parallel dispatch multiplies the advisory-row risk. Unblocks long read-only runs.


## Design review conditions (binding; plan step 1 is done and approved with these)

1. Lost-acknowledgement recovery needs a CLIENT-generated idempotency key (UUIDv4) sent with the submit, stored unique on the execution row with a payload hash: same key and hash returns the existing row, same key with a different hash is 409, and a resubmission never charges `max_paid_calls` twice. Test it.
2. Polling is used only when the submit response explicitly says polling is supported; otherwise use the legacy bounds and never resubmit automatically (an older server or a rollback would otherwise spend twice). Roll back in this order: switch off, let in-flight ids reach a terminal state, then revert code. Schema changes are additive; test that the old reconciler leaves new-format rows alone.
3. N = 180 s is unproven for Codex: before opting Codex in, measure the longest silent gap between output events in real lab Codex runs, using the exact invocation through a pipe (not a pty), and set N above it with margin. Start with Codex only; GLM and Claude are refused before admission until a reviewed streaming adapter exists.
4. Cite the activation stall-detection threshold and add it to the ordering invariant: either it exceeds T, or it reads activity from the row. Do not repeat the conflict that got 365a6c76 reverted.
5. Stage it smaller for one lab host. Drop for stage 1: the dedicated runner, the cgroup, new principal binding. Instead run the provider in its own session (setsid); record host, boot_id, PID and /proc start time on the row; settle by conditional update in `finally` once the process group is empty; a restarted control plane's reconciler kills the orphaned group and records an interrupted run with unknown usage. A changed boot_id counts as proof the process is gone (otherwise unresolved rows hold occupancy forever and can deadlock the parallel-dispatch card). Existing route auth plus unguessable ids suffices. Add a cgroup only if a test shows descendants escaping the process group. Liveness mode is Linux lab only; the Windows home worker is refused before admission.
6. State what drives the run after submit returns (the control-plane thread holding the transport) and add a fault test that restarts the control plane mid-run, not only one that kills the runner.
7. Anchor the transport bound: the transport timeout is the remaining W measured from durable admission, plus 15 s. Keep the submit request short (30 s or less); H need not appear in the CLI formula.
8. Make the status claims evidence-backed: commit the bound-arithmetic script and its values or drop the claim; cite the file and function of the claim-or-abort and quiescence primitives or mark them unverified; record the author's actual model from Codex's `model:` line; reconcile the card showing `ready` while a lease and execution exist for it.

Start at plan step 2, staged smaller as condition 5 says, behind the default-off switch.
---

# Liveness timeouts and admission control

## Why

The owner (2026-11-26): deadlines and time limits are not consequential and agents are ordered only by priority. A live run was cut off at the fixed 180 s read-only deadline while Codex was still reading a repository. A first attempt (raise it to 900 s) was reverted after independent review found it conflicts with the HTTP watchdog (210 s, plus the CLI's 240 s default), with worker transport headroom (catalogue lookups can use most of the headroom before inference starts, so transport can kill the worker during timeout cleanup), and with advisory-row reconciliation (an exception before terminal persistence leaves a row `running` while the backend PID lives).

## Outcome (design first, then implementation behind a switch)

1. Replace the fixed read-only deadline with an **inactivity timeout** (no output for N minutes) plus a generous absolute ceiling, applied end to end: the HTTP watchdog (or a durable execution id so a client can poll), the CLI default, the worker headroom including setup and cleanup, and the activation deadline carried to launch and recomputed after setup.
2. Make advisory ownership and completion explicit so a row is settled after proven quiescence and the replay fence is preserved.
3. **Admission control instead of "one in flight per run"**: parallel dispatch bounded only by safety, namely write leases (no two writers on overlapping paths), per-host memory and GPU admission, provider usage-window pacing and failure backoff. The existing ready card `2026-11-21-lazyusage-parallel-window-aware-dispatch` is the vehicle; reuse it, do not duplicate it.
4. Keep the safety limits that are not deadlines: write leases, host admission, provider pacing, `max_paid_calls`, failure backoff, stall detection.

## Verification

Fault tests: a long read that keeps producing output completes; a silent hang is killed and its row settled; the HTTP client and worker bounds agree; a killed worker leaves no `running` advisory row.

## Rules that apply to this card (owner standing rules, 2026-11-06 and 2026-11-26)

- Internal Odysseus work only, through the normal branch, test, independent-review and PR lane. Sol review first (labelled GLM only if Sol is unavailable). Merge decisions follow the owner's merge rule.
- No new accounts, credentials, API keys, paid services, third-party dependencies or external writes. If a stage needs one, stop and leave a precise owner debt (`protected_handoff`); never work around it.
- Priority order is the only ordering. Do not add deadlines, time-boxes or concurrency caps of your own.
- Never touch owner approval, delegation or card-approval code paths except where this card names them, and never widen what a model may approve.
- Record the actual model used in every verification record.
