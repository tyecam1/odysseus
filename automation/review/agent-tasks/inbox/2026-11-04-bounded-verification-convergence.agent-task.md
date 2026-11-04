---
artifact_type: agent-task
task_schema: agent-task/v2
task_id: 2026-11-04-bounded-verification-convergence
title: "Measure and stop low-value repeated agent verification"
status: inbox
priority: high
task_type: evaluation-and-bounded-implementation
created_by: chatgpt
created_at: 2026-11-04T11:12:00+00:00
updated_at: 2026-11-04T11:12:00+00:00
executor: claude_subscription
execution_mode: evidence-first-bounded-implementation
architecture: single-plus-verifier
architecture_rationale: "One owner audits real verification chains and implements only the smallest justified stop gate. A distinct qualified verifier checks the policy change, regressions and quality floor; no recursive reviewer cascade."
single_agent_baseline: "One executor classifies existing run histories, proposes a finite stopping rule, implements it in the canonical lifecycle only if justified, and checks deterministic replay before a single independent adjudication."
execution_host: lab
context_budget: medium
coordination_reason: "Prevent acceptance-complete tasks being repeatedly reopened by optional suggestions, while retaining consequential verification and independent review."
requires_remote_compute: false
requires_local_model: false
requires_zotero: false
requires_mcp: false
requires_web: false
verification_route: V2_HUMAN_VERIFIED
risk_level: medium
approval_required: true
source_traceability_required: true
repo: tyecam1/odysseus
branch: ""
allowed_paths:
  - automation/review/**
  - docs/**
  - evals/**
  - tests/**
  - src/**
  - routes/**
  - scripts/**
  - config/**
denied_paths:
  - "**/.env"
  - "**/secrets/**"
  - "**/*credential*"
  - "**/*password*"
inputs:
  - AGENTS.md
  - automation/review/agent-tasks/README.md
  - docs/aoteru-model-host-routing-contract.md
  - docs/subscription-model-currency-policy.md
  - automation/review/agent-tasks/ready/2026-10-01-sol-packet-efficiency.agent-task.md
  - automation/review/agent-tasks/ready/2026-09-08-subscription-usage-attribution-for-continuous-system-improvement.agent-task.md
  - automation/review/agent-tasks/inbox/2026-09-13-operating-contract-model-role-evaluation-system.agent-task.md
  - live execution/review traces and existing tests (discover at execution time)
outputs:
  - evidence-backed retrospective of repeated verification chains and marginal value per round
  - minimal acceptance/repair/escalation stopping contract mapped to existing lifecycle and routing ownership
  - targeted controller/prompt/structured-verdict changes only where the retrospective proves a defect
  - deterministic regression tests for PASS, BLOCK, OPTIONAL, disagreement, regressions and protected approvals
  - matched before/after replay or small canary with quality, latency and resource outcomes
result_path: docs/runtime-work-packages/bounded-verification-convergence-evaluation.md
review_report_path: automation/review/verification-convergence-independent-review.md
handoff_model: codex_subscription
operator_decision_path: docs/runtime-work-packages/bounded-verification-convergence-evaluation.md
supersedes: []
duplicates: []
notes: "Operator request 2026-11-04. Distinct from Sol packet batching: this item concerns acceptance and when to stop, not packing more decisions into each call. High priority does not override shipping-first backlog. Human approval required before changing protected acceptance/routing semantics or promoting deployment."
---

# Stop low-value repeated agent verification

## Problem and objective

Agentic work often undergoes 10+ Sol verification/repair rounds because each review finds another possible improvement. Do not assume these rounds are waste, and do not treat the ability to suggest improvements as evidence that work is unaccepted. Determine from actual traces when further rounds remove consequential defects versus create optional refinement, false positives, scope expansion or regressions. Reduce unnecessary review cost **without weakening correctness, safety, research integrity, mandatory independent review or human authority**.

The acceptance question is: **Does the deliverable meet its declared criteria, and is there evidenced material failure preventing acceptance?** It is not: "What else could be better?"

## Admission and existing ownership

- The canonical owner is `tyecam1/odysseus`. Consume this card through its existing queue and routing/lease lifecycle; do not create a second reviewer scheduler, task queue, telemetry store or model-selection authority.
- The shipping-first directive in `AGENTS.md` remains binding. This task stays in `inbox` until accepted backlog delivery, unless measured review churn demonstrably blocks an already accepted deliverable and existing triage authorises promotion.
- Inspect live `dev` HEAD, queue, actual controller, review prompts, tests, run telemetry and existing stop logic before planning edits. Run `aoteru preflight` / equivalent before implementation. Obtain existing governed repo-write authority; do not acquire implicit leases.
- Reuse the ready Sol packet-efficiency task for batching, the usage-attribution task for consumption data, and model-role evaluation for longitudinal comparisons. This card owns **verdict semantics and evidence-based stopping only**.
- Select the newest eligible subscription model through existing policy. Default to an adequate single implementation owner at medium effort; use an independent qualified cross-provider reviewer only where mandated, at high effort for consequential ambiguity. No model-version pinning or self-certification.

