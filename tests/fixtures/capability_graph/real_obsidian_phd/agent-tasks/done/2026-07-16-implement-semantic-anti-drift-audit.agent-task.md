---
artifact_type: agent-task
task_schema: agent-task/v1
task_id: 2026-07-16-implement-semantic-anti-drift-audit
title: "Implement semantic anti-drift audit"
status: done
priority: high
task_type: orchestration
created_by: chatgpt
created_at: 2026-07-16T11:04:00+01:00
claimed_by: fable-sol-route-loop
claimed_at: 2026-07-17T13:37:30+01:00
completed_by: fable-sol-route-loop
completed_at: 2026-07-17T13:49:00+01:00
verification_verdict: accept
verification_by: human

executor: codex_subscription
execution_mode: handoff
requires_remote_compute: false
requires_local_model: false
requires_zotero: false
requires_mcp: false
requires_web: false

verification_route: V2_HUMAN_VERIFIED
risk_level: high
approval_required: true
source_traceability_required: true

repo: tyecam1/obsidian-PhD
branch: agent/karpathy-wiki-hardening-work-items
allowed_paths:
  - automation/review/**
  - automation/docs/**
  - Scripts/**
  - .github/**
denied_paths:
  - 03-concept/**
  - 07-standards/**
  - 01-research-plan/**
  - 02-library/00-papers/**
  - 02-library/01-annotations/**
  - 02-library/02-evidence/**
  - 00-dashboards/**
  - 04-supportDesign/**
  - 10-inbox/**
  - 11-projects/**
  - 12-log/**
  - My Library.bib
  - 02-library/My Library.bib
  - "**/*.pdf"

inputs:
  - automation/review/repo-governance/2026-07-16-karpathy-llm-wiki-hardening-ultraplan.md
  - automation/review/agent-tasks/review/2026-07-16-define-currency-and-derived-trust-contract.agent-task.md
  - automation/review/agent-tasks/review/2026-07-16-add-write-time-entity-resolution-gate.agent-task.md
  - automation/review/agent-tasks/review/2026-07-16-document-trust-propagation-procedure.agent-task.md
  - .claude/agents/vault-hygiene-auditor.md
  - Scripts/automation/validator.py
  - Scripts/automation/evidence_grounding_check.py
  - Scripts/automation/improvement_loop.py
outputs:
  - advisory semantic anti-drift implementation for consolidation PR 6
  - focused and adversarial tests
  - automation/review/routine-reports/repo-governance/2026-07-16-semantic-anti-drift-report.md
result_path: automation/review/routine-reports/repo-governance/2026-07-16-semantic-anti-drift-report.md
review_report_path: ""
handoff_model: codex_work_package
handoff_prompt_path: automation/review/agent-tasks/review/2026-07-16-implement-semantic-anti-drift-audit.agent-task.md

operator_decision_path: ""
linked_pr: "#426"
supersedes: []
duplicates: []

notes: "Consolidation PR 6 amendment. Extend an existing hygiene or validation owner. Advisory only until precision is demonstrated."
---

# Implement semantic anti-drift audit

## Objective

Extend an existing hygiene or validation route so it can identify stale current-facing surfaces, active scoped conflicts, newer source basis, missing supersession lineage, derived trust escalation, and unresolved entity duplication risk.

## Prerequisites

- W1 currency and trust contract is implemented or stable.
- W2 entity-resolution result shape is stable.
- W3 methodology procedure defines how genuine research contradiction differs from stale duplicate truth.
- Search current hygiene, validation, evidence-grounding, and graph-fitness implementations before choosing an owner.

## Finding vocabulary

Implement these advisory findings:

- `stale-current-surface`
- `active-claim-conflict`
- `source-newer-than-synthesis`
- `missing-supersession-lineage`
- `derived-trust-escalation`
- `unresolved-entity-duplication-risk`

Each finding must contain:

- affected path or paths;
- relevant dates or `as_of` values;
- source basis;
- trust and verification metadata when applicable;
- detection basis;
- confidence or deterministic status;
- one bounded recommended next action;
- explicit `advisory-only` posture.

## Required architecture

1. Deterministic checks first.
2. Optional semantic or model-assisted candidate generation only where it materially improves recall.
3. Fail-visible status when semantic services are unavailable.
4. Lexical or metadata fallback where useful.
5. Bounded scan roots, file-size limits, and file-count limits.
6. Existing `automation/review/hygiene/` or routine-report outputs only.
7. No second hygiene agent, index, or reporting family.

## Required exclusions

- historical and superseded contexts from active-current conflict checks;
- code fences and generated payloads where claim extraction is meaningless;
- differences that are merely terminology or scope changes;
- research contradictions where both claims are valid within different populations, methods, dates, or contexts;
- unsupported model conclusions without exposed source paths.

## Required work

1. Select and document the existing implementation owner.
2. Define deterministic candidate rules for all feasible findings.
3. Implement optional semantic candidate generation behind explicit availability reporting.
4. Produce structured JSON and readable Markdown using an existing report family.
5. Add focused tests for each finding.
6. Add adversarial tests for historical exclusions, scoped scientific disagreement, semantic outage, malformed metadata, scan limits, and false-positive separation.
7. Run against known stale-current examples from the 2026-07-15 truth map and report precision limitations.
8. Keep the tool advisory unless measured precision justifies a stronger gate in a later decision.
9. Update capability truth in the same PR.

## Acceptance criteria

- Zero canonical writes.
- No automatic truth adjudication or supersession.
- Known stale-current examples are surfaced with evidence.
- Historical and superseded contexts do not produce active-current errors.
- Semantic outage is visible and does not silently pass.
- Findings expose source basis and affected paths.
- False positives are bounded and documented.
- Existing structural hygiene checks remain intact.
- Focused tests, full validation, validator ratchet, capability-truth tests, agent-task lint, and `git diff --check` pass or have isolated environmental failures.

## Stop conditions

Stop and report blocked when:

- W1 to W3 contracts are unresolved;
- no existing implementation owner can be extended without creating a parallel stack;
- source basis cannot be surfaced;
- test precision is too low for useful advisory output;
- the implementation requires canonical edits or autonomous claim adjudication;
- optional semantic tooling becomes a hard dependency.
