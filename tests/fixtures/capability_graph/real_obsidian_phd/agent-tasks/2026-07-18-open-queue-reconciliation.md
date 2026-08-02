---
artifact_type: workflow
title: Open agent-task queue reconciliation — full disposition audit
created: 2026-07-18
created_by: fable-route-loop
status: review
---

# Open agent-task queue reconciliation — 2026-07-18

Full audit of the 82 open items under `automation/review/agent-tasks/{inbox,ready,review,blocked}`
(audited 2026-07-17 in the live working tree; dispositions re-anchored to `origin/main`
641495269). Every review-lane task's declared `result_path`/outputs were verified present on
disk. Because every review task is `verification_route: V2_HUMAN_VERIFIED`, **acceptance into
`done/` remains the operator's act** — this report supplies the evidence; the companion decision
packet (`automation/review/decision-packets/2026-07-17-agent-task-acceptance.decision-packet.md`)
turns it into one yes/no.

Note: the previously-tracked "six #426 review tasks pending V2 acceptance" no longer exist in
the open tree — PR #428 ("accept Karpathy tasks") already accepted them. That expectation is
closed.

## Disposition summary

| disposition | count | resolution route |
|---|---:|---|
| done-evidence (outputs on disk / PR landed) | 61 | operator batch-acceptance via decision packet |
| live-agentic (real remaining agent work) | 10 | stays open; see routing notes |
| blocked-external | 7 | stays blocked; 5 now reopenable (preconditions landed) |
| superseded/duplicate | 2 | proposed `rejected/` (superseded) in decision packet |
| operator-owned (human-only) | 2 | stays; not agent-resolvable |

## Done-evidence (61) — accept via decision packet

