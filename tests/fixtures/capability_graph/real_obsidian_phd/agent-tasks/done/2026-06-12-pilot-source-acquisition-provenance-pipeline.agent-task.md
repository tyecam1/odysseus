---
artifact_type: workflow
task_schema: agent-task/v1
task_id: 2026-06-12-pilot-source-acquisition-provenance-pipeline
title: Pilot source acquisition provenance pipeline (crawl4ai + Stirling PDF)
status: done
priority: high
task_type: implementation
created_by: human
created_at: 2026-06-12T12:05:00+01:00
executor: codex_subscription
execution_mode: handoff
requires_remote_compute: true
requires_local_model: false
requires_zotero: false
requires_mcp: false
requires_web: true
verification_route: V2_HUMAN_VERIFIED
risk_level: high
approval_required: true
source_traceability_required: true
repo: tyecam1/obsidian-PhD
branch: ""
allowed_paths:
  - automation/review/platform-evaluations/source-acquisition-provenance-pilot.md
  - automation/review/architecture/source-acquisition-pipeline.md
denied_paths:
  - 03-concept/**
  - 07-standards/**
  - 01-research-plan/**
  - 02-library/00-papers/**
  - 02-library/01-annotations/**
  - 02-library/02-evidence/**
  - 00-dashboards/**
inputs:
  - automation/review/architecture/odysseus-consolidated-system-design.md
  - automation/docs/governed-library-pdf-import.md
  - automation/docs/agent-ecosystem-centralisation-design.md
  - crawl4ai repository/docs
  - Stirling PDF repository/docs
outputs:
  - automation/review/platform-evaluations/source-acquisition-provenance-pilot.md
  - automation/review/architecture/source-acquisition-pipeline.md
result_path: automation/review/platform-evaluations/source-acquisition-provenance-pilot.md
review_report_path: automation/review/platform-evaluations/source-acquisition-provenance-pilot.md
handoff_model: codex_work_package
handoff_prompt_path: ""
operator_decision_path: ""
linked_pr: ""
supersedes:
  - 2026-06-12-evaluate-source-acquisition-and-ops-sidecars
duplicates: []
notes: "Narrowed rewrite of the eleven-candidate sidecar omnibus: crawl4ai and Stirling PDF only, plus the provenance contract. Ops sidecars (Coolify, Supabase, Browser-use, Maxun, Graphify, find-skills, Langflow, Dify) are dispositioned on the consolidated design defer/pattern lists, not here. Evaluation and policy only — no installs, no deployment, no crawling, no endpoint exposure, no canonical paper processing."
---

# Task brief

## Objective

Define and pilot the provenance-preserving source acquisition pipeline using crawl4ai (public web → markdown) and Stirling PDF (local PDF preprocessing/OCR) as bounded sidecars subordinate to the vault.

## Deliverables (staged review-side, promoted via draft PR)

1. Source acquisition policy: mandatory provenance fields per acquisition (source URL/file, retrieved_at, content hash, raw snapshot path, clean output path, extraction method, tool version/commit, access/licence note, `data_access_level`, promotion status, linked task, verification status); raw versus processed separation; the rule that crawled/OCR/transformed text is never canonical evidence until promoted through the existing review/evidence workflow.
2. Review-side snapshot layout: where raw and processed acquisition artifacts live under `automation/review/**`.
3. Pipeline architecture note aligning acquisition with the integrity gate flow: source → raw snapshot → preprocessing → candidate extraction → handoff validation → integrity gate → human review → canonical promotion.
4. Pilot recommendation: whether crawl4ai and Stirling PDF should each receive a bounded implementation task, with explicit allowlist/denylist (no authenticated pages, no form submission, no paywalled content, no destructive PDF modification).

## Stop conditions

Block if implementation would install or deploy services, expose endpoints, crawl external sites, mutate PDFs destructively, process canonical papers or evidence files, store secrets in repo files, or mark acquired content canonical without human review.
