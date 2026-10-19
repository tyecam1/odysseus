---
artifact_type: agent-task
task_schema: agent-task/v2
task_id: 2026-10-19-harness2-contrastive-harness-evolution
title: "Evaluate and selectively integrate Harness² recursive harness optimisation"
status: inbox
priority: medium
task_type: evaluation-observability
created_by: chatgpt
created_at: 2026-10-19
updated_at: 2026-10-19T12:17:00+01:00
executor: ""
execution_mode: review-first
architecture: single-plus-verifier
architecture_rationale: "One mutation owner should extend existing Odysseus evaluation/prompt mechanisms; an independent verifier tests generalisation, security, authority and measurement claims."
single_agent_baseline: "Audit current execution/evaluation/prompt-evolution machinery, implement a bounded contrastive pilot, compare against the unchanged baseline, and make a measured adopt/reject decision."
execution_host: compute-box
context_budget: medium
coordination_reason: "Read-only external-method analysis may be delegated; only one worker owns code or canonical-prompt mutations at a time. Adjudication is independent."
requires_remote_compute: true
requires_local_model: false
requires_zotero: false
requires_mcp: false
requires_web: true
verification_route: V3_INDEPENDENT_MODEL_ADJUDICATION
risk_level: high
approval_required: true
source_traceability_required: true
repo: tyecam1/odysseus
branch: ""
inputs:
  - "live dev state and AGENTS.md (shipping-first backlog priority)"
  - "docs/initialising-prompt-register.md"
  - "evals/prompt-applications/**"
  - "evals/prompt-evolution/**"
  - "scripts/prompt_evolution.py"
  - "scripts/routing_replay_evaluator.py"
  - "docs/aoteru-model-host-routing-contract.md"
  - "automation/review/agent-tasks/inbox/2026-09-13-operating-contract-model-role-evaluation-system.agent-task.md"
  - "automation/review/agent-tasks/inbox/2026-09-10-external-capability-equivalence-audit.agent-task.md"
  - "https://arxiv.org/abs/2610.14224"
  - "https://github.com/google-research/harness2/tree/1cfe254e8d25b15f37048c3730134686abe60335"
outputs:
  - "one source-grounded Harness² to Odysseus mechanism/ownership gap matrix"
  - "bounded baseline vs one-step contrastive pilot with run manifests and cost/quality evidence"
  - "adopt / extract / retain / reject decision per candidate mechanism"
  - "small tested native integrations only where the pilot establishes benefit"
  - "independent review and rollback/stop evidence"
result_path: docs/runtime-work-packages/harness2-odysseus-adoption-review.md
review_report_path: ""
handoff_model: independent-reviewer
operator_decision_path: docs/runtime-work-packages/harness2-odysseus-adoption-review.md
linked_pr: ""
supersedes: []
duplicates: []
notes: "New nonessential capability work: keep in inbox under 2026-10-17 shipping-first directive. This item authorises review and a bounded isolated pilot, not automatic deployment, bypass of write leases, unrestricted Codex execution, or autonomous production-policy promotion."
---

# Evaluate and selectively integrate Harness² into Odysseus

## Autonomous prioritisation and delivery handoff

