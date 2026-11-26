---
artifact_type: agent-task
task_schema: agent-task/v2
task_id: 2026-11-26-model-lane-refinements
title: "Model-lane refinements from the Opus use-case review: contract reconciliation, expiring-allowance rule and GLM write-qualification plan"
status: ready
priority: high
task_type: design-and-staged-implementation
created_by: operator-directed-claude-code
created_at: 2026-11-26T14:00:00+00:00
executor: claude_subscription
execution_mode: staged-design-then-opt-in-implementation
architecture: single-plus-verifier
architecture_rationale: "One implementing worker amends documents and stages config proposals; an independent model family reviews."
single_agent_baseline: "One qualified worker edits the documents and writes the proposal against live repository evidence."
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
  - docs/**
  - automation/review/**
  - tests/**
denied_paths:
  - "**/.env"
  - "**/secrets/**"
  - "**/*credential*"
  - "**/*token*"
  - "**/*password*"
  - config/routing.yaml
  - config/models.yaml
  - src/**
inputs:
  - AGENTS.md
  - docs/aoteru-model-host-routing-contract.md
  - docs/subscription-model-currency-policy.md
  - automation/review/model-lane-review/2026-11-26-opus-model-use-review.md
result_path: docs/runtime-work-packages/2026-11-26-model-lane-refinements.md
---

## Plan (written 2026-11-26 by the controller; step 0 is to verify it against HEAD)
**Goal in one line.** Make the written routing rules match the owner's current standing rules, and stage (do not apply) the config changes and the expiring-allowance rule the Opus review recommended.
**Already done / do not redo:** The review itself (`automation/review/model-lane-review/2026-11-26-opus-model-use-review.md`, Claude Opus 5.5, read-only) and its line references are the starting evidence. Re-check each cited line against HEAD first; lines drift. GLM harvest outputs under `automation/review/glm-harvest/` (if present) corroborate but are same-family GLM, not a verdict.
**Steps:**
0. Re-verify each finding in section 3 of the review against HEAD (quote the live line). Drop any that no longer hold; say so.
1. Contract and policy amendments (docs only): reconcile the review-lane rule with the owner's current standing rule (Codex-written work reviewed by Opus; GLM- or Claude-written work by Sol; GLM-5.3 corroborates; GLM-Flash out of the review pool), replace hard-coded model-version pins with "newest model resolved at dispatch", and correct the stale "no paid provider configured" statements. Test or checker: a docs grep that fails if a version pin or the stale sentence returns.
2. Expiring-allowance rule (design plus a proposed `expiring_allowance` block as a patch file under `automation/review/proposals/`): admit queued read-only GLM-5.3 jobs when the provider's authoritative weekly reset is within 14 hours and at least 5% remains; one job at a time; 5-hour window at most 75% used; keep a reserve of the larger of 150 credits or 1.5% for fallback review; stop 20 minutes before reset; outputs only under `automation/review/glm-harvest/`; record credits before and after; all reset times in GMT. Do NOT edit `config/routing.yaml`.
3. Lane-list proposal (patch file only): `routine_lanes` and `high_consequence_lanes` per the review (Flash mechanical only; Opus and Sol in the high-consequence lane; no undefined `glm-standard`), and the `model_alias` correction for the Opus lane, each with a replay plan (contract section on replay). Do NOT edit `config/models.yaml`.
4. GLM-5.3 write qualification plan (document only): 12 real low-consequence tasks in leased worktrees, 12/12 gates, zero out-of-lease writes, at least 10/12 accepted by an independent reviewer, the effective model recorded per call, no self-review, no private or PhD paths, plus one live quota-to-GLM write. End with the single one-line owner authorisation question; do not send it.
5. Write the result document (findings with live quotes, what was changed, what is staged, the owner line). Run the full test suite and stop.
**Done when:**
- Every changed statement quotes its live line; no config or source file is modified.
- The staged patch files apply cleanly to HEAD (`git apply --check`) and their replay plan is written.
- Full suite green; the result names the actual model.
**Risks and stops:**
- Never edit `config/routing.yaml`, `config/models.yaml` or any `src/` file here; applying a lane change needs a governed PR with replay and an explicit decision.
- Never enable GLM writes or use an astra model; record a `protected_handoff` if a step needs a new credential or paid service.

---

# Model-lane refinements

## Why

The owner asked for Opus to review every available model's use case. The review found the routing contract still bans automatic Opus review, keeps GLM-Flash in the review pool, pins versions the currency policy forbids, and routes high-consequence work to an unqualified lane; and it found that GLM allowance that resets unused is wasted because nothing used it. GLM's weekly pool resets at 2026-11-27 01:56 GMT; Codex's weekly pool resets 2026-11-27 21:13 GMT.

## Outcome

Written rules that match the owner's current standing rules, a staged and replay-planned set of config proposals, a guarded use-it-or-lose-it rule for expiring GLM allowance, and a narrow, evidence-gated plan to qualify GLM-5.3 for low-consequence writes. Nothing here changes live routing by itself.

## Rules that apply to this card (owner standing rules, 2026-11-06 and 2026-11-26)

- Internal Odysseus work only, through the normal branch, test, independent-review and PR lane. Sol review first (labelled GLM only if Sol is unavailable). Merge decisions follow the owner's merge rule.
- No new accounts, credentials, API keys, paid services, third-party dependencies or external writes. If a stage needs one, stop and leave a precise owner debt (`protected_handoff`); never work around it.
- Priority order is the only ordering. Do not add deadlines, time-boxes or concurrency caps of your own.
- Record the actual model used in every verification record. Only the newest version of any model is called; never pin one.
