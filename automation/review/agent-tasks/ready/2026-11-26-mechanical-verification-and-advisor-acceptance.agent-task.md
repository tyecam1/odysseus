---
artifact_type: agent-task
task_schema: agent-task/v2
task_id: 2026-11-26-mechanical-verification-and-advisor-acceptance
title: "Mechanical verification from CI evidence, pre-registered acceptance criteria and an advisor-acceptance design"
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
  - scripts/**
  - src/**
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
result_path: docs/runtime-work-packages/2026-11-26-mechanical-verification.md
---

## Plan (written 2026-11-26 by the controller; step 0 is to verify it against HEAD)
**Goal in one line.** Write `verification_evidence` mechanically when every check passed at the exact commit, add pre-registered acceptance criteria, and ship advisor acceptance designed but switched off.
**Already done / do not redo:** An existing verified path writes `verification_evidence` (locate with grep: `verification_evidence`, `verified_by`). Use it and never add a second writer. An advisor-approval worker is built but NOT enabled; leave it off and keep it separate. Tagged Sol records and fallback-lane headers identify reviewer models.
**Steps:**
0. Grep HEAD for the verified path, smoke and review records, CI-status reads and the card checker. Correct this plan.
1. Evidence collector (a pure function of a SHA): CI conclusion, deterministic tests, a smoke check where deployed, and an approving review from another model family, all from machine records. Test: complete only when all are present; missing checks are named.
2. Write only through the existing verified path: `result: pass`, commit, ref, and `verified_by` naming the actual check ids. Tests: a missing check writes nothing; a same-family or prose review is rejected.
3. Commit binding: evidence is valid only for its SHA. Test: a changed commit invalidates it.
4. Pre-registered criteria: optional `acceptance_criteria` on implementation cards. The checker warns when a new card has none, or when they post-date its first work commit. Fixture tests.
5. Advisor acceptance: a design plus code behind a config switch that defaults OFF. It accepts only when every pre-registered criterion has recorded evidence. It always refuses material sent in the owner's name, physical-world results and canonical thesis claims. Tests: off refuses and writes nothing; the default is off; exclusions refuse even when on.
6. Put the exact one-line owner question in the result doc ("May the advisor accept internal tools against pre-registered criteria and recorded evidence?"); do not send it.
7. Write docs/runtime-work-packages/2026-11-26-mechanical-verification.md (findings, a read-only dry run over the four cards waiting on `verification_evidence`, actual model). Run full pytest and stop.
**Done when:**
- Evidence needs every check at the exact SHA, and a changed commit invalidates it (tests).
- The switch defaults off, its path refuses while off, and the owner question is in the result doc.
- Full suite green.
**Risks and stops:**
- Never enable the switch or the advisor-approval worker; touch no approval code beyond this card's path.
- Write no real evidence for the waiting cards here; that comes after merge.
- If CI status cannot be read from the lab without a new credential, record a protected_handoff.
**Ordering note:** Benefits from card-hygiene attestations. Unblocks the four `verification_evidence` cards and avenue-to-develop's verification-debt tier; live advisor acceptance waits for the owner's yes.

---

# Mechanical verification and evidence-based acceptance

## Why

Four cards wait on `verification_evidence` and one on owner acceptance for internal tools whose tests, review and live behaviour are already recorded. Those are mechanical or advisor-grade checks, not owner decisions.

## Outcome

1. **Mechanical verification**: when CI and the deterministic tests are green at the exact commit, a smoke check passed where the work is deployed, and an approving review from another model family is recorded, write the `verification_evidence` (`result: pass`, commit, ref, `verified_by` naming the actual checks) through the existing verified path, never by a model's say-so.
2. **Pre-registered acceptance criteria**: new implementation cards carry written, checkable criteria before work starts, so acceptance can be evidence-based.
3. **Advisor acceptance, design only plus an opt-in flag that ships OFF**: an advisor may accept an internal tool against its pre-registered criteria and the recorded evidence. Turning this on is an owner decision (it changes who accepts work); this card produces the design, the guarded implementation behind a default-off switch, and the exact one-line question for the owner. It must not enable itself.
4. Human verification stays for: material sent to other people in the owner's name, physical-world results, and canonical thesis claims (which keep their repository's propose/review/ratify path).

## Verification

Tests: evidence is written only when every named check is present for that exact commit; a changed commit invalidates it; the advisor-acceptance path refuses to run while its switch is off.

## Rules that apply to this card (owner standing rules, 2026-11-06 and 2026-11-26)

- Internal Odysseus work only, through the normal branch, test, independent-review and PR lane. Sol review first (labelled GLM only if Sol is unavailable). Merge decisions follow the owner's merge rule.
- No new accounts, credentials, API keys, paid services, third-party dependencies or external writes. If a stage needs one, stop and leave a precise owner debt (`protected_handoff`); never work around it.
- Priority order is the only ordering. Do not add deadlines, time-boxes or concurrency caps of your own.
- Never touch owner approval, delegation or card-approval code paths except where this card names them, and never widen what a model may approve.
- Record the actual model used in every verification record.