- **Canonical intake:** this `inbox/` agent-task is the sole work item. Consume it through the existing Odysseus queue/prioritisation and autonomous-development workflow, not a GitHub issue, secondary backlog, autonomous runtime or new programme controller.
- **Admission and precedence:** `priority: medium` is a provisional intake classification, **not permission to pre-empt** the 2026-10-17 shipping-first instruction in `AGENTS.md`. When the accepted baseline backlog is shipped (or this item proves necessary to unblock an accepted item), reassess its relative value, dependencies and delivery cost against the *live* queue. Promote to `ready/` only through existing triage authority; otherwise retain, merge with an existing task, or reject with a recorded reason.
- **Duplication/dependencies:** explicitly reconcile the operating-contract/model-role evaluation card (2026-09-13) and external-capability equivalence audit (2026-09-10). The Harness² item concerns the **contrastive experiment and evidence-backed composition/transfer mechanism**, not reimplementation of their model telemetry, capability inventory or lifecycle owners. Link or fold any overlap, and preserve predecessor evidence.
- **First eligible autonomous unit:** take a read-only, source-grounded gap inventory of Harness² versus *live* Odysseus at HEAD and identify one narrowly measurable failure class. Return a compact evidence pointer and the smallest independently verifiable baseline/pilot plan. Do not begin full adaptation from the upstream README alone.
- **Development route:** recheck `AGENTS.md` and the live estate policy; run Odysseus `aoteru preflight`, use the cheapest adequately qualified route, obtain a governed write lease for mutations, and keep one implementation owner. Use staged bounded commits, deterministic tests and independent adjudication. No silent policy mutation or permission escalation.
- **Authority gates:** ordinary read-only reconnaissance and local isolated tests follow the normal queue/workflow permissions. `approval_required: true` reserves operator approval for the task's guarded implementation/adoption boundary; it must not be interpreted as permission to deploy, alter guardrails, expose secrets, disable sandboxing or bypass existing approval mechanisms. An authorised reviewer may split out a separately approved read-only pilot if this flag blocks all preliminary work.
- **Done means shipped:** a written review alone is not implementation completion. Record the source/HEAD, task-level baseline and candidate comparisons, total effort and cost, verification outcomes, accepted native changes if any, deployment or real-path evidence where relevant, explicit rejections, queue disposition and rollback. A justified `retain/reject` with rigorous evidence also completes the **evaluation** objective; no feature must be imported merely because the task exists.
- **No schedule implied:** this card is durable intake. It does not establish that an automatic watcher is currently running or authorise an immediate dispatch contrary to the backlog policy.

## Objective

Determine whether mechanisms from Google's Harness² (Xu et al., 2026) measurably improve Odysseus's accepted task outcomes, verification quality and cost-efficiency. Implement the smallest useful enhancements to the **existing** control plane after comparative proof. Do not add a second router, agent-task queue, orchestration authority, memory authority, executable-plugin registry or autonomous policy owner.

The correct success criterion is **improved results under unchanged safety/authority floors at an acceptable all-in cost**, not feature parity with Harness².

## Grounded external method

Source: *Harness²: Recursive Agent Harnessing for an Open World*, arXiv:2610.14224, Google Research repository at `1cfe254e8d25b15f37048c3730134686abe60335` (14 October 2026).

- Two nested loops: task-level contrastive **Propose–Probe–Compose**, then cross-task reflection into a persistent improvement harness.
- Proposal scopes: general/invariant procedure vs domain-specific method.
- Evidence includes baseline trajectories, edited harness versions, candidate trajectories and produced deliverables; composition may retain the base unchanged.
- A candidate-output selector uses anonymised candidate artefacts, without access to the benchmark's grading verdict.
- Parallel recursion explores `k` general and `k` domain candidates, then composes `k` alternatives; sequential recursion carries the latest harness through `k` rounds.
- Per-domain experience libraries contain adopted harness trees and evidence-backed lessons, with ordered access to prior tasks.
- Eight candidate mutation surfaces: system prompt, guardrails, memory, tool guidance, subagents, skills, scripts, plugins.
- Research implementation schedules approximately `4k` executor rollouts and `3k` improvement stages, before optional selection/reflection. This is not a default low-cost runtime.
- Upstream warns that network-unrestricted benchmark executors, including Codex run without sandboxing, may read public benchmark rubrics. **Never inherit those permissions or interpret benchmark scores as locally verified gains.**

Relevant upstream implementation: `harness2/core/{recursion,selection,library,context,prompts,tree}.py`, `docs/EXPERIMENTS.md`, `docs/SETUP.md`. Apache-2.0 upstream, but third-party benchmark dependencies have separate notices.

## Existing Odysseus capabilities: reconcile before designing

Inspect live implementation, not old task cards alone:

