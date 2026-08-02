---
artifact_type: workflow
task_schema: agent-task/v1
task_id: 2026-06-17-add-writing-cycle-support
title: Add writing-cycle support to agent workflows
status: rejected
priority: medium
task_type: prompt-workflow-update
created_by: chatgpt
created_at: 2026-06-17T00:00:00+01:00
executor: codex_subscription
execution_mode: handoff
requires_remote_compute: false
requires_local_model: false
requires_zotero: false
requires_mcp: false
requires_web: false
verification_route: V2_HUMAN_VERIFIED
risk_level: low
approval_required: true
source_traceability_required: true
repo: tyecam1/obsidian-PhD
branch: ""
allowed_paths:
  - automation/review/handoff-prompts/2026-06-16-j1-beaver-mcp-evidence-routing.codex-work-package.md
  - automation/review/2026-06-17-agentic-dispatch-and-prompts.md
  - automation/review/routine-reports/writing-cycle-support/**
  - automation/review/agent-tasks/**/2026-06-17-add-writing-cycle-support.agent-task.md
denied_paths:
  - 00-dashboards/**
  - 01-research-plan/**
  - 02-library/00-papers/**
  - 02-library/01-annotations/**
  - 02-library/02-evidence/**
  - 03-concept/**
  - 07-standards/**
  - automation/review/supervisor-office-pack/erfu-simple-supervision-record-final-format.md
inputs:
  - 09-resources/writing/academic-writing-cycle.md
  - 12-log/26-06/26-25/academic-writing-workshop-2026-06-17.md
outputs:
  - automation/review/routine-reports/writing-cycle-support/2026-06-17.writing-cycle-support.md
result_path: automation/review/routine-reports/writing-cycle-support/2026-06-17.writing-cycle-support.md
review_report_path: automation/review/routine-reports/writing-cycle-support/2026-06-22.scope-adjudication.md
handoff_model: ""
handoff_prompt_path: ""
operator_decision_path: ""
linked_pr: ""
supersedes: []
duplicates: []
notes: "Rejected on 2026-06-22 because execution changed active paths outside the declared review-only allowlist. Existing history was preserved; no retrospective scope expansion was applied."
verification_verdict: reject
verification_by: human
---

# Add writing-cycle support to agent workflows

## Objective

Update agent-facing writing and review workflows so agents support multi-pass academic writing rather than treating writing tasks as single-pass drafting or polishing.

## Required changes

1. Add writing-pass classification to relevant prompts:
   - human free-write
   - evidence pass
   - structural edit
   - style pass
   - final technical check

2. Use the reusable workflow at:
   - `09-resources/writing/academic-writing-cycle.md`

3. Update J1 writing and evidence-review prompts so agents identify:
   - paragraph premises
   - missing premise chains
   - unsupported claims
   - citation lists without synthesis
   - sections drifting away from the paper's central idea

4. Add the following block to supervision-prep templates or generated supervision-prep notes where relevant:

```markdown
## Writing / output coaching check

- Current output:
- Single idea this output must communicate:
- Current blocker:
- Decision needed from supervisor:
- Deliverable before next meeting:
```

## Boundaries

- Do not modify Zotero or Beaver MCP behaviour.
- Do not mutate canonical evidence ontology.
- Do not change the supervisor-facing Excel format.
- Do not add external writing or project-management software.
- External tools are acceptable only for system design, diagrams or experimental architecture.

## Acceptance criteria

- Agent writing prompts distinguish evidence routing from structural editing and final checking.
- Agents are instructed not to polish human free-writing prematurely.
- J1 review prompts include premise-chain and central-idea checks.
- Supervision preparation can include the coaching block without altering supervisor-facing records.
