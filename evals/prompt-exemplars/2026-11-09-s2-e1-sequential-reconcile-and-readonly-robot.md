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

- Targets one specific S2-E1 repo and stacked PRs #10/#11. Live refs, delivery states and tool permissions must be verified before application.
- Prompt is unexecuted and unevaluated. Candidate capture does not establish run success.
- The canonical generic planning template is owned by `tyecam1/obsidian-PhD/08-template/planning/sequential-experiment-execution.md`.

## Exact prompt

```text
Work from the registered checkout of `tyecam1/s2-e1-ros2-measurement-spine` via the governed lab SSH route. Execute **sequentially**.

**1. Reconcile (read-only):** Inspect live main, experiment branches, draft PRs #10/#11, registered local and Jetson worktrees, dirty/unpushed commits, and retained E1a raw-data manifests/SHA-256. Preserve all histories and data. Report what was directly verified versus inaccessible. Stop before writes if safe branch ancestry cannot be established.

**2. Finish the read-only uArm gate:** In an isolated worktree/branch, inspect and improve the existing uArm query-only script, tests and operator runbook in PR #11. Verify query codes and reply handling against the manufacturer; record raw responses, identifiers, units, timestamps, failures and serial-open reset risk. Add bounded synthetic tests and a reviewable PR against the reconciled branch. No hardware port opening, servo/pump/gripper/mode/motion commands, firmware changes or physical measurements. Treat firmware-reported position as non-independent evidence.

Stop at **human step 3: mount the unpowered uArm**. Report the reconciliation evidence, tested software state, PR and exact mounting handoff. Do not claim hardware verification or merge an unapproved PR.
```
