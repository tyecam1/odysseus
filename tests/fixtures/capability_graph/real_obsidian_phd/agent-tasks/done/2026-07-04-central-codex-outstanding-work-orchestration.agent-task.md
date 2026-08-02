---
artifact_type: agent-task
task_schema: agent-task/v1
task_id: 2026-07-04-central-codex-outstanding-work-orchestration
title: "Central Codex outstanding work orchestration"
status: done
priority: high
task_type: orchestration
created_by: chatgpt
created_at: 2026-07-04T17:00:00+01:00

executor: codex_subscription
execution_mode: central-orchestrator
requires_remote_compute: false
requires_local_model: false
requires_zotero: false
requires_mcp: false
requires_web: false

verification_route: V2_HUMAN_VERIFIED
risk_level: high
approval_required: true
source_traceability_required: true

repo: tyecam1/obsidian-PhD
branch: codex/central-outstanding-work-20260704
allowed_paths:
  - automation/review/**
  - automation/docs/**
  - .github/**
  - Scripts/**
  - 08-template/**
  - 10-inbox/**
  - 00-dashboards/**
  - README.md
  - AGENTS.md
denied_paths:
  - 01-research-plan/**
  - 02-library/00-papers/**
  - 02-library/01-annotations/**
  - 02-library/02-evidence/**
  - 03-concept/**
  - 04-supportDesign/**
  - 07-standards/**
  - 11-projects/**
  - 12-log/**
  - My Library.bib
  - 02-library/My Library.bib
  - "**/*.pdf"

inputs:
  - automation/review/decision-packets/2026-07-03-repo-future-operating-plan.decision-packet.md
  - automation/review/decision-packets/2026-07-03-first-five-work-items.dispatch.md
  - automation/review/decision-packets/2026-07-03-review-lane-batch-adjudication.decision-packet.md
  - automation/review/agent-tasks/ready/2026-07-03-review-lane-batch-adjudication.agent-task.md
  - 10-inbox/backlog.md
  - 10-inbox/update-j1-journal-plan-and-write-draft.md
  - 10-inbox/approve-s2-experiment-split-and-optimisation-boundaries.md
  - 10-inbox/s3-event-measurement-decision.md
outputs:
  - automation/review/routine-reports/central-codex-outstanding-work/2026-07-04-orchestration-run-report.md
  - automation/review/decision-packets/2026-07-04-outstanding-work-residuals.decision-packet.md
  - pull_request: central outstanding work batch
result_path: automation/review/routine-reports/central-codex-outstanding-work/2026-07-04-orchestration-run-report.md
review_report_path: automation/review/decision-packets/2026-07-04-outstanding-work-residuals.decision-packet.md
handoff_model: codex_work_package
handoff_prompt_path: automation/review/agent-tasks/inbox/2026-07-04-central-codex-outstanding-work-orchestration.agent-task.md

operator_decision_path: automation/review/decision-packets/2026-07-04-outstanding-work-residuals.decision-packet.md
linked_pr: ""
supersedes: []
duplicates: []

notes: "Central orchestration run completed as a draft PR with run report and residual decision packet. Human-gated residue remains in the residual packet; no canonical paths were modified."
---

# Central Codex outstanding work orchestration

## Context

The repo already contains an operating plan and a first-five dispatch note. This task turns the remaining outstanding work into a single central Codex run that can spawn specialised subagents, execute safe deterministic changes, and produce review-side decision packets for anything requiring human judgement.

Current constraints:

- Do not delete branches unless they are merged or explicitly approved by a human decision record.
- Do not run branch pruning until three fresh daily heartbeat dates are visible on `main` after `REMOTE_UPKEEP_HEARTBEAT_TO_MAIN=true` activation.
- Do not fabricate heartbeat artifacts.
- Do not convert held W4 work unless the repository now explicitly supersedes that hold.
- R3 remains off.
- Do not write canonical research content under `01-research-plan/**`, `02-library/**`, `03-concept/**`, `04-supportDesign/**`, `07-standards/**`, `11-projects/**`, or `12-log/**`.
- Agents may prepare review-side drafts, decision packets, reports, lint checks, templates, and work-item hygiene changes.
- Silence is never approval.

## Central Codex prompt