## Stage 1. Retrospective audit (read-only first)

Recover **up to 20 representative recent verification chains** with multiple rounds, or all available if fewer. Include routine code, substantial engineering, research-adjacent and governance-sensitive cases if available; report sampling bias and missing records. Do not manufacture runs just to reach a count.

For each round record existing trace pointers and where observable:

`task/run | acceptance criteria | model/role | round | explicit finding | objective supporting evidence | blocker/optional/uncertain | actual repair | regression | tests | accepted outcome | tokens or quota proxy | elapsed time | stop reason`

Use a constrained classification:

- `BLOCKER`: reproducible failure of a declared acceptance criterion, safety/security gate or protected authority.
- `UNCERTAIN`: credible consequential concern with insufficient proof; investigate once or escalate, not automatic rewrite.
- `OPTIONAL`: style, refactor, speculative architecture or new requirement that does not block acceptance.
- `INVALID`: unsupported or contradicted reviewer criticism.

Independently assess whether each repair improved the specified outcome. Do not equate a reviewer agreeing with itself to ground truth. Report the distribution of material findings and costs by round, especially rounds 4-10+, and examples of false rejection, regression or real late defect detection. If available traces cannot distinguish these categories, document the instrumentation gap and make only the smallest needed capture change.

## Stage 2. Stop contract and minimal implementation

Implement only if Stage 1 demonstrates preventable churn or a clearly reproducible open-ended-loop defect. Embed the rule within the existing task lifecycle/verification boundary rather than a new framework:

1. Run deterministic tests, schema/authority checks and other prescribed objective gates first.
2. Independent model review, when required, returns structured `PASS | BLOCK | ESCALATE` plus a separately recorded `OPTIONAL` set. Each `BLOCK` cites an explicit unmet criterion and concrete evidence; a suggestion alone cannot fail acceptance.
3. `PASS` with satisfied mandatory gates closes the verification loop. Optional findings go to the existing backlog only when material, deduplicated and authorised. Do not automatically reopen the accepted task.
4. Repair only validated blockers and recheck the **smallest affected scope**. Avoid repeated global review after local repairs unless a declared dependency is touched.
5. A default budget of **two model review-repair cycles** is a provisional heuristic, not a universal correctness cap. A further cycle requires a named unresolved blocker, new consequential evidence or mandatory domain gate, recorded with a reason and budget. Identical unresolved findings trigger changed strategy/escalation, not repetition.
6. `ESCALATE` or unresolved protected risks remain blocked/pending under their existing human/research-integrity authority. Never auto-PASS a failed test, override V2/human approval, remove required independence, weaken evidence floors or let quota exhaustion imply success.
7. Bound the verifier of this task itself: one independent review of the changed scope, then a single targeted repair/recheck if necessary. Escalate a persisting material disagreement rather than recursively reviewing the stopping-rule implementation.

Keep all thresholds configurable through existing governed policy only if evidence justifies configurability. No global arbitrary hard limit and no new user-facing tuning panel.

## Stage 3. Replay, canary and decision

Compare the unchanged baseline with the proposed gate on the **same historical cases/acceptance criteria**, including cases with genuinely late severe defects. Use deterministic replay where possible, and separately label any live model reruns or uncertain counterfactuals. Measure:

- acceptance-quality non-inferiority and missed material defects;
- false rejections, optional rework and reopening after PASS;
- total verifier rounds, tokens/quota proxy, elapsed time and time to accepted delivery;
- authority violations, regression frequency and operator intervention.

Reject or narrow a change if it suppresses legitimate blockers, mandates weaker review, creates false closure, or fails to demonstrate worthwhile improvement. Preserve unchanged behaviour as a valid outcome. If evidence is weak, deliver only diagnosis and a tested proposal, not an automatic policy rollout.

## Acceptance and stop

- [ ] Live ownership, runtime and existing stop semantics inspected; overlap with three existing efficiency tasks resolved.
- [ ] Real multi-round traces classified with evidence and explicit sampling/telemetry limitations.
- [ ] PASS is allowed with zero improvement suggestions; OPTIONAL cannot block acceptance.
- [ ] Concrete BLOCK/ESCALATE findings preserve tests, safety, independence and human/research-integrity approval.
- [ ] Tests cover no-findings PASS, optional-only PASS, material BLOCK, false criticism, repeated unchanged blocker, late severe defect, failed mandatory gate and scope-limited recheck.
- [ ] Comparative evidence shows quality at least maintained, and identifies actual change in review cost or an honest no-benefit outcome.
- [ ] All adopted changes pass relevant tests, independent review, existing authority and rollout/rollback gates; no silent merge or policy promotion.
- [ ] One concise outcome record states `ADOPT | NARROW | REJECT | INSUFFICIENT_EVIDENCE`, stop reason and any bounded follow-up debt.

Stop when evidence supports a decision and required acceptance gates pass. Do not continue optimising verification merely because an additional improvement can be imagined.
