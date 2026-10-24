---
artifact_type: agent-task
task_schema: agent-task/v2
task_id: 2026-10-22-phd-supervision-progress-automation
title: "Automate approved PhD supervision progress register after each meeting"
status: inbox
priority: high
task_type: implementation
created_by: chatgpt
created_at: 2026-10-22T12:00:00+01:00
updated_at: 2026-10-22T12:00:00+01:00
executor: claude_subscription
execution_mode: review-first
architecture: single-plus-verifier
architecture_rationale: "One agent integrates the approved workbook and existing PhD staging workflow. A separate verifier checks evidence fidelity, workbook preservation and external sharing safety."
single_agent_baseline: "One implementation agent plus focused independent review."
execution_host: primary
context_budget: medium
coordination_reason: "Crosses PhD evidence extraction, workbook update, automation scheduling and university OneDrive publishing."
requires_remote_compute: false
requires_local_model: false
requires_zotero: false
requires_mcp: false
requires_web: false
verification_route: V2_HUMAN_VERIFIED
risk_level: medium
approval_required: true
source_traceability_required: true
repo: tyecam1/obsidian-PhD
branch: ""
allowed_paths:
  - Scripts/automation/**
  - automation/review/supervisor-office-pack/**
  - tests/**
denied_paths:
  - "**/.env"
  - "**/secrets/**"
inputs:
  - automation/review/supervisor-office-pack/erfu-pivotal-register-contract.md
  - automation/review/supervisor-office-pack/2026-10-22-supervision-record-approval.md
  - Scripts/automation/supervision_register_export.py
  - Scripts/automation/erfu_supervision_review_check.ps1
  - Scripts/automation/install_erfu_supervision_review_task.ps1
  - "approved workbook SHA256: 7d79dfbe15d0c115eaf19cf443b03f1d50c02a8686a6f501f03e84f10c1062e6"
outputs:
  - event-driven or quiet change-detected workbook update pipeline
  - exact three-sheet approved baseline preservation
  - evidence and supervisor-attribution checks
  - staged release and approved OneDrive publication procedure
  - tests on representative new, revised, agenda-only and no-change notes
result_path: automation/review/supervisor-office-pack/erfu-pivotal-register-contract.md
review_report_path: automation/review/supervisor-office-pack/supervision-progress-updater-verification.md
handoff_model: gpt-6
operator_decision_path: ""
supersedes: []
duplicates: []
notes: "Do not reinstate legacy exporter, create another backend queue, or claim a live scheduled trigger or successful OneDrive sharing without deployment tests."
---

# Implement the approved PhD supervision record update workflow

## Authorised baseline

On 22 October 2026, Tye approved the exact Excel workbook `Tye Cameron-Robson - Supervision Progress Record.xlsx`, SHA-256 `7d79dfbe15d0c115eaf19cf443b03f1d50c02a8686a6f501f03e84f10c1062e6`. The file is privately available to the operator and is **not yet verified to be in OneDrive**.

The workbook's only sheets are `Research overview`, `Supervision history` and `Next priorities`. Do not replace it with the deprecated multi-sheet register or one-page Word export. The new contract is in PhD PR #620, which must be reconciled with live main before execution: https://github.com/tyecam1/obsidian-PhD/pull/620

## Goal

Following a completed, source-backed supervision meeting note, agents update the approved workbook's pivotal outcomes and forward priorities in the user's established plain-academic style, with no redundant human review burden. The same workbook is intended for both Erfu Yang and Richard Millar.

## Implementation order

1. Preflight and check live tasks, current authority and PR state before editing. Retain Odysseus ownership of task execution; all PhD-specific evidence and document rules live in the PhD repository.
2. Verify the exact operator-approved workbook. Arrange its first safe placement at `C:\Users\tyeca\OneDrive - University of Strathclyde\Erfu Yang's files - Tye Cameron-Robson\Tye Cameron-Robson - Supervision Progress Record.xlsx`. Check that Erfu and Richard have appropriate, least-privilege access. No unrelated folder sharing.
3. Wire a quiet change trigger to **completed supervision notes** involving Erfu, Richard, or an explicitly relevant CPI discussion. A prepared agenda does not qualify. Event-based if feasible, otherwise silent daily change detection. It must not open Notepad, send repetitive reminders or react to nonmaterial edits.
4. Read dated notes and the most recent canonical research programme sources. Reconcile only genuinely pivotal guidance, decisions, material progress, methodological changes, blockers and next steps. Preserve user-edited history and remove superseded priorities. Include no speculative results, outdated broad research question, or internal agent workflow in the supervisor-facing workbook.
5. Update `Supervision history` with the minimal factual delta. Revise `Research overview` only when the scientific position changes; keep its current manufacturing-objective J1, latest J2 and measurement-first S2 focus. Reconcile `Next priorities`. Preserve sheet names, structure, user edits, minimal dark-green styling, and ordinary hyphens.
6. Validate source coverage, attribution, dates, no duplicates, current research state, missing evidence, row integrity and visual spreadsheet readability. Stage the candidate and a concise diff with exact hash; do not replace the shared workbook when verification fails.
7. Implement publishing with the release gate in the PhD contract. The user has approved the historical baseline, **not unobserved future meeting claims**. Obtain explicit approval for changed supervisor-facing content unless the operator separately authorises and tests a narrower automatic-publication rule.
8. Use verified, accepted changes for the next meeting's decision questions and progress review. Route any proposed research tasks through existing Odysseus ownership with duplicate checks, never through the shared spreadsheet.

## Acceptance

- Baseline workbook SHA matches before first installation. No altered original historical row or user correction.
- Representative test meeting produces precisely one correctly attributed new row and reconciles affected priorities.
- A mere agenda, a duplicate or a nonmaterial note edit creates no new external content.
- A revised note stages a corrected candidate without creating an obsolete action or silently overwriting the previously approved version.
- New J1/J2/S2 text follows current canonical directives and the dated evidence; no claims of achieved results without support.
- The updater is tested on the actual Windows/OneDrive path; published bytes and sync/permission access for both supervisors are verified.
- Any inability to verify OneDrive write access or Richard's sharing permission is reported as blocked, not success.
- No popups, daily approval demands, extra Word exports, competing agent-task authority or unattended publication of unapproved meeting claims.

## Current constraints

SharePoint/OneDrive write access is not connected to ChatGPT in the session where the workbook was approved. GitHub changes cannot install a Windows task or confirm folder permissions. Do not close this item until the local integration and supervisor access are demonstrated.
