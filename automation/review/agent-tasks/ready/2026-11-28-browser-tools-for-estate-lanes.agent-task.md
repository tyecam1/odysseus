---
artifact_type: agent-task
task_schema: agent-task/v2
task_id: 2026-11-28-browser-tools-for-estate-lanes
title: "Qualify opt-in Playwright MCP browser tools for estate lanes (web-evidence capability)"
status: ready
priority: medium
task_type: implementation
created_by: operator-directed-claude-code
created_at: 2026-11-28
updated_at: 2026-11-28
executor: codex
execution_mode: backend-integration-and-live-qualification
execution_host: lab
requires_remote_compute: true
requires_local_model: false
requires_zotero: false
requires_mcp: true
requires_web: true
verification_route: V3_INDEPENDENT_MODEL_ADJUDICATION
risk_level: medium
approval_required: false
source_traceability_required: true
repo: tyecam1/odysseus
branch: dev
related_tasks:
  - 2026-11-26-read-only-liveness-and-dispatch-admission
inputs:
  - AGENTS.md
  - docs/aoteru-model-host-routing-contract.md
  - .claude/skills/lazyUsage/SKILL.md
allowed_paths:
  - src/**
  - routes/**
  - config/**
  - tests/**
  - docs/**
  - automation/review/**
denied_paths:
  - "**/.env"
  - "**/secrets/**"
  - "**/*credential*"
  - "**/*token*"
  - "**/*password*"
result_path: automation/review/2026-11-28-browser-tools-lanes-handoff.md
---

## Capability context (verified live 2026-11-28)

Claude in Chrome is structurally unavailable to token-auth GLM lanes (claude.ai connectors
are disabled whenever ANTHROPIC_AUTH_TOKEN is set), so browser capability for GLM must come
from MCP. Both hosts already have a working opt-in path at the launcher level:

- Laptop `claude-glm -Browser`: loads `%USERPROFILE%\.aoteru\claude-glm-browser-mcp.json`
  (Playwright MCP via npx, headed Chrome, visible/auditable).
- Lab `CLAUDE_GLM_BROWSER=1 claude-glm ...`: loads
  `~/.aoteru/claude-glm-browser-mcp.json` (Playwright MCP, `--headless --isolated`,
  `--executable-path` pinned to the cached
  `~/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome`, URL params
  `token,key,secret,password` redacted at the MCP layer).

Both verified end-to-end on 2026-11-28 with nonce-probe navigations
(`https://httpbin.org/get?probe=<nonce>`; GLM returned the exact nonce on both hosts,
exit 0), which excludes hallucinated tool output. Wrapper backups:
`claude-glm-impl.ps1.bak-20261128` (laptop), `claude-glm.bak-20261128` (lab).

The gap: the estate router's lane launcher and qualification config do not know this
capability exists. Cards cannot request browser evidence through governed config, and
nothing records what a browser lane actually did.

## Plan (written 2026-11-28 by the controller; step 0 is to verify it against HEAD)

**Goal in one line.** Expose an opt-in, governed browser-evidence capability to estate
lanes so web-flagged cards get real navigation evidence, without widening any lane's
default tool surface.

**Already done / do not redo:** everything in "Capability context" above; do not
re-provision wrappers or MCP configs on either host.

**Steps:**
0. Verify every file/symbol claim here against HEAD before coding (lane launcher module,
   qualification config schema, trace/event writers).
1. Lane launcher: pass `--mcp-config` only when the dispatch's resolved capability set
   includes browser (default off). Config path comes from governed config, not prose.
2. Qualification: add a browser capability to the qualified-executor/attestation path;
   lanes still attest the effective model; browser capability is refused for unqualified
   executors.
3. Boundary rules, deterministic in code: browser lanes record the resolved tool list per
   dispatch in the trace/event; interaction-class actions (click/type/fill, uploads,
   purchases, credential entry) are `protected_handoff`, never dispatched; a card is
   eligible only when it carries `requires_web: true` or `requires_mcp: true`.
4. Tests (no network in unit tests): flag default-off; flag on passes the correct
   `--mcp-config`; eligibility gate rejects non-web-flagged cards; trace contains the
   tool list.
5. Live proof: one governed dispatch with the capability navigates a nonce URL and records
   nonce + tool list as evidence; lanes without the flag gain no tools.
6. Docs: routing-contract and SKILL.md notes; handoff file at `result_path`.

**Done-when:** lab suite green on the delivery commit; step-4 tests pass; live nonce
evidence recorded; qualification entry present in governed config; card moves to awaiting
acceptance.

**Stops:** no browser dispatch for cards that are not web-flagged; purchases, credential
entry, form submissions and file uploads are protected handoff; GLM lanes must not receive
PhD/Misumi content in browser briefs (Claude lane only); if the MCP server cannot launch
headless on the lab, record the failure and stop — do not fall back to headed/interactive.

**Owner debts:** none to start. Enabling browser capability on a new card class, or going
beyond read-leaning navigation, is a policy change through the existing approval gates.

**Ordering:** independent of the approval backlog; lower priority than verification and
acceptance work (the 2026-11-26 advisor ordering hint still applies).