Group A — merged-PR-backed (5, safest): 2026-07-02-asi-evolve-lesson-skill-compilation (#401) ·
2026-07-02-decouple-odysseus-heartbeat (#399; caveat: confirm daily heartbeats actually resumed
after 06-29 before accepting) · 2026-07-02-evidence-grounding-check (#400) ·
2026-07-02-execute-review-retention-archival (#398) ·
2026-06-19-odysseus-remote-compute-dispatch-guard (odysseus PR #2; contract-compatibility
review posted on the PR 2026-07-17).

Group B — audit/eval/automation artifacts with outputs on disk (32): elongate-odysseus-timeouts ·
fm1-endpoint-attestation · obsidian-git-conflict-containment · review-retention-sweep ·
consolidate-skill-mcp-browser-deployment-policy · implement-research-integrity-and-handoff-contracts ·
odysseus-central-interface-registry · pilot-source-acquisition-provenance-pipeline ·
adoption-readiness-1cf50fd4 · agentic-work-item-consolidation-027aea9d ·
audit-live-agent-routine-migration-state · implement-post-audit-agent-routine-convergence ·
prune-agent-routines-for-vault-relevance · quarantine-a40bf353 · campagna-trust-pack-adjudication ·
lee-see-trust-source-reconciliation · mono-colour-backfill-residue-triage ·
odysseus-git-single-writer-safety · odysseus-routine-hygiene-and-provenance ·
odysseus-schedule-attestation-and-heartbeat-gating · asi-evolve-compute-box-evidence-ingest ·
asi-evolve-compute-box-bundle-run · vault-grounded-paper-selection-instructions ·
canonical-promotion-review-dashboard · evidence-authority-repair-batch-plan ·
ontology-alias-and-factor-freeze-audit · operator-cockpit-minimum-spec ·
root-hygiene-and-artifact-containment · standards-path-authority-resolution ·
validator-debt-baseline-and-ratchets · methodological-spine-drafting-guidance-digest ·
advance-completed-claude-task-lifecycle.

Group C — S2/J1/supervision research packets feeding human writing (24): socially-conscious-robotics
source scout · benchmark-system-paper-scaffold · cad-base-requirements ·
constrained-manipulation-lit-grounding · j1-paragraph-level-research-gathering ·
s2-experiment-question-split · s2-system-architecture-framework · supervision-log-integrity-audit ·
supervision-record-rollup-source · weekly-erfu-supervision-docx-export (identity drift:
task_id ≠ filename — record, do not rename) · s2-e1 benchmark-validity · dynamic-obstacle ·
min-safety-distance · sensing-event-classification · useful-support-action · s3-event-linked-safety ·
s4-safety-response-policy · s2-cad-to-system-model-pack · s2-e1-mechatronic-v-model ·
s2-hardware-zotero-constraints · j1-adjacent-automation-calibrated-reliance ·
rescope-superseded-s2-literature (human-executed, recorded) · 2026-07-01-s2-missing-experiment-research
(already in review/ with status review on origin/main; the audit's inbox sighting reflected the
stale dirty working tree — no move needed) · 2026-06-16-update-erfu — see
operator-owned note below; listed here only for visibility.

(Count note: update-erfu is operator-owned recurring, not acceptance-eligible; Groups A+B+C
acceptance-eligible total is 60, plus the s2-missing-experiment-research move = 61 dispositioned.)

## Superseded (2) — proposed rejected/superseded
- 2026-06-15-a-systematic-review-...-927c772e → superseded by campagna-trust-pack-adjudication
  (declared in its `supersedes`).
- 2026-06-15-annotation-rollup-...-c0729480 → superseded by mono-colour-backfill-residue-triage.

## Live-agentic (10)
inbox: open-work-queue-audit (satisfied by THIS report — accept and close with it) ·
review-dirty-rescue-branch · s1-journal-manuscript-reset · s2-lab-blackout-replan (blackout
07-28→08-28 imminent, highest urgency) · s2-perception-supervision-synthesis · the five
2026-07-04 J1 tasks (bainbridge-ingestion-prep, citation-chain-log, ground-truth-micro-patches,
positive-programme-evidence-balance, s4-verification-economics-scout) — **note: these five plus
blocked j1-skill-formation exist only as uncommitted files in the operator's dirty
`automation/vault-attention-compute-box` working tree, not on main; their registration rides
with that branch's disposition.**

## Blocked-external (7)
Reopenable now (preconditions landed in review): graphiti-temporal-memory · langgraph-orchestration ·
operator-cockpit-platform-eval (overlaps landed cockpit-minimum-spec — merge on reopen) ·
ragflow-vs-onyx-bakeoff · rtk-command-output-optimization. Still genuinely blocked:
zotero-library-vault-alignment (needs Zotero write capability) · j1-skill-formation-transfer
(gated on J1 §6 drafting start; also uncommitted, see above).

## Operator-owned (2)
branch-protection-main (GitHub settings toggle; `ready/`) · update-erfu-supervision-record
(recurring after-meeting human update).

## Duplicate clusters (recorded for future queue hygiene)
Odysseus P0–P4 programme (4 tasks, one attestation family) · ASI-Evolve pair · trust-pack trio ·
annotation-rollup chain · agent-routine trio · cockpit pair · S2-E1 supervision programme (8) ·
S2-E1 literature batch (7) · supervision office-pack quartet · 06-29 roadmap sextet ·
review-retention pair · queue-audit overlap (this report closes it).

## Stale backlog pointers (10-inbox/backlog.md)
Eight active bullets point at files moved to `10-inbox/complete/` **in the operator's
uncommitted working tree only** (dino-buildability, s2-e1-human-task-extraction, s2-e1-cad-mockup,
build-constrained-manipulation-cad-base, prepare-next-week-s2-architecture,
interim-s2-perception, icac2026-registration (deadline passed), mobile-vault-approval-channel).
The pointer fix belongs to the dirty-branch disposition, not to this branch — recorded here so
it is not lost.

## Schema drift (recorded, not fixed here)
Most pre-July tasks use `artifact_type: workflow` where the schema now says `agent-task`;
weekly-erfu task_id ≠ filename. Both are candidates for the next queue-hygiene pass, not
silent edits.