```text
You are Codex acting as the central orchestrator on tyecam1/obsidian-PhD.

Goal:
Make all outstanding repo-system, review-lane, J1, S2, metadata, automation, AI-use, and blackout-routing work visible, deduplicated, and as complete as safely possible. Spawn specialised subagents where useful, but keep one central run report and one residual decision packet. Do not create another planning layer.

Repository and safety constraints:
- Work from a fresh branch: codex/central-outstanding-work-20260704.
- Pull latest main before doing anything.
- Do not delete branches.
- Do not prune branches.
- Do not fabricate heartbeat artifacts.
- Do not mutate external systems unless explicitly listed as safe in an existing agent-task and verified.
- Do not write canonical research content under 01-research-plan/**, 02-library/**, 03-concept/**, 04-supportDesign/**, 07-standards/**, 11-projects/**, 12-log/**, PDFs, or BibTeX files.
- Do not treat review-side draft outputs as canonical research truth.
- Do not create new queue roots, new backlog systems, new dashboards, or new planning layers.
- Do not self-merge judgement-heavy work.
- If a step requires human judgement, create or update a bounded decision packet and stop that step.
- If a gate fails, stop the affected lane and record the blocker.

Required inputs to inspect first:
- automation/review/decision-packets/2026-07-03-repo-future-operating-plan.decision-packet.md
- automation/review/decision-packets/2026-07-03-first-five-work-items.dispatch.md
- automation/review/decision-packets/2026-07-03-review-lane-batch-adjudication.decision-packet.md
- automation/review/agent-tasks/ready/2026-07-03-review-lane-batch-adjudication.agent-task.md
- automation/review/agent-tasks/**
- automation/review/routine-reports/**
- automation/docs/**
- 08-template/**
- 10-inbox/**
- 00-dashboards/**
- Scripts/**
- .github/**
- J1 control files discovered by search: j1-ground-truth-plan, j1-execution-plan, j1-evidence-map, j1Hub, section skeletons, and recent J1 evidence audits.

Spawn these specialised subagents. Each subagent must write a concise report section into:
automation/review/routine-reports/central-codex-outstanding-work/2026-07-04-orchestration-run-report.md

Subagent A — Inventory and dependency auditor
Task:
- Build a complete inventory of outstanding work from agent-tasks, 10-inbox, decision-packets, routine reports, backlog.md, J1 files, and the July/August blackout plan.
- Mark each item as: complete, active, duplicate, superseded, blocked, unsafe-for-agent, or ready-for-agent.
- Tie every classification to an inspected path.
Deliverable:
- Inventory table.
- Dependency graph in text form.
- List of duplicate/superseded work items that can be moved or linked.
Stop:
- If a work item touches canonical research paths, classify it but do not edit it.

Subagent B — Review-lane and operating-debt agent
Task:
- Continue from the existing review-lane batch adjudication packet and first-five dispatch note.
- Verify whether W1-W5 from the repo future operating plan are done, still pending, or blocked.
- For each pending item, either execute safe review-side lifecycle moves or create a bounded residual decision entry.
- Do not delete branches. Do not prune branches unless all heartbeat gate conditions are already satisfied on main and explicit approval exists.
Deliverable:
- Review-lane status summary.
- Residual move plan if human approval is required.
- Evidence that no heartbeat or branch-deletion rule was violated.
Stop:
- Any unverified branch content, missing heartbeat day, or non-main heartbeat artifact.

Subagent C — Human work-item inbox curator
Task:
- Normalise and simplify 10-inbox without inventing tasks.
- Move already completed human work items to 10-inbox/complete only when completion is evidenced in repo context.
- Consolidate duplicates by updating or linking the surviving work item; do not scatter new notes.
- Ensure current human-gated work is visible in backlog.md or the canonical current inbox route.
- Preserve the July/August lab-access constraint: before 2026-07-28 = lab/physical/communications; 2026-07-28 to 2026-08-28 = writing, evidence, CAD, protocol, non-physical modelling.
Deliverable:
- Minimal diff to 10-inbox and backlog.md.
- Report of moved, consolidated, and untouched items.
Stop:
- Any ambiguous completion claim.

Subagent D — J1 spine and control-file consolidator
Task:
- Inspect J1 control files and recent J1 evidence outputs.
- Reduce contradictory or redundant planning where safe by linking to one canonical control source.
- Do not draft manuscript prose.
- Ensure the J1 spine is explicit in review-side planning: industrial HRC should not be judged by technical task success alone, but by task, safety, exception/recovery, and worker-role conditions that make collaboration worth adopting.
- Ensure these pasted-scan insights are represented in a review-side J1 work product or TODO list: exception/recovery as the hidden cross-perspective connection; worker-role outcomes as adoption evidence; missing counterfactuals; skill-formation blind spot; worker-centric rhetoric versus measurable role-quality evidence.
Deliverable:
- A concise review-side J1 consolidation report or matrix under automation/review/J1/ or automation/review/routine-reports/central-codex-outstanding-work/.
- Links from existing J1 work items to the chosen source where safe.
Stop:
- Any need to change canonical claim strength, ontology, evidence promotion, or manuscript prose.

Subagent E — J1 evidence and reporting-matrix agent
Task:
- Create or update a J1 reporting matrix if missing.
- Rows must include: task context; human role before support; human role after support; exception/recovery responsibility; intervention authority; comparator condition; worker voice/participation; skill formation/training exposure; human-factor measure; transferability limits; industrial adoption mechanism; standards/safety boundary.
- For each row, route to existing evidence, missing evidence, manuscript section, and required claim type.
- Do not fabricate sources. Missing evidence must be marked as missing.
Deliverable:
- Review-side matrix under automation/review/J1/ or another existing review-side J1 location.
Stop:
- Any request to promote evidence into 02-library or 03-concept.

Subagent F — Metadata, template, and schema hardening agent
Task:
- Audit current metadata/front-matter usage, templates, and validation scripts.
- Apply only minimal schema hardening that reduces future overhead.
- Preserve artifact_type categories already in use, including: reference node, reference link, impact node, impact link, success criteria, standard, KPI, evidence, research-question, work-item, agent-task.
- If safe, update template/docs/lint so they support: DRM stage, substudy S1-S5, status, evidence_role, linked_claims, linked_research_questions, source/ref key, and AI-use/disclosure where materially relevant.
- Do not mass-edit the vault to satisfy a new schema.
Deliverable:
- Small template/docs/script diff or a decision packet explaining why no edit is safe.
Stop:
- Any migration touching canonical notes or large file sets.

Subagent G — S2 benchmark and blackout scaffold agent
Task:
- Create or update a review-side S2 benchmark decision scaffold for preparative handling versus constrained manipulation/glovebox point-cell work.
- Include: candidate task, why it matters, human role, robot role, material/process state, exception/recovery events, measurable success criteria, comparator baselines, physical feasibility before 2026-07-28, writing-only tasks for 2026-07-28 to 2026-08-28, and unresolved decisions.
- Respect current direction: constrained manipulation / glovebox point-cell is promoted, but preparative handling remains a comparative benchmark option unless explicitly superseded.
Deliverable:
- Review-side scaffold under automation/review/operator-decisions/ or automation/review/S2/.
Stop:
- Any attempt to create final experimental protocol, H&S submission, or canonical support-design content without human approval.

Subagent H — Automation QA agent
Task:
- Inspect existing validation, agent-task lint, link checks, front-matter checks, and GitHub Actions.
- Add or improve lightweight checks only where they enforce already accepted rules.
- Target checks: broken internal links; required front matter for agent-tasks; duplicate open work-item titles; dated inbox files older than threshold; accidental large binaries excluding approved PDFs/assets; new queue roots or backlog-shaped files outside approved roots.
- Default to advisory warnings unless an error is safe and obvious.
Deliverable:
- Minimal scripts/.github diff with local validation evidence.
Stop:
- Any noisy gate likely to block normal research writing.

Subagent I — AI-use and reproducibility workflow agent
Task:
- Create or refine a minimal AI-use and reproducibility disclosure workflow.
- Include a short AI-use disclosure field/template only where AI materially shaped content.
- Include a reproducibility note template covering: search source, query/prompt, tool used, date, human verification status, output location.
- Do not force AI metadata into every ordinary note.
Deliverable:
- Template/docs update and one example review-side note if useful.
Stop:
- Any workflow that creates high daily overhead.

Subagent J — Independent verifier
Task:
- Review all diffs from the other subagents.
- Confirm the work obeys the path restrictions and did not create new planning layers.
- Run available validation/lint/test commands.
- Check that each outstanding item is either completed, safely updated, linked to an existing task, or listed in the residual decision packet.
Deliverable:
- Verification section in the central run report.
- One residual decision packet:
  automation/review/decision-packets/2026-07-04-outstanding-work-residuals.decision-packet.md
Stop:
- Any unexplained mutation, uncited completion claim, or canonical-path write.

Required final outputs:
1. A PR from codex/central-outstanding-work-20260704 to main.
2. A central run report at:
   automation/review/routine-reports/central-codex-outstanding-work/2026-07-04-orchestration-run-report.md
3. A residual decision packet at:
   automation/review/decision-packets/2026-07-04-outstanding-work-residuals.decision-packet.md
4. Existing work items updated, moved, linked, or marked blocked only where evidence supports the change.
5. A concise PR summary containing:
   - What changed.
   - Which outstanding items are now done.
   - Which items remain blocked and why.
   - Which validation commands passed/failed.
   - Any required human decisions.

Acceptance criteria:
- All outstanding work is visible in exactly one surviving route: agent-task, 10-inbox item, decision packet, or explicit residual blocker.
- No duplicate task worlds or new queue roots are introduced.
- No canonical research note, evidence note, concept node, support-design note, PDF, log, or BibTeX file is modified.
- No branch deletion or pruning is performed without the heartbeat and approval gates.
- Missing evidence is labelled missing, not filled by guesswork.
- J1 now has an explicit review-side matrix for worker-role / exception-recovery / comparator / skill-formation reporting conditions.
- S2 now has a review-side scaffold separating pre-2026-07-28 physical tasks from 2026-07-28 to 2026-08-28 blackout-suitable writing and modelling tasks.
- Metadata/schema changes are minimal and do not require mass migration.
- Validation evidence is included in the PR.

Commit and PR discipline:
- Use small commits grouped by subagent lane.
- Keep the PR bounded. If the diff becomes too large, split into sequential PRs and keep the central run report as the index.
- Do not merge your own PR if judgement-heavy changes are included.
```

## Acceptance criteria for this handoff

- The central orchestration prompt exists on the repo.
- The prompt references existing operating-plan and dispatch artifacts instead of replacing them.
- The prompt routes outstanding work through specialised subagents while preserving human authority over canonical research decisions.
- The prompt can be pasted directly into Codex.
