---
artifact_type: workflow
task_schema: agent-task/v1
task_id: 2026-06-19-odysseus-routine-hygiene-and-provenance
title: Auto-flag zombies, apply cadence collapse, cloud-parity gate, provenance validator (P3/P4)
status: done
priority: medium
task_type: implementation
created_by: claude
created_at: 2026-06-19T00:00:00+01:00
executor: codex_subscription
execution_mode: handoff
requires_remote_compute: false
requires_local_model: false
requires_zotero: false
requires_mcp: false
requires_web: false
verification_route: V2_HUMAN_VERIFIED
risk_level: medium
approval_required: true
source_traceability_required: true
repo: tyecam1/obsidian-PhD
branch: ""
allowed_paths:
  - automation/review/agent-tasks/review/2026-06-19-odysseus-routine-hygiene-and-provenance.agent-task.md
  - automation/review/operator-decisions/**
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
  - automation/review/decision-packets/2026-06-15-agent-routine-relevance-pruning.decision-packet.md
  - automation/review/operator-decisions/2026-06-15-agent-routine-disable-actions.decision-card.md
  - automation/config/odysseus_skill_registry.yaml
outputs:
  - Scripts/automation/** (zombie detector + provenance validator rule)
  - automation/config/** (cadence + lifecycle updates)
  - automation/review/operator-decisions/2026-06-19-routine-cadence-and-cloud-parity.decision-card.md
  - automation/docs/current-capabilities.md
  - automation/docs/capability_manifest.json
result_path: automation/review/operator-decisions/2026-06-19-routine-cadence-and-cloud-parity.decision-card.md
review_report_path: automation/review/routine-reports/odysseus-interface-health/2026-06-22.odysseus-interface-health.json
handoff_model: codex
handoff_prompt_path: automation/review/agent-tasks/inbox/2026-06-19-odysseus-routine-hygiene-and-provenance.agent-task.md
operator_decision_path: automation/review/operator-decisions/2026-06-19-routine-cadence-and-cloud-parity.decision-card.md
linked_pr: ""
supersedes: []
duplicates:
  - 2026-06-15-audit-live-agent-routine-migration-state
  - 2026-06-15-implement-post-audit-agent-routine-convergence
notes: "Completed the bounded residual scope on 2026-06-22. Interface health now marks unverified Codex Cloud routines non-actuating; schedule attestation flags overdue active tasks and found none; existing provenance validation already fails closed on machine-derived trust tiers. The proposed cadence targets are absent from live Odysseus, so no schedule mutation was applied. Cowork remains unavailable and is deferred in the decision card."
completed_at: 2026-06-22T19:00:00+01:00
completed_by: codex_subscription
verification_verdict: pending-human-review
verification_by: codex
---

# Routine hygiene + provenance enforcement (P3/P4)

## Completion

The automated hygiene checks and human decision card now reflect live runtime evidence. No schedule was silently changed or disabled.

## Source

Review `…/2026-06-19-odysseus-automatic-process-improvement-review.md` findings **P3** (zombies/cadence/cloud-parity caught only by one-off audits) and **P4** (machine provenance not enforced). Apply the existing relevance-pruning packet (`2026-06-15-agent-routine-relevance-pruning.decision-packet.md`).

## Scope (implement)

1. **Zombie auto-flag**: extend `odysseus-interface-health` to flag registered-but-no-recent-output routines each run (e.g. `daily-progress-review`, `weekly-supervision-packet`, `weekly-blog-post`).
2. **Cadence collapse**: apply the pruning packet — daily review-debt → weekly; weekly research-engine-health + retrieval-readiness → a single monthly infra-readiness report. Update routine lifecycle/cadence config.
3. **Cloud-prompt-parity gate**: a `prompt_location: codex-cloud` entry (incl. `opus-pr-review-and-automerge`) must pass a parity attestation before counting as live; until then mark non-actuating. Keep automerge disabled (no-autonomous-merge invariant).
4. **Provenance validator rule**: validator asserts overnight-worker / extraction outputs carry the correct trust tier (`extraction-support-material`/`quarantined-extraction-derived`); fail closed on missing/elevated provenance.

## Guardrails

- Do not silently delete or disable any live schedule; surface disables/cadence changes as a decision card for human action.
- No autonomous merge; stage branch + draft PR.

## Capability truth (mandatory)

Update `current-capabilities.md` + `capability_manifest.json`; run `python -m unittest Scripts.automation.tests.test_capability_truth_contracts`.

## Acceptance criteria

- Interface-health auto-flags zombies; tested.
- Cadence collapses applied in config; reflected in attestation.
- Cloud-parity gate marks unverified codex-cloud entries non-actuating; automerge stays disabled.
- Provenance validator fails closed on mistier; tested.
- Decision card lists the disable/cadence actions for human approval. Capability docs updated; truth tests pass. No canonical/Zotero mutation.
