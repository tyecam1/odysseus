---
artifact_type: workflow
task_schema: agent-task/v1
task_id: 2026-06-19-odysseus-git-single-writer-safety
title: Make Odysseus git upkeep single-writer and conflict-safe (P0)
status: done
priority: high
task_type: implementation
created_by: claude
created_at: 2026-06-19T00:00:00+01:00
executor: codex_subscription
execution_mode: handoff
requires_remote_compute: true
requires_local_model: false
requires_zotero: false
requires_mcp: false
requires_web: false
verification_route: V2_HUMAN_VERIFIED
risk_level: high
approval_required: true
source_traceability_required: true
repo: tyecam1/obsidian-PhD
branch: ""
allowed_paths:
  - automation/review/agent-tasks/review/2026-06-19-odysseus-git-single-writer-safety.agent-task.md
  - automation/review/decision-packets/**
  - automation/review/routine-reports/**
denied_paths:
  - 03-concept/**
  - 07-standards/**
  - 01-research-plan/**
  - 02-library/00-papers/**
  - 02-library/01-annotations/**
  - 02-library/02-evidence/**
  - 00-dashboards/**
inputs:
  - automation/review/architecture/2026-06-19-odysseus-automatic-process-improvement-review.md
  - automation/deploy/ubuntu/install_odysseus_remote_upkeep_task.sh
  - automation/review/routine-reports/odysseus-heartbeat/2026-06-15.heartbeat.json
  - automation/docs/obsidian-git-conflict-containment.md
outputs:
  - automation/review/routine-reports/odysseus-runtime/2026-06-22-compute-box-runtime-attestation.md
result_path: automation/review/routine-reports/odysseus-runtime/2026-06-22-compute-box-runtime-attestation.md
review_report_path: automation/review/routine-reports/odysseus-runtime/2026-06-22-compute-box-runtime-attestation.md
handoff_model: codex
handoff_prompt_path: automation/review/agent-tasks/inbox/2026-06-19-odysseus-git-single-writer-safety.agent-task.md
operator_decision_path: automation/review/decision-packets/2026-06-19-odysseus-autopull-pause.decision-packet.md
linked_pr: ""
supersedes: []
duplicates:
  - 2026-06-11-obsidian-git-conflict-containment
notes: "Verified on the authorised compute box on 2026-06-22. Auto-pull targets the clean vault-runtime checkout and already uses flock plus clean/detached/ahead/diverged/fast-forward gates. Audit and upkeep use separate checkouts; the dirty legacy vault is not an active target. No pause is recommended because the P0 premise is stale."
completed_at: 2026-06-22T19:00:00+01:00
completed_by: codex_subscription
verification_verdict: pending-human-review
verification_by: codex
---

# Make Odysseus git upkeep single-writer and conflict-safe (P0)

## Completion

Live service configuration, checkout state, scheduler runs and auto-pull logs were inspected over Tailscale SSH. Existing controls satisfy the implementation objective; the review report records why the requested pause is not supported by current evidence.

## Source

`automation/review/architecture/2026-06-19-odysseus-automatic-process-improvement-review.md` finding **P0**: a live "DRM Legacy Git Auto Pull Service" auto-pulls into a checkout recorded as conflict-laden (`/home/agent/projects/vault`), while concurrent agents write the same tree. Observed failure class this week: held `.git/index.lock`, a supervision file truncated mid-write, agent task files deleted under a writer, git writes failing.

## Objective

Eliminate concurrent-writer corruption of the vault git tree without enabling any new autonomous authority.

## Scope (implement on a branch; PR for human merge)

1. **Pre-pull clean-tree gate**: the upkeep/auto-pull path must refuse to pull when the working tree is dirty, mid-merge/rebase, or `.git/index.lock` is present. Fail closed with a recorded reason.
2. **Single-writer lease**: a repo-level advisory lock so only one automated git writer operates at a time; others wait or skip and log.
3. **Worktree-per-runner**: document/enforce that each automated runner uses its own worktree with a merge/PR gate, never a shared checkout.
4. **Decision packet** (review-side, in allowed scope) recommending the human **pause the auto-pull service** until `/home/agent/projects/vault` conflicts are resolved.

## Guardrails

- Vault write-scope is review-side only (allowed_paths). Code/config/doc changes are branch + draft-PR deliverables, not vault writes.
- No autonomous service start/stop and no autonomous merge (no-autonomous-merge invariant).

## Capability truth (mandatory, in the PR)

Update `current-capabilities.md` and `capability_manifest.json` in the same change and run `python -m unittest Scripts.automation.tests.test_capability_truth_contracts`.

## Acceptance criteria

- Pre-pull clean-tree gate + single-writer lease implemented with tests (on the branch).
- Worktree-per-runner convention documented/enforced.
- Decision packet recommends the auto-pull pause with rationale and the resolve-conflicts precondition.
- Capability docs updated; truth tests pass. Branch + draft PR opened; nothing merged. No canonical/Zotero mutation.
