---
exemplar_id: 2026-11-09-s2-e1-sequential-reconcile-and-readonly-robot
title: S2-E1 sequential agent-to-human experiment handoff
status: candidate
captured_at: 2026-11-09
capture_basis: operator-directed-workflow-persistence
source_surface: chatgpt-phd-research
source_reference: tyecam1/s2-e1-ros2-measurement-spine PR-11
task_context: S2-E1 unblocks uArm read-only connection while the lux sensor and metallic gripper are pending
applications: []
evaluations: []
supersedes: []
---

# Capture rationale

The user requested reusable **sequential** rather than separate parallel agent/human plans. This prompt couples a provenance-first research checkout gate to a hardware-free implementation gate and finishes at an explicit human physical handoff. Stored as a **candidate exemplar**, not a global session initializer or autonomous execution authority.

## Reusable behaviours

- One accountable owner and accepted evidence per dependent stage.
- Registered-checkout reconciliation before modification.
- Explicit distinction between software capability, firmware-reported data, physically observed state and permitted hardware action.
- Stop at the first required human mounting/authorisation gate.

## Task-specific assumptions and limitations

- Laptop-launched Claude Code: local checkout is the starting point, Jetson access is conditional on existing authorised SSH/host routing, and remote facts cannot be inferred from laptop state.
- Targets one specific S2-E1 repo and stacked PRs #10/#11. Live refs, delivery states and tool permissions must be verified before application.
- Prompt is unexecuted and unevaluated. Candidate capture does not establish run success.
- The canonical generic planning template is owned by `tyecam1/obsidian-PhD/08-template/planning/sequential-experiment-execution.md`.

## Exact prompt

```text
From my laptop, use the existing local checkout of `tyecam1/s2-e1-ros2-measurement-spine`. Verify cwd, Git remote, branch and dirty worktrees first; discover the registered checkout if needed. Use only existing authorised Odysseus/SSH access for Jetson inspection. Never assume the laptop checkout is the Jetson checkout.

Execute sequentially:

1. **Read-only reconciliation:** Inspect live `main`, experimental branches, draft PRs #10/#11, laptop and accessible Jetson checkouts/worktrees, dirty/unpushed commits, E1a raw evidence and checksum ledgers. Do not alter history or raw data. Clearly distinguish directly verified, ledger-only and inaccessible evidence. If safe branch ancestry is uncertain, stop before writes.
2. **Read-only uArm software gate:** Inspect PR #11's existing probe, tests, CI and mounting runbook before changing code. In an isolated worktree, fix only demonstrated defects or missing requirements; test allowlisted informational queries, raw/error logging, time/units, serial-reset risk and failure behaviour. If changes are justified, open a reviewable PR against the reconciled review branch, preserving the PR #10/#11 stack. Do not duplicate working tooling.

No serial-port opening, robot actuation, firmware changes, calibration measurements, motion commands or merges. If Jetson access is unavailable, report that limit and complete only safely isolated software checks.

Stop before **human step 3: mount the unpowered uArm**. Report findings, tests, PR (if needed), unresolved gates and precise physical handoff.
```
