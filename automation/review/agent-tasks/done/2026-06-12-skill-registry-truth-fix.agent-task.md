---
artifact_type: workflow
task_schema: agent-task/v1
task_id: 2026-06-12-skill-registry-truth-fix
title: Skill registry truth fix (context-parity repair R1)
status: done
priority: high
task_type: repo-hygiene
created_by: claude_subscription
created_at: 2026-06-11T23:00:00+01:00
claimed_by: claude_subscription
claimed_at: 2026-06-11T23:00:00+01:00
completed_by: claude_subscription
completed_at: 2026-06-11T23:30:00+01:00
executor: claude_subscription
execution_mode: handoff
requires_remote_compute: false
requires_local_model: false
requires_zotero: false
requires_mcp: false
requires_web: false
verification_route: V1_LLM_VERIFIED
risk_level: low
approval_required: true
source_traceability_required: true
repo: tyecam1/obsidian-PhD
branch: claude/skill-registry-truth-fix-2026-06-12
allowed_paths:
  - automation/review/agent-tasks/**/2026-06-12-skill-registry-truth-fix.agent-task.md
denied_paths:
  - 03-concept/**
  - 07-standards/**
  - 01-research-plan/**
  - 02-library/00-papers/**
  - 02-library/01-annotations/**
  - 02-library/02-evidence/**
  - 00-dashboards/**
inputs:
  - automation/review/agent-jobs/2026-06-11-odysseus-memory-skill-context-parity.claude/skill-registry-audit.md
  - automation/config/odysseus_skill_registry.yaml
outputs:
  - automation/config/odysseus_skill_registry.yaml
result_path: automation/config/odysseus_skill_registry.yaml
review_report_path: ""
handoff_model: claude_work_package
handoff_prompt_path: ""
operator_decision_path: ""
linked_pr: "https://github.com/tyecam1/obsidian-PhD/pull/353"
supersedes: []
duplicates: []
notes: "R1 from the approved context-parity decision packet. Change scope (PR-gated, outside allowed_paths by design): automation/config/odysseus_skill_registry.yaml rewrite per skill-registry-audit dispositions; removal of mis-named .agents/skills/cd/ and .claude/skills/cd/ duplicates. Operator approved execution in Cowork session 2026-06-11."
---

# Task: Skill registry truth fix (R1)

Executed in the same PR that carries this task file. Applies the dispositions from
`automation/review/agent-jobs/2026-06-11-odysseus-memory-skill-context-parity.claude/skill-registry-audit.md`:

1. Rename `concept-pressure-decision` → `concept-pressure-decision-packet`; prompt path now resolves and matches the `claude_job.py` task name.
2. Register the 10 previously unregistered scheduled-task prompts; `weekly-zotero-push` carries `dispatchable: false` (external mutation, human lane).
3. Register `automation/prompts/ontology-proposal.md` (V2: feeds ontology proposals).
4. Register the 6 research/routine agent skills; declare the utility-skill non-registration class in the header.
5. Add `prompt_location: codex-cloud` entries for the three Codex app automations, bound to their repo-side contract docs.
6. Remove `.agents/skills/cd/` and `.claude/skills/cd/` (mis-named duplicates of the networkx skill; frontmatter `name: networkx`).

Registry remains policy/contract only; no runner consumes it yet; entries grant no write scope.

## Stop condition

Met when the registry parses, every registered prompt path resolves on the branch, lint passes, and the PR is open as draft. Verification: V1 rubric review by a non-producing lane (Codex), per `verification-routing-policy.md`.

## Close-out

Merged on `main` via PR #353 (commit `33a9ab68`, `config: skill registry truth fix (parity repair R1)`). Deliverable `automation/config/odysseus_skill_registry.yaml` rewrite confirmed present on `origin/main`; mis-named `.agents/skills/cd/` and `.claude/skills/cd/` duplicates removed. Status moved review -> done 2026-06-15.
