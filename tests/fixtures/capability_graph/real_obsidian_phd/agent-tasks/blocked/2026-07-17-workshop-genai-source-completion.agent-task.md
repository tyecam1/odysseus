---
artifact_type: agent-task
task_schema: agent-task/v1
task_id: 2026-07-17-workshop-genai-source-completion
title: Complete workshop recording inputs
status: blocked
blocked_reason: external_media_transcripts_and_timing_not_supplied
recheck_trigger: operator_supplies_listed_inputs_and_privacy_confirmation
priority: medium
task_type: evidence-extraction
created_by: fable-route-loop
created_at: 2026-07-17T00:00:00+00:00
executor: human
execution_mode: handoff
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
  - automation/review/sources/workshop-genai-researcher-2026/**
denied_paths:
  - 03-concept/**
  - 07-standards/**
  - 01-research-plan/**
  - 02-library/00-papers/**
  - 02-library/01-annotations/**
  - 02-library/02-evidence/**
  - 00-dashboards/**
inputs:
  - external segmented workshop .m4a files
  - external timestamped transcript files
  - external Zoom comment-log export
  - operator-supplied recording start clock and recorded date
outputs:
  - automation/review/sources/workshop-genai-researcher-2026/manifest.json
  - automation/review/sources/workshop-genai-researcher-2026/transcripts/*.cues.json
  - automation/review/sources/workshop-genai-researcher-2026/comment-log.cues.json
  - automation/review/sources/workshop-genai-researcher-2026/status.md
result_path: automation/review/sources/workshop-genai-researcher-2026/status.md
review_report_path: ""
handoff_model: claude_work_package
handoff_prompt_path: ""
operator_decision_path: ""
linked_pr: ""
supersedes: []
duplicates: []
notes: "Human-owned continuation with a claude_work_package handoff. Source slides are registered and 92 page-anchored extraction items are staged; media and full transcripts remain external."
---

# Complete workshop recording inputs

## Problem

The slide source and page-anchored extraction are complete, but recording-derived timing and participant-comment context cannot be staged until the operator supplies the remaining external inputs.

## Exact pending inputs

- Segmented `.m4a` files, in recording order, with segment number, duration, and global start offset for each.
- One timestamped VTT, SRT, or Whisper-style JSON transcript per audio segment, plus the transcription-model name when known.
- The Zoom comment-log text export.
- The recording start clock as ISO-8601 with UTC offset.
- The true recorded date; the manifest currently stores `null` from the `unknown` sentinel.

## Scope

Register the external audio segments, run the documented `add-transcript` and `add-comment-log` commands, rerun `ingest-extraction` only for new recording/comment-located candidates, and regenerate `status`.

## Exclusions

- Do not copy source media or full transcript prose into the repository.
- Do not retain comment authors unless the operator explicitly approves `--keep-authors`.
- Do not promote extraction-derived content to evidence or canonical notes.

## Acceptance criteria

- Every audio segment has validated non-overlapping global timing and a normalized cue file.
- Comment-log parse losses and pre-start untimed comments are reported.
- `status.md` lists no supplied input as pending.
- Human review confirms source completeness and privacy handling.
