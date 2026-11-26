---
artifact_type: agent-task
task_schema: agent-task/v2
task_id: 2026-11-26-claude-lane-credential-refresh-resilience
title: "Claude lane: survive an OAuth token refresh without losing its login (owner decision: credential handling)"
status: ready
priority: high
task_type: design-and-staged-implementation
created_by: operator-directed-claude-code
created_at: 2026-11-26T09:10:00+00:00
executor: claude_subscription
execution_mode: staged-design-then-opt-in-implementation
architecture: single-plus-verifier
architecture_rationale: "A credential-handling change in the Claude lane needs the owner's choice between options before any code; the design is a single reviewed document."
single_agent_baseline: "One worker writes the options document from the evidence below; the owner decides; implementation follows."
execution_host: lab
context_budget: medium
requires_remote_compute: false
requires_local_model: false
requires_zotero: false
requires_mcp: false
requires_web: false
verification_route: V3_INDEPENDENT_MODEL_ADJUDICATION
risk_level: high
approval_required: true
owner_gate_class: credential
source_traceability_required: true
repo: tyecam1/odysseus
branch: ""
allowed_paths:
  - docs/runtime-work-packages/**
  - automation/review/**
denied_paths:
  - "**/.env"
  - "**/secrets/**"
  - "**/*credential*"
  - "**/*token*"
  - "**/*password*"
inputs:
  - AGENTS.md
  - src/estate_router.py
result_path: docs/runtime-work-packages/2026-11-26-claude-lane-credential-resilience.md
---

# Claude lane: survive an OAuth token refresh

## What happened (2026-11-26, controller evidence)

`estate_router.execute_claude` runs the official Claude CLI with `CLAUDE_CONFIG_DIR=~/.cache/aoteru/claude-lane/config`, a stub whose `.credentials.json` is meant to be a SYMLINK to the operator's `~/.claude/.credentials.json`. At 08:30 UTC the CLI refreshed its OAuth token inside the lane; the CLI writes credentials atomically, which REPLACED the symlink with a regular file. That lane copy then reported "Failed to authenticate: OAuth session expired and could not be refreshed" while the operator's own login kept working. Every Claude-lane caller failed with `auth_failed` (the coordinator, the advisor checkpoint, the phone inbox's package wording, the reply parser), and provider health recorded a 15-minute `auth_failed` cooldown. The controller restored the designed state by removing the stale lane copy (the router re-creates the symlink); no credential content was read or printed. It will recur at the next refresh.

## Options (the owner chooses; this is credential handling)

A. Self-heal in the router: before each call, if the lane's `.credentials.json` is a regular file, replace it with the symlink. Risk: if the lane's copy happened to be the FRESH one (refresh tokens rotate), deleting it can invalidate the operator's own login. Needs a defined winner rule.
B. Sync-back: after each call, if the lane copy is a regular file newer than the live one, atomically copy it over the live file and restore the symlink. Moves credential bytes without parsing them; still credential handling.
C. A dedicated login for the lane (a separate `claude login` into the lane directory, so the two never share a refresh token). A new login is an owner action.
D. Run the lane against the default config directory with hooks disabled by a flag, dropping the isolation stub.

## Outcome

A short options-and-risks document with a recommendation, a test plan using a fake CLI that atomically replaces the credentials file (no real credentials), and an alert that tells the owner when the lane's login is the problem. Do NOT read, print, copy or log any credential content, and do not implement anything until the owner chooses.

## Plan (written 2026-11-26 by the controller)

**Goal in one line.** Write the options document and the fake-CLI test plan so the owner can choose; implement nothing.
**Steps:** 0. Verify the lane code and the refresh behaviour against HEAD (grep `claude-lane`, `.credentials.json`). 1. For each option, state who holds the winning token after a refresh, what a failure looks like, and the rollback. 2. Design the fake-CLI test (atomic replace of the lane credentials file) that fails today. 3. Design the owner alert for a lane-only auth failure (distinguish it from the operator's own login failing). 4. Write the document with a recommendation and the exact one-line question for the owner, run the full suite, stop.
**Done when:** the four options are compared with a stated recommendation; the fake-CLI test is specified; no credential content appears anywhere.
**Risks and stops:** this is an owner credential decision (`owner_gate_class: credential`): record it as an owner debt and stop; never work around it.