- prompt versioning/application traces/graph evolution: `config/initialising-prompts.yaml`, `docs/initialising-prompt-register.md`, `evals/prompt-*`, `scripts/prompt_evolution.py`;
- runtime telemetry, routing comparisons and policy: `scripts/routing_replay_evaluator.py`, `src/routing_evaluator.py`, `config/routing.yaml`, `docs/aoteru-model-host-routing-contract.md`;
- agent-task orchestration, qualified workers, single writer, leases and immutable provenance: `AGENTS.md`, estate routes/services and current code;
- overlapping unshipped work: 2026-09-13 operating-contract/model-role evaluation, 2026-09-10 external-capability equivalence audit, skill lifecycle, prompt exemplars and staged implementation loop.

Produce a gap/overlap table: **upstream mechanism | local executable analogue | true missing behaviour | value hypothesis | minimal owner/path | security cost | recommendation**. Do not mark an existing capability as absent merely because it uses a different name. Coordinate with existing work items rather than implementing their entire scope again.

## Staged work

### A. Read-only method and compatibility audit

1. Verify upstream version and actual code-level behaviour, not just abstract/README. Separate the paper's claims, released-code behaviour, and proposed Odysseus adaptations.
2. Distinguish candidate editing from candidate judging and final promotion. Identify evidence leakage and same-task selection bias.
3. Confirm the baseline Odysseus workflow for at least three relevant task classes and its existing run identity, contract hash/version, telemetry and verified-outcome fields.
4. Reject entire upstream-framework integration unless a specific capability is demonstrably impossible to extract. Prefer native extension and no runtime hard dependency on Google Cloud, OpenCode, or the upstream benchmark suite.

### B. Small contrastive pilot (priority mechanism)

Prototype behind a disabled-by-default flag or isolated temporary worktree:

1. Run unchanged baseline on a fixed task/input/ref using the normal qualified executor, authority and tool permissions.
2. Propose one narrow invariant improvement and one narrow domain-specific improvement. Every proposed edit specifies observed failure, minimal delta, affected contract, risks, and rollback.
3. Probe the same task for each candidate with the same model, tool surface, task snapshot, resource budget and evaluation conditions. Retain failed/empty runs.
4. Compare executed artefacts and trajectories, not self-reported advantages. Allow retain-base, adopt-single, or composed candidate; give any composition a fresh probe.
5. Use deterministic verification first; where subjective output comparison is unavoidable, test a blinded selector and independently assess selector agreement with held-out/external outcomes. Selector votes alone never constitute correctness.
6. Attribute token/call cost, latency, retries, context and operator intervention across **all** proposal/probe/selection/reflection stages, not only the selected answer.

Do not use production secrets, unrestricted network or unsandboxed Codex, hidden grading rubrics, or writable canonical state in the pilot. Preserve task snapshot hashes and tool/network policy in each run manifest.

### C. Generalisable lessons without uncontrolled self-modification

If the pilot supports it, extend the *existing* application/evolution graph with concise evidence-linked lessons:

- `lesson_id`, source run IDs, task class/domain, exact model, role, contract and tool-surface IDs/hashes, claimed applicability, observed benefit, confidence, negative evidence, affected files and lineage;
- explicit `candidate -> validated -> ratified` and `rejected/superseded` lifecycle compatible with existing governance, not a competing status machine;
- retrieval filtered by domain/role/contract and only earlier admissible evidence; isolate held-out task content and verifier/rubric signals;
- preserve failure/regression examples, sanitise sensitive data, and prevent task-specific answer facts, user data, injected instructions and grader verdicts from becoming reusable agent authority.

Prefer a small typed manifest and pointers to immutable existing artefacts over copying whole executable harness trees into prompt context. Do not let a remembered lesson amend protected invariants, grants, model routing or live deployment policy.

### D. Selective adaptation of remaining Harness² mechanisms

Evaluate only if supported by pilot evidence:

