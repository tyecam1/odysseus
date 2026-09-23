---
artifact_type: workflow
task_schema: agent-task/v1
task_id: 2026-06-12-adapt-hermes-verification-patterns
title: Adapt Hermes-style checkpoint verification into Odysseus agent execution
status: rejected
priority: high
task_type: implementation
created_by: human
created_at: 2026-06-12T00:05:00+01:00
executor: codex_subscription
execution_mode: handoff
requires_remote_compute: false
requires_local_model: false
requires_zotero: false
requires_mcp: false
requires_web: true
verification_route: V2_HUMAN_VERIFIED
risk_level: medium
approval_required: true
source_traceability_required: true
repo: tyecam1/obsidian-PhD
branch: ""
allowed_paths: []
denied_paths:
  - 03-concept/**
  - 07-standards/**
  - 01-research-plan/**
  - 02-library/00-papers/**
  - 02-library/01-annotations/**
  - 02-library/02-evidence/**
  - 00-dashboards/**
inputs:
  - automation/docs/agent-task-centralisation-plan.md
  - automation/docs/agent-ecosystem-centralisation-design.md
  - automation/docs/agentic-system-platform-assessment-plan.md
  - automation/docs/verification-routing-policy.md
  - automation/docs/agent-task-frontmatter-schema.md
  - Hermes agent / verification-oriented agent pattern discussed in system-planning chat
outputs:
  - automation/docs/agent-execution-verification-contract.md
  - automation/review/architecture/hermes-verification-pattern-adaptation.md
  - automation/review/platform-evaluations/hermes-agent-pattern-adoption.md
result_path: automation/docs/agent-execution-verification-contract.md
review_report_path: ""
handoff_model: codex_work_package
handoff_prompt_path: ""
operator_decision_path: ""
linked_pr: ""
supersedes: []
superseded_by: 2026-06-12-implement-research-integrity-and-handoff-contracts
duplicates: []
notes: "Merged into 2026-06-12-implement-research-integrity-and-handoff-contracts (checkpoint verification, proof-carrying outputs, continuation state are integrity/handoff contract content). Verdict MERGE in automation/review/platform-evaluations/agentic-work-item-consolidation-review.md."
---

# Task brief

## Objective

Adapt the useful architectural pattern from Hermes-style verification agents into Odysseus: agent execution should interleave informal work with explicit checkpoint checks and produce proof-carrying outputs.

This is not a task to adopt Hermes as a framework. It is a task to encode the verification pattern into Odysseus execution contracts, lintable output expectations, and routing policy.

## Core pattern to adopt

```text
agent work / reasoning / implementation
    -> checkpoint validation
    -> continue only if valid
    -> proof-carrying output
    -> independent verification route
```

For Odysseus this becomes:

```text
task claim
    -> scope and path-authority check
    -> implementation or synthesis
    -> intermediate checks
    -> validation/test/lint evidence
    -> review-side output or PR
    -> verifier different from builder for high-risk work
```

## Required implementation work

### 1. Create an agent execution verification contract

Create `automation/docs/agent-execution-verification-contract.md` defining:

- required checkpoints for high-risk and implementation-capable tasks;
- checkpoint vocabulary;
- proof-carrying output requirements;
- continuation-state format for long-running tasks;
- verifier separation rules;
- how checkpoint failures map to `blocked`, `review`, or `rejected` lifecycle states;
- how this contract relates to `verification-routing-policy.md`.

Suggested checkpoint vocabulary:

```yaml
checkpoints:
  - task_scope_read
  - input_sources_resolved
  - path_authority_checked
  - implementation_plan_recorded
  - intermediate_output_validated
  - tests_or_lints_run
  - source_traceability_checked
  - denied_paths_checked
  - review_output_written
```

### 2. Define proof-carrying output metadata

Define a reusable metadata block for review-side outputs and PR-producing tasks:

```yaml
verification_evidence:
  validation_commands_run: []
  tests_run: []
  files_changed: []
  source_paths_consulted: []
  denied_paths_checked: []
  assumptions_open: []
  unresolved_risks: []
  required_human_decisions: []
  verifier_recommendation: "accept|revise|block|human-review"
```

Do not require this in every canonical note. It belongs to review-side outputs, implementation task reports, and PR summaries.

### 3. Define task-local continuation state

For long tasks, define a compact continuation block:

```yaml
continuation_state:
  goal: ""
  current_claim: ""
  verified_steps: []
  failed_steps: []
  open_assumptions: []
  next_action: ""
  source_paths: []
```

This should be used instead of relying on chat memory or opaque model memory.

### 4. Update or propose routing/verification policy changes

Update `verification-routing-policy.md`, `agent-task-centralisation-plan.md`, or `agent-ecosystem-centralisation-design.md` only where the existing contract clearly needs amendment.

Required policy addition:

- high-risk implementation tasks should not be accepted by the same lane that produced them;
- builder and verifier may be the same only for low-risk V0/V1 tasks explicitly allowed by policy;
- V2 remains human verified.

### 5. Add lint/check support if feasible

If straightforward, add tests or lint checks under `Scripts/automation/tests/**` to detect:

- missing `verification_evidence` in review-side task reports where required;
- high-risk implementation tasks without verifier separation;
- tasks claiming validation without command evidence;
- outputs that omit source traceability despite `source_traceability_required: true`.

Do not overbuild a new validation framework. Extend existing automation patterns if available.

### 6. Produce an adoption report

Create `automation/review/architecture/hermes-verification-pattern-adaptation.md` explaining:

- what was adopted;
- what was rejected;
- why Hermes is not being adopted as a framework;
- how checkpoint verification fits Odysseus;
- how this reduces agent drift and silent failure.

Create `automation/review/platform-evaluations/hermes-agent-pattern-adoption.md` with the open/closed decisions and remaining work.

## Closed decisions

- Adopt the Hermes-style principle of interleaving informal agent work with verification checkpoints.
- Adopt proof-carrying output metadata for review-side outputs and implementation reports.
- Adopt task-local continuation state for long-running tasks.
- Reject Hermes as a central framework or replacement for Odysseus.
- Reject model memory as authority; continuation state must be task-local and source-linked.

## Open decisions

- Exact checkpoint set per task type.
- Whether checkpoint evidence should become mandatory front matter or body metadata.
- Whether lint enforcement should be hard-fail immediately or warning-only during transition.
- How much of this belongs in the Claude/Codex execution contracts versus the global agent execution contract.

## Stop conditions

Block or reduce scope if the change would create a new execution framework, a second task lifecycle, canonical write paths, proof-system dependencies unrelated to this vault, or validation bureaucracy that blocks useful work without improving safety.
