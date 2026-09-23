---
artifact_type: agent-task
task_schema: agent-task/v2
task_id: 2026-09-22-odysseus-stage3-5-convergence-repair
title: "Repair Odysseus multihost stages 3-5 before lifecycle work"
status: done
migrated_from_repo: tyecam1/obsidian-PhD
migrated_from_pr: 568
migration_note: "Task executed before repository-ownership migration; retained here as backend provenance."
priority: high
task_type: implementation-repair
created_by: gpt-5.6-sol
created_at: 2026-09-22T21:20:00+01:00
updated_at: 2026-09-22T21:20:00+01:00
executor: claude_subscription
execution_mode: review-first
architecture: single
architecture_rationale: "The Opus multihost plan remains valid. This task repairs bounded implementation defects in Stages 3-5 without reopening architecture or entering Stage 6."
single_agent_baseline: "One fresh Sonnet session should inspect the live branch, repair the confirmed defects, run regression tests, and stop."
execution_host: compute-box
context_budget: medium
coordination_reason: "Use the existing implementation branch/worktree, but a fresh Sonnet session, to prevent continuation momentum into Stage 6."
requires_remote_compute: true
requires_local_model: false
requires_zotero: false
requires_mcp: false
requires_web: false
verification_route: V2_HUMAN_VERIFIED
risk_level: high
approval_required: true
source_traceability_required: true
repo: tyecam1/odysseus
branch: feat/multihost-stage1-3-20260922
allowed_paths:
  - src/estate_router.py
  - src/estate_worker.py
  - src/estate_worker_client.py
  - src/estate_worker_procs.py
  - src/estate_worker_protocol.py
  - docs/aoteru-home-worker-setup.md
  - docs/aoteru-multihost-execution-implementation-plan.md
  - tests/test_estate_router.py
  - tests/test_estate_worker.py
  - tests/test_estate_worker_client.py
  - tests/test_estate_worker_procs.py
  - tests/test_estate_worker_protocol.py
  - tests/**
denied_paths:
  - core/database.py
  - config/models.yaml
  - scripts/windows/odysseus-host.ps1
  - routes/**
  - companion/**
inputs:
  - tyecam1/odysseus branch feat/multihost-stage1-3-20260922 at/after e45ecc0806e13a11db7484824f57fc3edf65a44a
  - docs/aoteru-multihost-execution-implementation-plan.md
  - Stage 3 commit fb23b90124af176fe14c577010619146fb2e965b
  - Stage 4 commit c7e86922298625444833448f919d011cc3d637c0
  - Stage 5 commit e45ecc0806e13a11db7484824f57fc3edf65a44a
outputs:
  - bounded Stage 3-5 repair commits on feat/multihost-stage1-3-20260922
  - passing targeted worker/router/process tests
  - full tests/ comparison against pre-repair branch state
result_path: ""
review_report_path: ""
handoff_model: gpt-5.6-sol-independent-review
operator_decision_path: ""
supersedes: []
duplicates: []
notes: "Do not run or spend /ultrareview. Do not begin Stage 6. Home remains disabled. Preserve the existing Opus architecture."
---

# Repair Odysseus multihost Stages 3-5 before Stage 6

## Authority

Work from the live branch:

`feat/multihost-stage1-3-20260922`

at or after:

`e45ecc0806e13a11db7484824f57fc3edf65a44a`

Read and preserve the architecture in:

`docs/aoteru-multihost-execution-implementation-plan.md`

This is a **bounded convergence repair**. Do not redesign the worker architecture and do not begin Stage 6.

Use a fresh Sonnet session but the same implementation branch/worktree.

## Confirmed review findings to repair

### 1. Truthful read-only execution semantics

Current Stage 3 behaviour can return `executed: true` even when `_dispatch_read_only()` fails before any host attests execution.

Required invariant:

> `executed: true` means an attested worker actually executed the task.

For both:
- local-model read-only execution; and
- paid/Codex read-only execution,

a transport/protocol/pre-execution worker failure with no attested execution host must return:

- `ok: false`;
- `executed: false`;
- `placement.executed_host: null`;
- truthful failure telemetry;
- no alternate-host or in-process fallback.

Replace stale tests that encode the old/wrong `executed: true` failure semantics. Add explicit regression coverage for both local and Codex read-only failure paths.

### 2. Make the Windows forced-command worker entrypoint actually viable

The current runbook documents a forced command of the form:

`python -m src.estate_worker --root E:\aoteru\odysseus-aoteru`

but Python must import `src.estate_worker` before `--root` can be parsed and applied. A normal Windows OpenSSH session does not guarantee that the current directory or `PYTHONPATH` makes `src` importable.

Implement/document the smallest robust launcher so the forced SSH command:

- works from an arbitrary SSH starting directory;
- explicitly enters/targets the dedicated worker checkout;
- uses that checkout's venv/interpreter;
- still invokes the same `aoteru-worker/1` worker;
- does not introduce a daemon/listener/scheduled task.

Add deterministic coverage of the entrypoint assumption where practical.

### 3. Make detached-spawn survival qualification executable

The current Stage 4 runbook asks the operator to set `AOTERU_WORKER_SELFTEST=1` in an SSH session, then call `call_worker()`.

That is not a valid propagation mechanism: each `call_worker()` invocation opens a fresh forced-command SSH session and does not inherit another session's environment.

Replace this with the smallest explicit operator-controlled self-test gate that:

- is disabled by default;
- enables only the bounded `noop-sleep` survival check;
- works through the real forced-command transport;
- is manually enabled and removed by the operator;
- cannot silently qualify `codex-write`.

A temporary home-local sentinel file under `~/.aoteru/` is acceptable if it is the simplest safe mechanism.

Update the runbook accordingly and test the gate semantics.

### 4. Add repo locality to host selection

For any task naming `repo`, host selection must verify that the repo resolves on that candidate host before selecting it.

Required behaviour:

- auto routing skips a healthy/model-capable host that lacks the requested repo and selects another qualified host that has it;
- explicit `requested_host` with the repo absent fails before execution;
- explicit placement is never silently substituted;
- no host is treated as repo-capable merely because the control-plane checkout has that repo.

Use worker-attested inventory or `repo.probe` as appropriate. Keep the design minimal and consistent with the Opus plan.

Add cross-host tests for:
- home healthy + model present + repo absent, lab repo present -> auto selects lab;
- requested home + repo absent -> refusal before dispatch;
- no candidate with repo -> truthful blocked route.

### 5. Keep route evidence bound to the selected host

Current Stage 5 paid-escalation fallback can compute `capability_resolutions` against `eligible[0]` and then select a different host for Codex.

A returned route must not mix:
- `route.host = H`; with
- alias/capability reasoning evaluated against some other host.

When a host is selected for escalation, the returned capability resolution, reason and telemetry must describe that selected host.

Add regression coverage with two eligible hosts whose model/Codex state differs.

### 6. Harden the Windows process API boundary

Before remote write lifecycle work depends on it:

- explicitly declare ctypes signatures/types for Win32 APIs used by the process layer, including `OpenProcess`, `GetProcessTimes`, `GetExitCodeProcess`, and `CloseHandle`;
- use pointer-safe HANDLE types;
- review the `is_alive(handle) -> taskkill /PID` PID-reuse claim;
- close the race if practical within this small module, or narrow the documented guarantee so it is truthful rather than absolute.

Do not expand this into a new Windows process framework.

## Guardrails

- Do **not** begin Stage 6.
- Do **not** modify EstateExecution or ParkLease schema/lifecycle semantics.
- Do **not** enable the home worker.
- Do **not** change `config/models.yaml`.
- Do **not** touch the household/Misumi deployment or `scripts/windows/odysseus-host.ps1`.
- Do **not** introduce alternate-host or backend-local execution fallback.
- Do **not** merge effort-routing/GLM work.
- Do **not** run or spend `/ultrareview`.
- Preserve one lab control plane and thin attested workers.
- If any review finding is incorrect against live code, report evidence instead of forcing a change.

## Verification

Run the directly affected worker/router/process tests after each coherent repair.

Then run the full `tests/` suite.

Compare any failures against the pre-repair branch state at `e45ecc0`; do not claim a new regression is pre-existing without reproducing it from that baseline.

At minimum ensure explicit tests exist for:

- local dispatch failure -> `executed: false`;
- Codex read-only dispatch failure -> `executed: false`;
- forced worker entrypoint independent of SSH starting cwd;
- self-test gate disabled by default and explicitly enabled only for `noop-sleep`;
- auto routing skips a host missing the requested repo;
- explicit requested host missing repo fails without substitution;
- escalation evidence belongs to the selected host;
- Windows HANDLE typing/process-liveness behaviour.

## Completion

Commit the repair in one or more logically separated commits on the same implementation branch and push it.

Then stop.

Report:

- commit SHA(s);
- files changed;
- exact targeted and full-suite results;
- any findings rejected with evidence;
- any remaining blocker;
- whether Stages 1-5 are now a sound base for Stage 6.

Do not proceed into Stage 6.
