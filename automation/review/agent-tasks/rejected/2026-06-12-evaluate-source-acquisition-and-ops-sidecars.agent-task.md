---
artifact_type: workflow
task_schema: agent-task/v1
task_id: 2026-06-12-evaluate-source-acquisition-and-ops-sidecars
title: Evaluate source acquisition and remote-ops sidecars for Odysseus
status: rejected
priority: high
task_type: implementation
created_by: human
created_at: 2026-06-12T01:05:00+01:00
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
  - automation/docs/agentic-system-platform-assessment-plan.md
  - automation/docs/agent-ecosystem-centralisation-design.md
  - automation/docs/agent-task-centralisation-plan.md
  - automation/docs/research-integrity-gate-contract.md
  - automation/docs/data-access-level-policy.md
  - crawl4ai repository/docs
  - Stirling PDF repository/docs
  - OpenHands repository/docs
  - Coolify repository/docs
  - Supabase repository/docs
  - Browser-use repository/docs
  - Maxun repository/docs
  - Graphify repository/docs
  - find-skills repository/docs
  - Langflow repository/docs
  - Dify repository/docs
outputs:
  - automation/review/platform-evaluations/source-acquisition-and-ops-sidecars-evaluation.md
  - automation/docs/source-acquisition-sidecar-policy.md
  - automation/docs/remote-service-deployment-policy.md
  - automation/config/source_acquisition_allowlist.yaml
  - automation/review/architecture/source-acquisition-and-ops-sidecar-adaptation.md
result_path: automation/review/platform-evaluations/source-acquisition-and-ops-sidecars-evaluation.md
review_report_path: automation/review/platform-evaluations/source-acquisition-and-ops-sidecars-evaluation.md
handoff_model: codex_work_package
handoff_prompt_path: ""
operator_decision_path: ""
linked_pr: ""
supersedes: []
superseded_by: 2026-06-12-pilot-source-acquisition-provenance-pipeline
duplicates: []
notes: "Rewritten as 2026-06-12-pilot-source-acquisition-provenance-pipeline, narrowed to crawl4ai + Stirling PDF + provenance contract; ops-sidecar dispositions moved to the consolidated design defer list. Verdict REWRITE in automation/review/platform-evaluations/agentic-work-item-consolidation-review.md."
---

# Task brief

## Objective

Evaluate source acquisition, PDF preprocessing, browser automation, coding-agent sandbox, remote deployment, and runtime-state sidecars for Odysseus. The goal is to decide which capabilities should be piloted, deferred, rejected, or absorbed as patterns while preserving the vault as canonical authority.

This task must not install, deploy, expose, crawl, process canonical evidence, or mutate services. It is an evaluation and policy task only unless a small repo-local test/lint is clearly safe.

## Candidates to evaluate

Evaluate the following as bounded sidecars or pattern sources:

- `crawl4ai` — public web/source-to-markdown acquisition sidecar;
- `Stirling PDF` — local PDF preprocessing/OCR/transformation sidecar;
- `OpenHands` — coding-agent sandbox/evaluation pattern source;
- `Coolify` — remote-box deployment plumbing candidate;
- `Supabase` — derived runtime/dashboard state candidate;
- `Browser-use` — bounded browser automation candidate;
- `Maxun` — browser/web extraction candidate;
- `Graphify` — repo/code graph extraction pattern source;
- `find-skills` — skill discovery metadata pattern source;
- `Langflow` — visual LLM workflow prototype canvas;
- `Dify` — LLM app prototype canvas.

## Required work

### 1. Inspect existing Odysseus contracts

Review current docs and configs before creating new files:

- platform assessment plan;
- agent ecosystem centralisation design;
- agent task centralisation plan;
- any MCP/browser policy;
- any research-integrity gate contract;
- any data-access policy;
- any existing source acquisition, Zotero, PDF, or evidence intake docs;
- any existing remote deployment docs or capability manifests.

Do not duplicate an existing policy if it should be amended instead.

### 2. Produce sidecar evaluation report

Create `automation/review/platform-evaluations/source-acquisition-and-ops-sidecars-evaluation.md`.

For each candidate, include:

```yaml
candidate:
role:
primary_value:
fit_for_odysseus:
risks:
authority_boundary:
recommended_status: adopt_candidate | pattern_source | defer | reject
required_policies_before_use:
pilot_conditions:
stop_conditions:
```

At minimum, answer:

- Should `crawl4ai` become the default public web-to-markdown acquisition sidecar?
- Should `Stirling PDF` become the default local PDF preprocessing/OCR utility?
- Should `OpenHands` influence Codex sandbox/evaluation contracts?
- Should `Coolify` manage remote-box service lifecycle later?
- Should `Supabase` ever store derived runtime/dashboard state, or are markdown/Git/SQLite sufficient?
- Should `Browser-use` or `Maxun` be considered after Playwright/browser policy exists?
- Should `Graphify` feed repository maps, Graphiti memory, or neither?
- Should `find-skills` be absorbed by skill registry work?
- Should `Langflow` and `Dify` remain prototype-only?

### 3. Create source acquisition sidecar policy

Create `automation/docs/source-acquisition-sidecar-policy.md` defining how web/PDF sidecars may be used.

The policy must require every source acquisition output to preserve:

