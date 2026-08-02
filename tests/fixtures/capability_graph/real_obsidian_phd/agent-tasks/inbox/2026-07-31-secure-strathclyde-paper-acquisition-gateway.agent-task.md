---
artifact_type: agent-task
task_schema: agent-task/v2
task_id: 2026-07-31-secure-strathclyde-paper-acquisition-gateway
title: Build a secure Strathclyde paper-acquisition gateway
status: inbox
priority: high
task_type: implementation
created_by: codex
created_at: 2026-07-31T12:00:00+01:00
executor: codex_subscription
execution_mode: design-then-implementation
requires_remote_compute: false
requires_local_model: false
requires_zotero: true
requires_mcp: true
requires_web: true
verification_route: V2_HUMAN_VERIFIED
risk_level: high
approval_required: true
source_traceability_required: true
architecture: single-plus-verifier
architecture_rationale: "Credential isolation, licensed-content handling and Zotero mutation require independent security verification after implementation."
single_agent_baseline: "One implementation agent builds the bounded localhost service and tests; a separate verifier audits credential, network, licence and repository boundaries."
execution_host: laptop
coordination_reason: "Independent verification is required for a local service that mediates authenticated university access and library writes."
repo: "new local paper-acquisition-gateway repository plus bounded tyecam1/obsidian-PhD integration"
branch: ""
allowed_paths:
  - automation/review/paper-acquisition-gateway/**
  - automation/review/agent-tasks/**/2026-07-31-secure-strathclyde-paper-acquisition-gateway.agent-task.md
denied_paths:
  - 00-dashboards/**
  - 01-research-plan/**
  - 02-library/00-papers/**
  - 02-library/01-annotations/**
  - 02-library/02-evidence/**
  - 03-concept/**
  - 07-standards/**
  - 11-projects/**
  - 12-log/**
  - "**/*.pdf"
  - My Library.bib
inputs:
  - automation/docs/governed-library-pdf-import.md
  - automation/docs/central-operating-contract.md
  - automation/docs/current-capabilities.md
  - automation/docs/capability_manifest.json
  - automation/docs/sensitive-input-policy.md
outputs:
  - automation/review/paper-acquisition-gateway/implementation-and-security-report.md
result_path: automation/review/paper-acquisition-gateway/implementation-and-security-report.md
notes: "Queued from Tye's 2026-07-31 secure university paper-acquisition specification. Execute as a separate infrastructure cycle; do not broaden a live manuscript evidence pass."
---

# Task: Build a secure Strathclyde paper-acquisition gateway

## Objective

Build, test, document and deploy a localhost-only service through which authorised local research agents can request one identified paper at a time, prefer lawful open-access copies, use a constrained visible-browser Strathclyde session only when necessary, create or update a Zotero item and attachment, and emit complete provenance without exposing credentials, MFA secrets, cookies, browser profiles or arbitrary browser control.

## Required boundary

- Application code belongs in a dedicated software repository, not the vault.
- Authentication occurs only in a visible native browser; Tye personally enters credentials and completes MFA on verified official domains.
- The agent-facing API accepts implemented scholarly identifiers, never arbitrary URLs, wildcard acquisition, issue traversal or bulk download.
- Bind only to `127.0.0.1`; keep the persistent browser profile outside Git and outside agent-readable API responses.
- Prefer existing Zotero attachments, Crossref metadata and lawful open-access routes before institutional retrieval.
- Fail closed on unclear rights, access denial, authentication state, unexpected redirects or ambiguous identity.
- Do not modify Better BibTeX exports manually or store credentials, sessions, licensed PDFs or secrets in Obsidian.
- Stage any proposed vault documentation change under `automation/review/paper-acquisition-gateway/`; canonical documentation requires a separate reviewed promotion decision.

## Minimum interface

- `POST /v1/papers/fetch`
- `GET /v1/jobs/{job_id}`
- `GET /v1/papers/{identifier}`
- `GET /v1/health`
- `GET /v1/auth/status`
- `POST /v1/auth/start`
- `POST /v1/auth/clear`
- matching `paper-gateway` CLI commands for fetch, status, login, auth status and session clearing.

## Implementation sequence

1. Verify current Strathclyde remote-access, electronic-resource, authentication and password rules from official sources.
2. Reconcile the design with `governed-library-pdf-import.md` and current capability truth before widening any vault-side contract.
3. Implement metadata resolution, open-access acquisition, deduplication, hashing, provenance, rate limits, allowlists, denial handling and deterministic Zotero-intake fallback.
4. Implement the visible authenticated broker with one grouped human SSO/MFA checkpoint.
5. Integrate with Zotero through a supported local mechanism or a separately approved deterministic intake path.
6. Add minimal review-side vault integration only after the software boundary is stable.
7. Run functional, security, secret-scan, localhost-binding and fresh-clone tests; independently verify the result.

## Acceptance criteria

- One lawful open-access DOI is acquired automatically.
- One ordinarily licensed article is acquired only after Tye completes visible Strathclyde SSO/MFA.
- Both requests produce a Zotero item/attachment or the documented deterministic intake fallback and complete provenance.
- Arbitrary URLs, bulk requests, unexpected domains and repeated access-denial retries are rejected.
- Logs redact cookies, tokens, authorization headers and credential-field contents.
- The service is localhost-only; session clearing works; the browser profile is outside the repository and cannot be returned by the API.
- Automated tests and an independent security review pass.
- Obsidian contains only minimal operational integration and no credentials, sessions, restricted PDFs or duplicated source-code documentation.
