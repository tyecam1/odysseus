---
artifact_type: agent-task
task_schema: agent-task/v2
task_id: 2026-10-29-odysseus-governed-browser-for-misumi
title: "Enable governed interactive internet browsing for Misumi"
status: inbox
priority: normal
task_type: tool-integration
created_by: chatgpt
created_at: 2026-10-29T14:04:00+00:00
executor: policy-selected
execution_mode: bounded-implementation
architecture: single-plus-verifier
architecture_rationale: "Reuse existing web-search and browser/tool routing; a single implementation owner plus independent security review prevents duplicate transports and unsafe web execution."
risk_level: high
approval_required: true
requires_web: true
requires_mcp: false
source_traceability_required: true
repo: tyecam1/odysseus
branch: dev
domain_consumer: tyecam1/misumi
allowed_paths:
  - automation/review/**
  - config/**
  - core/**
  - docs/**
  - integrations/**
  - routes/**
  - services/**
  - src/**
  - tests/**
  - evals/**
denied_paths:
  - "**/.env"
  - "**/secrets/**"
  - "**/*credential*"
  - "**/*password*"
outputs:
  - existing-browser-capability audit and selected reuse path
  - policy-gated browser navigation and read-only page inspection exposed to Misumi
  - source-cited response transport and error-state reporting
  - isolated browser sessions and security tests
  - one verified normal Misumi conversation demonstration
---

# Governed browser internet access for Misumi

## Objective

Let Misumi use an actual internet-connected browser to search, open, navigate, inspect and cite public web pages in response to user requests. This is **interactive browser access**, distinct from search-result snippets. Misumi should be able to follow links, scroll/read dynamic pages where necessary, and return grounded findings without giving the language model unconstrained control of a household PC or logged-in account.

## Ownership and overlap

Odysseus owns shared browser tool/runtime execution, capability routing, sandbox/network controls, approvals, logging and verifiable outcomes. Misumi owns the household-specific choice to invoke the capability and its interface presentation. No private household canon or credentials should be mirrored into this public repository.

Before coding, inspect live `dev`, `AGENTS.md`, the existing `comprehensive_web_search` route, browser/skill/MCP policy, available browser transports and:
- `automation/review/agent-tasks/ready/2026-10-01-claude-in-chrome-scholar-finding-retrieval.agent-task.md`
- `automation/review/agent-tasks/ready/2026-10-19-claude-brave-chatgpt-query-adapter.agent-task.md`
- `automation/review/agent-tasks/blocked/2026-09-02-claude-chatgpt-project-browser-bridge.agent-task.md` (superseded historical scope only)

Reuse a qualified transport and existing execution/permission surface if possible. Do not reimplement those research-specific browser bridges or mix their quota/authentication state with general Misumi browsing. First prove whether a real browser is needed rather than existing public search+page retrieval.

## Requested vertical slice

1. Define `web.open / web.navigate / web.inspect / web.search` semantics, or adapt the current equivalent, for **public, unauthenticated, read-only browsing**. Provide visible page URL, title, retrieved timestamp, content/extract and failure state. The model must not hallucinate a successful visit.
2. Support following links and reading rendered content on JavaScript-heavy sites when an ordinary fetch is inadequate. Take a screenshot only when it materially helps interpretation; do not screenshot unrelated private tabs or personal windows.
3. Surface useful URLs/citations and a short summary back through the normal `/misumi/respond` path and existing chat/kiosk frontend. Users need not know the browser implementation or request a specialist persona.
4. Reuse existing Odysseus routing, tool allowlists, budget/timeout mechanisms, preflight and write-lease rules. No new task queue, browser authority, persistent memory store, model gateway or second web-search source of truth.
5. Apply hard bounds on navigation hops, pages, runtime, data transferred and concurrent sessions. Separate user workspaces, run the browser in a sandboxed low-privilege profile, and never silently open public inbound ports or provide remote desktop control.
6. Block SSRF and unsafe network egress including LAN/private, loopback, link-local, cloud metadata and non-HTTP(S) targets. Validate redirects and DNS outcomes, not just the initial URL. Prevent untrusted web content from issuing tool instructions or modifying system policies.
7. No form submission, purchases, posting, downloads, file uploads, account login, cookies/token extraction or persistent authenticated sessions in the first release. Treat any later authenticated/side-effecting workflow as a separate explicit-consent gate with per-action review and domain restrictions.
8. Respect site terms, access limitations and robots/publisher restrictions as applicable. On CAPTCHA, paywall, login requirement, rate limit or blocked access, report the limitation. Never bypass protections, scrape private endpoints or imply the source was reviewed.
9. Keep network and source logs minimal and redact sensitive page content. Retrieved text remains untrusted input, never autonomous instructions. Avoid background crawling unless separately authorised.

## Acceptance and verification

- [ ] One user request through Misumi searches the web, opens a public page, follows a relevant link and returns a sourced answer with real URLs and retrieval timestamps.
- [ ] At least one representative rendered/JS page is read where needed, with exact content or an honest failure state.
- [ ] Missing browser, browser crash, blocked site, timeout, challenge and stale source conditions produce truthful, recoverable errors rather than fabricated browsing.
- [ ] Tests demonstrate blocking of private IP and metadata targets (including redirects/DNS rebinding), unapproved POST, file access, credential stores, prompt-injected page text and uncontrolled navigation.
- [ ] Browser and ordinary web-search routes remain distinct, bounded and observable; no unreviewed external side effects.
- [ ] Independent security review plus an operator-observed, non-sensitive real-path test precede an `operational` status; record route, model/host, limits, tests and exact blockers.

## Work selection

This is a new, nonessential inbox request under the `AGENTS.md` shipping-first backlog policy. Triage for duplicates and then defer until existing accepted delivery work is shipped, unless the operator explicitly reprioritises. Execute on the cheapest qualified lane after `aoteru preflight`; use an independent verifier for browser security and prompt-injection boundaries.

## Stop rule

Stop after one safe end-to-end **public read-only** browser path is demonstrated inside Misumi with citations and tested isolation. Do not grow this into unrestricted computer use, autonomous web transactions or a separate browser agent platform.