```yaml
source_url_or_file:
retrieved_at:
content_hash:
raw_snapshot_path:
clean_output_path:
extraction_method:
tool_version_or_commit:
access_or_license_note:
data_access_level:
promotion_status:
linked_agent_task:
verification_status:
```

The policy must distinguish:

```text
raw source
processed source
candidate extraction
review-side evidence
canonical evidence
```

and must explicitly state that transformed/crawled/OCR text is not canonical evidence until promoted through the existing review/evidence workflow.

### 4. Create remote service deployment policy

Create `automation/docs/remote-service-deployment-policy.md` defining how tools such as Coolify, Supabase, RAGFlow, Graphiti, Open WebUI, LibreChat, crawl4ai servers, Stirling PDF, browser agents, and n8n may be deployed.

The policy must cover:

- remote-box-first deployment;
- no laptop-local long-running services unless explicitly approved;
- no public endpoints without security review;
- secret handling and `.env` rules;
- backup/restore expectations;
- service inventory requirements;
- port exposure rules;
- update/rollback rules;
- logging and retention;
- which service state is canonical versus derived;
- how service changes are represented as agent tasks or PRs.

### 5. Create or defer source acquisition allowlist

Create `automation/config/source_acquisition_allowlist.yaml` unless a better config location already exists.

Suggested initial structure:

```yaml
version: 1
mode: explicit_allowlist
raw_outputs_are_canonical: false
sidecars:
  crawl4ai:
    status: evaluate
    allowed_for:
      - public_web_to_markdown
      - public_report_snapshot
      - documentation_snapshot
    denied_for:
      - authenticated_pages
      - form_submission
      - paywalled_content
      - private_user_data
      - canonical_evidence_write
  stirling_pdf:
    status: evaluate
    allowed_for:
      - local_pdf_split
      - local_pdf_merge
      - local_pdf_ocr
      - local_pdf_to_images
      - pre_ingestion_transform
    denied_for:
      - canonical_evidence_write
      - destructive_original_modification
  browser_use:
    status: defer_until_browser_policy
  maxun:
    status: defer_until_browser_policy
  coolify:
    status: defer_until_deployment_policy
  supabase:
    status: defer_until_runtime_state_policy
```

Adapt this to existing repo conventions.

### 6. Optional architecture note

Create `automation/review/architecture/source-acquisition-and-ops-sidecar-adaptation.md` if useful.

It should show how the source acquisition pipeline connects to the ARS-inspired integrity work:

```text
source acquisition
  -> raw snapshot
  -> preprocessing/OCR/clean markdown
  -> candidate extraction
  -> handoff schema validation
  -> integrity gate
  -> human review
  -> canonical promotion
```

### 7. Optional tests/lints

If feasible, add lightweight checks under `Scripts/automation/tests/**` for policy drift, for example:

- source acquisition allowlist exists and is explicit;
- sidecar outputs require raw snapshot and hash fields;
- transformed/OCR/crawled output is not marked canonical by default;
- browser automation candidates are deferred unless browser policy exists;
- deployment policy forbids public endpoints without security review.

Do not create a large validation framework.

## Closed decisions already accepted

- `crawl4ai` is the leading web/source-to-markdown acquisition candidate.
- `Stirling PDF` is the leading local PDF preprocessing/OCR/transformation candidate.
- Web/PDF sidecars must preserve provenance and raw/processed output separation.
- `OpenHands` is a coding-agent sandbox/evaluation pattern source, not a Codex replacement.
- `Coolify` is deployment plumbing only, not task/approval/secret authority.
- `Supabase` is derived runtime/dashboard state only, not canonical state.
- `Browser-use` and `Maxun` are deferred behind browser policy.
- `Graphify` is a repo/code graph extraction pattern source unless it proves stronger fit.
- `find-skills` is skill discovery metadata pattern only.
- `Langflow` and `Dify` are prototype canvases only, not workflow authority.

## Open decisions to resolve or document

- whether crawl4ai should receive a pilot implementation task;
- whether Stirling PDF should receive a pilot implementation task;
- where raw web/PDF snapshots should live in review-side paths;
- what metadata must be mandatory for source acquisition packets;
- whether Coolify should manage remote-box service lifecycle later;
- whether Supabase is justified over markdown/Git/SQLite for dashboard state;
- whether OpenHands patterns should modify Codex sandbox/evaluation contracts;
- whether Graphify should produce repository maps, feed Graphiti, or remain unused;
- whether Langflow/Dify should be explicitly forbidden in production workflows.

## Expected result

A reviewable evaluation and policy packet that allows Odysseus to safely pilot source acquisition and PDF preprocessing while preventing browser, deployment, workflow, runtime-state, and code-agent sidecars from becoming second authority systems.

## Stop conditions

Block or reduce scope if implementation would:

- install or deploy any service;
- expose any local, LAN, or public endpoint;
- crawl external sites;
- run browser automation;
- mutate PDFs or source files destructively;
- process canonical papers or evidence files;
- write to canonical evidence, concept, standards, research-plan, or dashboard paths;
- create a second workflow/task/state/deployment authority;
- store secrets in repo files;
- use Supabase/Coolify/Browser-use/Maxun/Langflow/Dify as authority;
- make crawled, OCR, transformed, or extracted content canonical without human review.