- **Conditional recursion**: no change on easy/deterministically verified tasks; one-step candidate probe on recurring failures; `k>1` or wider parallelism only when expected value exceeds measured all-in cost.
- **Blind result selection**: useful for source-grounded documents or ambiguous results, never a substitute for objective task tests.
- **Broader editable surfaces**: start with prompt/tool guidance/skill trigger changes; scripts, plugin hooks, security guardrails and write-scope modifications require isolated testing and explicit governance, not automated promotion.
- **Executor-agnostic packaging**: reuse current host/model qualification and ParkLease/EstateExecution semantics; do not graft in Harness² executor authority.

Document explicit **retain** decisions where local mechanisms are already more appropriate.

### E. Independent, held-out evaluation and gate

Build a small reproducible, repo-shaped comparison, at minimum three task classes with three representative cases each where feasible (for example bounded code repair, evidence/source-grounded extraction, and governance-sensitive task planning). Include at least one adversarial case: prompt injection, cross-domain leakage, unsupported source claim, rubric exposure or unsafe write attempt.

Compare:
- A: unchanged Odysseus baseline;
- B: current Odysseus prompt-evolution/routing process (if it actually differs from A for the tested task);
- C: one-step contrastive mechanism;
- D: higher budget / persistent lessons **only if** C shows credible value.

Hold task, model version, baseline ref, access policy and independent grader constant; use fixed seeds where supported and repeat enough to report variation. Split pilot/evolution tasks from held-out assessment. If controlled replication is infeasible, report descriptive evidence and lower confidence. No invented statistical significance.

Metrics: independent accepted-output rate, correctness/coverage, first-pass test outcome, governance incidents, evidence provenance, negative transfer, operator corrections, tokens/calls, latency, and total cost **per accepted outcome**. Report paired task-level deltas, sample sizes, confidence limitations, and regressions. A method that improves polished-looking answers but worsens correctness, safety or cost-adjusted usefulness is rejected.

### F. Delivery, disposition and reuse

1. Publish one compact source-mapped review and comparative evidence packet.
2. Promote **only** proven bounded improvements through existing review, write-lease, tests and deployment gates. A high-consequence policy/guardrail change always requires explicit operator approval.
3. Run targeted regression tests and independent security/architecture adjudication; preserve safe rollback and a disabled-default fallback until acceptance.
4. Resolve overlap with existing operating-contract evaluation and skill audit cards; update their links instead of creating another evaluation subsystem.
5. Record whether each Harness² feature was **adopted**, **extracted**, **retained locally**, **rejected**, or remains **unproven**, with reasons. Close the task with a justified no-adoption result if no measurable improvement survives verification.

## Mandatory acceptance conditions

- No duplicate control plane, task queue, skill registry, model router, telemetry owner or promotion authority.
- Contrastive candidates are tied to reproducible same-task baseline artefacts, contract hashes, model identity, permission sets and full rollout costs.
- The baseline is a valid possible outcome; failed/empty probes and unsuccessful edits are preserved.
- Any candidate judged without ground truth is marked provisional until independent verification; hidden graders and future-task artefacts cannot leak into improvement context.
- No unrestricted networking, unsafe shell execution, unsandboxed Codex, automatic permission widening or policy auto-promotion.
- Demonstrated benefit, **or** a justified rejection based on matched outcomes and total resource use; external benchmark improvements alone never count.
- Smallest supported change integrated with existing prompt/evaluation machinery, with passing regression checks and operator-controlled ratification/rollback.
- Shipping-first directive respected: nonessential refinement remains in `inbox` until accepted backlog delivery or explicit reprioritisation.

## Source and related-work record

- Xu et al. (2026), `https://arxiv.org/abs/2610.14224`.
- Google Research Harness² `https://github.com/google-research/harness2`, inspected commit `1cfe254e8d25b15f37048c3730134686abe60335`.
- Upstream experimental controls: `https://github.com/google-research/harness2/blob/main/docs/EXPERIMENTS.md`.
- Related Odysseus tasks: `2026-09-13-operating-contract-model-role-evaluation-system` and `2026-09-10-external-capability-equivalence-audit`.
