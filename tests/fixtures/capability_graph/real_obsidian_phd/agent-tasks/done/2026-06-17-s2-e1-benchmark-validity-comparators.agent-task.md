---
artifact_type: workflow
task_schema: agent-task/v1
task_id: 2026-06-17-s2-e1-benchmark-validity-comparators
title: Research S2-E1 benchmark appropriation and local comparator structure
status: done
priority: high
task_type: evidence-synthesis
created_by: chatgpt
created_at: 2026-06-17T17:18:00+01:00
updated_at: 2026-06-19T00:00:00+01:00
executor: claude_subscription
execution_mode: handoff
requires_remote_compute: false
requires_local_model: false
requires_zotero: true
requires_mcp: true
requires_web: true
verification_route: V2_HUMAN_VERIFIED
risk_level: high
approval_required: true
source_traceability_required: true
repo: tyecam1/obsidian-PhD
allowed_paths:
  - automation/review/s2-benchmark-design/literature-reinforcement/2026-06-17-s2-e1-benchmark-validity-comparators.md
  - automation/review/agent-tasks/**/2026-06-17-s2-e1-benchmark-validity-comparators.agent-task.md
denied_paths:
  - 01-research-plan/**
  - 02-library/00-papers/**
  - 02-library/01-annotations/**
  - 02-library/02-evidence/**
  - 02-library/**
  - 03-concept/**
  - 04-supportDesign/**
  - 07-standards/**
  - 00-dashboards/**
inputs:
  - 04-supportDesign/thesis-benchmark/s2-e1-minimum-safety-distance-benchmark.md
  - 04-supportDesign/operator-task-fit-adaptive-support/experiment-design-ledger.md
  - 03-concept/decisions/define-staged-s2-s5-comparator-and-benchmark-appropriation-model.md
outputs:
  - automation/review/s2-benchmark-design/literature-reinforcement/2026-06-17-s2-e1-benchmark-validity-comparators.md
result_path: automation/review/s2-benchmark-design/literature-reinforcement/2026-06-17-s2-e1-benchmark-validity-comparators.md
operator_decision_path: 10-inbox/prepare-next-week-s2-system-architecture-discussion.md
---
# Task: Research S2-E1 benchmark appropriation and local comparator structure

## Objective

Research two linked questions before S2-E1 experimental conditions are fixed:

1. Which simple existing benchmark families can be appropriated for S2-E1 by copying task grammar, apparatus simplicity and metrics?
2. Which **local S2-E1** condition comparison is necessary once the thesis-level comparator is staged across S2, S3, S4 and S5?

The thesis-level comparator model is fixed as staged maturity:

```text
S2: benchmark validity and bounded useful support
S3: communication / human-factor layer on the same benchmark
S4: control / safety-policy layer on the same benchmark
S5: abstraction and industrial transferability
```

Do not treat C0 manual, C1 static support, C2 dynamic response as the thesis-level comparator. At most, such conditions are local S2 candidates.

## Agent execution contract

Work autonomously until the required output exists and the acceptance criteria are satisfied.

- Act once enough information exists. Do not keep searching after the likely benchmark/comparator answer is clear.
- Use web only for benchmark-family verification and missing source detail. Prefer primary sources, official project pages, papers, or repositories.
- Use Beaver/Zotero read-only if relevant papers are already in the vault. Do not mutate Zotero or canonical evidence.
- Pause only for a destructive action, a real scope change, missing access, or a missing user-only input.
- If blocked, write a blockage section in the output with exact blocker, attempted route, partial results, and the next human action needed.
- Before reporting completion, audit every claim against a source, file read, web result, or output file from this run.
- Final response: recommended local comparator, output path, major uncertainty. No excess commentary.
- Do not reveal private chain-of-thought. Give short rationale only where it changes the comparator decision.

## Research question

> Which simple benchmark task grammar and local S2-E1 condition comparison should be used to test constrained-process robotic support without collapsing the work into generic assembly, obstacle avoidance, glovebox teleoperation, or safe-RL benchmarking?

## Required output

Write one review-side packet to:

`automation/review/s2-benchmark-design/literature-reinforcement/2026-06-17-s2-e1-benchmark-validity-comparators.md`

The packet must include:

1. Existing simple benchmark families that can be appropriated, including collaborative assembly benchmarks, HRC model sets, NIST Assembly Task Boards, RAMP-like assembly benchmarks, speed-and-separation-monitoring experiments, perceived-safety/preferred-separation experiments, and short-cycle handover benchmarks.
2. For each family: apparatus, task primitives, object types/sizes, starting/target poses, condition structure, metrics, reproducibility assets, and distance from the S2-E1 constrained-process claim.
3. A clear judgement on what to copy: task grammar, metric grammar, condition logic, apparatus modularity, or nothing.
4. A clear judgement on what not to copy: domain identity, full assembly complexity, manipulation novelty, simulation-only RL, or glovebox teleoperation framing.
5. Comparator patterns used in HRC, shared autonomy, collaborative manipulation, safety/separation monitoring, robot obstacle avoidance, and laboratory/process automation benchmarks.
6. What each local comparator type isolates: manual burden, robot usefulness, static automation, safety response, dynamic adaptation, failure recovery, operator control, task continuity, workload, perceived safety or transferability.
7. Whether a manual baseline is necessary, optional, or misleading for S2-E1.
8. Whether a fixed/scripted support condition is meaningful, and what “static” should mean if retained.
9. Whether the first local dynamic condition should be called “dynamic response”, “safety-aware response”, “obstruction-aware support”, “minimum-distance-preserving support”, or another more defensible label.
10. Whether S2-E1 needs two, three, or more local conditions, and the minimum number required to answer the S2 claim without importing S3 or S4.
11. Recommended local S2-E1 condition structure, with pros, cons, source traceability and validity risks.
12. A short section explaining how the same apparatus should support S3, S4 and S5 later without changing the physical benchmark beyond necessity.

## Benchmark families to evaluate first

Evaluate these first, then add only directly relevant sources:

- CT-style collaborative assembly benchmarks: useful for 3D-printable parts, repeated task primitives, manual/automatic/collaborative comparison logic, assembly time and workload metrics.
- HRC Model Set-style apparatus: useful for modular, extendable and distributable task objects.
- NIST Assembly Task Boards and RAMP-like assembly benchmarks: useful for small-part placement, peg/fixture interaction and known start/target poses.
- Speed-and-separation-monitoring or safety-zone experiments: useful for minimum separation, violation count, response latency, stop/slow states, stop time and idle time.
- Perceived-safety and preferred-separation experiments: useful for S3 measurement design, not as the first S2 comparator.
- Short-cycle handover studies: useful only if fixed return/presentation becomes true handover.
- Human-Robot Gym or safe-RL simulation benchmarks: useful only for S4 conceptual comparison, not as the first physical S2 benchmark.

## Local comparator candidates to evaluate

Evaluate, but do not assume, structures such as:

- manual constrained task versus robot-supported constrained task;
- robot-off versus robot-on;
- fixed/scripted robot support versus obstruction-aware robot support;
- stop-only safety response versus slow/stop response;
- support without retained human authority versus support with explicit human override;
- nominal task success versus safety-distance-preserving task support;
- no obstruction versus staged dynamic obstruction;
- within-subject versus between-condition comparisons.

## Hard constraints

- Do not assume C0/C1/C2 is correct.
- Do not add local conditions unless they isolate a necessary S2 claim.
- Do not broaden S2-E1 into a full HRI study.
- Do not promote S3/S4 questions into S2.
- Preserve process-engineering relevance.
- Preserve the distinction between useful support and ordinary obstacle avoidance.
- Treat local comparator design as pending until human approval.
- Keep all output review-side. Do not mutate canonical evidence, Zotero, ontology, decision files or active planning files.

## Acceptance criteria

The packet must answer:

> What simple benchmark grammar should S2-E1 appropriate, and what local condition comparison is required to make S2-E1 a benchmark of constrained-process collaboration rather than ordinary robot obstacle avoidance?

Completion requires:

- output packet exists;
- benchmark families are compared, not merely listed;
- recommendation is explicit and concise;
- local comparator has the minimum number of conditions needed;
- S3/S4/S5 extension path is preserved but not imported into S2;
- all material claims are source-traced or marked uncertain;
- no denied paths, Zotero state, canonical evidence or decision files are mutated.
