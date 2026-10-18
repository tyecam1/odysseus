---
artifact_type: agent-task
task_schema: agent-task/v2
task_id: 2026-10-02-seed-order-raw-note-and-candidate-labelling
title: "Steer the household runtime to preserve raw notes verbatim and label candidates (Seed Order fixtures 2 and 3)"
status: done
priority: medium
task_type: implementation
created_by: claude
created_at: 2026-10-02T18:00:00+01:00
updated_at: 2026-10-03T15:00:00+01:00
executor: ""
execution_mode: review-first
architecture: single
architecture_rationale: "Prompt/steering change in the existing Seed Order runtime-loading path only. No new agent, router or store; no model swap in this task."
single_agent_baseline: "One implementation owner extending the existing owner named in the task."
execution_host: compute-box
context_budget: medium
coordination_reason: "Split out of 2026-08-19-aoteru-central-memory-and-universal-assistant when the Phase 4 ADR was ratified (Misumi PR #46), so that the genuinely deferred part is not lost with the retired broker and Mem0 work."
requires_remote_compute: false
requires_local_model: false
requires_zotero: false
requires_mcp: false
requires_web: false
verification_route: V2_HUMAN_VERIFIED
risk_level: low
approval_required: true
source_traceability_required: true
repo: tyecam1/odysseus
branch: ""
allowed_paths:
  - docs/**
  - tests/**
  - src/**
denied_paths:
  - "**/.env"
  - "**/secrets/**"
inputs:
  - automation/review/agent-tasks/rejected/2026-08-19-aoteru-central-memory-and-universal-assistant.agent-task.md
  - tyecam1/misumi:docs/memory-architecture.md
  - tyecam1/misumi:docs/memory-policy.md
outputs:
  - a steering change (prompt/context assembly or a deterministic post-check) so that the corrected fixtures pass, plus tests
result_path: ""
review_report_path: ""
handoff_model: gpt-5.6-sol
operator_decision_path: ""
supersedes: []
duplicates: []
notes: "Corrected live fixtures 2 and 3 failed 3 of 3 each on 2026-10-02 (qwen3:8b on home, GPU free). Prompts 1 and 4 pass. Model changes are out of scope: they go through 2026-09-13-operating-contract-model-role-evaluation-system."
---
# Seed Order steering: raw-note preservation and candidate labelling

## Why

`tyecam1/misumi` card `agent-tasks/odysseus/verify-seed-order-live-runtime.md` could not be judged until its fixtures were
valid. They were rebuilt (`fixtures/seed-order/live-verification.yaml`, Misumi PR #47): a real messy raw note, and five explicit
repeated observations. Run live through the authorised interface-box `/agent` proxy with `persist_turn:false`,
`retention_mode:"off"`, `history_mode:"off"`:

| Fixture | Result | Failure |
| --- | --- | --- |
| 2 raw-note preservation | 0 of 3 | the note is paraphrased every time; no `inferred` or `proposed` label |
| 3 recurring-observation scan | 0 of 3 | the findings are stated plainly, with no `candidate_pattern` or `candidate_mechanism` label (ratification is never claimed) |
| 1 new household rule, 4 activate all personas | pass | |

The fixtures are valid and the failures consistent, so this is a steering defect. Do not tune the fixtures to the model.

## Required work

1. Find where the Seed Order text reaches the `/misumi/respond` prompt (the existing runtime-loading path) and why the labelling
   and preservation rules do not bind for these two intents (for example the rule is present but not placed where the model
   attends to it, or a retrieval path answers first).
2. Change steering at the smallest scope that works: the instruction placement or wording, or a deterministic check that
   quotes the raw note verbatim and applies the label vocabulary (`inferred`, `proposed`, `candidate_pattern`,
   `candidate_mechanism`; never `ratified`). Prefer the deterministic check if prompting alone is unreliable.
3. Re-run the fixtures with `scripts/host/verify-seed-order-live.ps1` on the interface box and score them with
   `scripts/score_seed_order_fixtures.py`, at least 3 runs each for fixtures 2 and 3.

## Constraints

- Verification only through the box's existing `/agent` proxy. Never extract, print, copy or persist the service token anywhere.
  Every verification request sends `persist_turn:false`, `retention_mode:"off"`, `history_mode:"off"`.
- Confirm the canonical Misumi clone is unchanged by the run (and note that it was already dirty; see
  `tyecam1/misumi:docs/audits/2026-10-02-home-clone-dirty-working-copy.md`).
- No model swap here. If prompting cannot fix it, record that and route the question to the model-role evaluation task.

## Acceptance

- Fixtures 1 to 4 all pass in at least 3 consecutive runs each, scored by the Misumi scorer, with persistence checks clean.
- A unit test pins the steering behaviour (or the deterministic check) for the raw-note and candidate-label cases.
- The Misumi card is then closed with the run evidence.

## Result (2026-10-03, programme application 05)

- **Change:** Odysseus PR #79. `src/seed_order_enforcement.py` plus two lines in `routes/misumi_routes.py`: the Seed Order output rules are restated in
  the last system message, directly before the user turn, and enforced deterministically when the model does not comply (the user's own raw
  span is quoted verbatim and the weakest applicable label, `inferred` or `candidate_pattern`, is applied, never `ratified`). Narrow triggers;
  every other reply is untouched. No model change and no fixture change.
- **Unit evidence:** 40 tests pass on the lab (the new file plus the neighbouring Misumi reply, consultation and conversation suites); three mutants
  (verbatim check removed, candidate label removed, rules block removed) each turn tests red; the tests replay the replies the live model gave on 2026-10-02.
- **Live evidence, through the interface box's own `/agent` proxy** (`persist_turn:false`, `retention_mode:"off"`, `history_mode:"off"`, token never
  read), runtime release `a62728a4d9bf`, `qwen3:8b`: all four corrected fixtures pass **6 of 6 each** (two batches of three consecutive runs), every response
  confirming nothing persisted. Recorded on the Misumi card `verify-seed-order-live-runtime`.
- **Honest limits:** how much the restated rules achieve without the deterministic step was not measured separately (a direct run on the household
  host was not permitted). A scorer precision defect (any mention of "ratified" was scored as a claim) was found by reading the replies and fixed with tests
  in Misumi; fixtures and the model were not changed. The Misumi card stays open only for the clean-clone criterion and one re-run after the operator
  authorised home clone reconciliation.
