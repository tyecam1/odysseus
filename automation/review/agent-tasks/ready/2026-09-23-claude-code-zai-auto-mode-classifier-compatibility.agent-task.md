---
artifact_type: agent-task
task_schema: agent-task/v2
task_id: 2026-09-23-claude-code-zai-auto-mode-classifier-compatibility
title: "Diagnose and resolve Claude Code auto-mode classifier compatibility on the Z.AI route"
status: ready
priority: medium
task_type: implementation
created_by: gpt-5.6-sol
created_at: 2026-09-23T12:18:00+01:00
updated_at: 2026-09-23T12:18:00+01:00
executor: codex_subscription
execution_mode: implementation
architecture: single-owner-plus-bounded-verifier
architecture_rationale: "This is one transport/configuration fault domain. One Codex owner should trace the live Claude Code -> launcher -> endpoint path, make only the smallest justified change, and independently verify that model routing and ordinary tool use still work. Parallel agents would mostly duplicate network/config inspection."
single_agent_baseline: "A single high-reasoning coding agent can inspect the local launchers, current Claude Code behaviour, upstream compatibility contract, and repository routing authority, then either implement a bounded local fix or close with an evidence-backed upstream blocker."
execution_host: laptop
context_budget: medium
coordination_reason: "Keep diagnosis and mutation in one owner so request-path evidence, launcher edits, and regression checks remain causally linked."
requires_remote_compute: false
requires_local_model: false
requires_zotero: false
requires_mcp: false
requires_web: true
verification_route: V2_HUMAN_VERIFIED
risk_level: medium
approval_required: false
source_traceability_required: true
repo: tyecam1/odysseus
migrated_from_repo: tyecam1/obsidian-PhD
migration_note: "Ownership migrated to Odysseus. Treat references to obsidian-PhD automation paths as historical inputs until capability-path convergence is complete."
branch: ""
allowed_paths:
  - automation/review/**
denied_paths:
  - 00-dashboards/**
  - 01-research-plan/**
  - 02-library/**
  - 03-concept/**
  - 04-supportDesign/**
  - 06-datasets/**
  - 07-standards/**
  - 09-resources/**
  - 10-inbox/**
  - 11-projects/**
  - 12-log/**
  - .agents/**
  - .claude/**
  - Scripts/**
  - automation/config/**
  - automation/docs/**
inputs:
  - AGENTS.md
  - automation/AGENTS.md
  - automation/docs/central-operating-contract.md
  - automation/docs/path-authority.md
  - automation/config/model_execution_policy.yaml
  - automation/config/agent_routing.yaml
  - https://code.claude.com/docs/en/auto-mode-classifier-billing
  - https://code.claude.com/docs/en/gateway
  - C:\Users\tyeca\.local\bin\claude-glm.ps1
  - C:\Users\tyeca\.local\bin\claude-glm-flash.ps1
outputs:
  - evidence-backed root-cause classification
  - smallest justified local launcher/configuration fix, if available
  - explicit upstream Z.AI compatibility blocker, if local remediation cannot enable server-side checks
  - regression evidence for both Z.AI-backed Claude Code launchers
  - concise Z.AI support packet when upstream work is required
result_path: automation/review/2026-09-23-claude-code-zai-auto-mode-classifier-compatibility.md
review_report_path: automation/review/2026-09-23-claude-code-zai-auto-mode-classifier-compatibility.md
handoff_model: gpt-5.6-sol-independent-review
operator_decision_path: automation/review/2026-09-23-claude-code-zai-auto-mode-classifier-compatibility.md
supersedes: []
duplicates: []
notes: "The observed warning names api.z.ai. Do not assume Odysseus is in this runtime request path. Do not emulate or fabricate safeguard_results merely to suppress the warning. If Z.AI cannot support Claude Code's server-side auto-mode checks, preserve the safe legacy classifier path and document the upstream requirement."
---

# Diagnose Claude Code auto-mode classifier compatibility on the Z.AI route

## Trigger

Claude Code reports:

> We're changing auto mode to no longer charge for classifier requests in Claude Code.
>
> However, this session isn't eligible because your requests go through api.z.ai, which isn't compatible with this update.
>
> Nothing breaks: auto mode keeps working, and its classifier requests are billed as before.

Official current guidance:

- https://code.claude.com/docs/en/auto-mode-classifier-billing
- Claude Code v2.1.278 or later can ask the server to perform auto-mode safety checks as part of the session's own model requests.
- Gateway compatibility requires pass-through behaviour for request headers/body fields and response/streaming fields, including unknown fields.
- The guidance specifically names the `safeguards` request field, `safeguard_results` response field, and preservation of tool-use IDs.
- If a known gateway cannot provide server-side checks, Claude documents `CLAUDE_CODE_AUTO_MODE_SERVER=0` as a temporary way to deliberately retain Claude Code's own billed classifier requests and suppress repeated compatibility attempts/notices.

Treat the upstream documentation as authoritative and re-read it at execution time because this feature is explicitly evolving.

## Objective

Determine the actual reason the Z.AI-backed Claude Code sessions are ineligible for no-charge server-side auto-mode classification, then implement the smallest safe remediation that is genuinely under local control.

The task succeeds in either of two ways:

1. **Local fix:** server-side checks become genuinely functional through the existing Z.AI route without changing intended model routing; or
2. **Bounded upstream result:** evidence shows Z.AI does not implement/pass the required protocol, the local launchers are made explicit about the supported legacy behaviour if useful, and a precise upstream support request is prepared.

Suppressing the warning without understanding the request path is not success.

## Runtime boundary

Start from live state, not assumptions.

Expected local launchers to inspect:

- `C:\Users\tyeca\.local\bin\claude-glm.ps1`
- `C:\Users\tyeca\.local\bin\claude-glm-flash.ps1`

The recent working configuration routes these launchers directly to:

`https://api.z.ai/api/anthropic`

Verify this rather than trusting the task packet.

Do not assume Odysseus, Aoteru, LiteLLM, a local proxy, or another gateway is present merely because those systems exist elsewhere in the estate.

## Phase 0. Authority and duplicate-owner scan

Before editing anything:

1. read the repository operating contract and current model-routing authority;
2. search active/recent agent tasks for an existing owner of Claude Code launcher or Z.AI compatibility work;
3. inspect the live launchers and effective environment;
4. identify every hop between Claude Code and the final API endpoint.

If another active work item already owns this exact fault, route into that owner rather than creating a parallel implementation.

## Phase 1. Reproduce and capture current state

Record, without exposing secrets:

- `claude --version`;
- launcher invoked;
- effective API/base URL host;
- intended model mapping;
- relevant non-secret Claude Code environment variables;
- whether auto mode is active;
- `/status`, especially the `Auto mode server` row;
- exact warning text;
- whether the warning occurs on both `claude-glm` and `claude-glm-flash`;
- whether direct ordinary model/tool calls still succeed.

Never print or commit API keys, tokens, authorization headers, cookies, or other secrets.

## Phase 2. Trace the compatibility failure

Use Claude Code debug/network evidence where safely available.

Determine separately whether:

1. Claude Code emits the server-side check request on this route;
2. the request contains/preserves the relevant feature/beta headers;
3. the `safeguards` request field is emitted;
4. anything local strips, rewrites, validates away, or reconstructs unknown body fields;
5. Z.AI accepts or drops the field;
6. Z.AI returns a compatible `safeguard_results` field/event;
7. response streaming preserves unknown keys;
8. tool-use IDs are returned unchanged;
9. Claude Code consequently keeps `Auto mode server: Enabled` or falls back to `Disabled`.

Do not infer protocol behaviour solely from the warning. Capture enough evidence to distinguish where the field/result is lost.

## Root-cause classification

End diagnosis with exactly one primary class:

### A. Local launcher/configuration fault

Examples:

- environment disables/breaks the new mechanism;
- local wrapper points at an unintended intermediary;
- local configuration drops required headers/fields;
- stale Claude Code version.

Implement the smallest local repair.

### B. Locally controlled proxy/gateway fault

A proxy in the actual request path fails transparent pass-through.

Repair only that hop and add a focused regression check for unknown request/response fields where practical.

### C. Z.AI upstream incompatibility

The local request reaches `api.z.ai` intact but Z.AI does not preserve/implement the required safeguards protocol or server-side check result.

Do not fake compatibility locally.

### D. Upstream/credential rollout state not yet supporting the feature

If evidence does not support blaming request rewriting and the relevant platform/account simply lacks server-side checks, record that precisely and avoid speculative local changes.

## Implementation rules

### If A or B

Implement the smallest affected-scope fix.

Requirements:

- preserve existing `claude-glm` model identity;
- preserve existing `claude-glm-flash` model identity;
- preserve authentication precedence;
- preserve direct normal `claude` behaviour;
- do not route ordinary Claude sessions through Z.AI;
- do not widen unrelated model-routing policy;
- do not introduce a permanent new gateway merely for this feature.

### If C or D

Do not:

- fabricate `safeguard_results`;
- rewrite failed responses to look compatible;
- bypass safety checks;
- disable the classifier while presenting the session as server-checked;
- silently redirect to another provider.

Evaluate the documented temporary setting:

`CLAUDE_CODE_AUTO_MODE_SERVER=0`

Only add it to the **Z.AI-specific launchers** if all of the following are true:

1. server-side checks are demonstrably unavailable on that route;
2. the setting preserves the existing safe local classifier behaviour;
3. it avoids repeated pointless negotiation/warnings;
4. current Claude documentation still recommends it for this exact case;
5. the change is clearly documented as temporary and does not claim to make classifier requests free.

If those conditions are not met, leave the launchers unchanged and record the blocker.

## Upstream support packet

If the blocker is Z.AI, prepare a concise support packet containing:

- Claude Code version;
- endpoint family: Anthropic-compatible Z.AI route;
- symptom: server-side auto-mode checks do not reach/return to session;
- expected transparent pass-through requirements;
- preservation of unknown request headers/body fields;
- `safeguards` request field;
- `safeguard_results` response and streaming field;
- unchanged tool-use IDs;
- redacted minimal reproduction;
- confirmation that ordinary Claude-compatible inference still works;
- no credentials or private research content.

Do not send the support request without a separate operator instruction if sending requires an external account/action.

## Repository boundary

The actual launcher files are local user-managed runtime files, not vault research content.

This task may modify the two named local launcher files if justified.

Within `tyecam1/obsidian-PhD`, write only review-side evidence/results declared by this task. Do not commit machine-specific secrets or duplicate launcher copies into the vault.

If a durable estate-level launcher/configuration authority is discovered in another repository, do not create a shadow copy here. Record the correct owner and route a bounded cross-repository follow-up if needed.

## Verification

After any change, test both Z.AI launchers independently.

Minimum checks:

1. `claude --version` is recorded and compatible with the current feature contract.
2. `claude-glm` launches and resolves to its intended model.
3. `claude-glm-flash` launches and resolves to its intended model.
4. Authentication still works without exposing credentials.
5. Ordinary text/model requests work.
6. A harmless tool/classifier-eligible operation works.
7. `/status` is checked before and after the eligible action.
8. Warning behaviour is recorded.
9. If claiming server-side compatibility, `Auto mode server` remains genuinely enabled and protocol evidence supports the claim.
10. If setting `CLAUDE_CODE_AUTO_MODE_SERVER=0`, verify the session deliberately uses Claude Code's own classifier path and do **not** report this as no-charge server-side classification.
11. Existing relevant launcher/model-policy tests remain green where present.

## Result report

Write:

`automation/review/2026-09-23-claude-code-zai-auto-mode-classifier-compatibility.md`

It must contain:

1. live request-path diagram;
2. Claude Code version and launcher state;
3. reproduction evidence;
4. root-cause class A/B/C/D;
5. exact fields/headers/events observed or proven missing;
6. local changes made, if any;
7. before/after behaviour for both launchers;
8. whether free server-side classifier requests are actually achievable through Z.AI now;
9. residual risk;
10. upstream action required;
11. rollback instructions;
12. independent verification result.

## Acceptance criteria

Complete only when:

- the actual request path is established rather than assumed;
- the issue is classified as local, controlled-gateway, Z.AI upstream, or rollout/credential support;
- no secret is logged or committed;
- no fake `safeguard_results` or safety bypass is introduced;
- both Z.AI launchers still resolve to their intended models;
- ordinary Claude Code operation remains functional;
- any `CLAUDE_CODE_AUTO_MODE_SERVER=0` use is Z.AI-scoped, evidence-backed, temporary, and accurately described;
- any claim that server-side checks work is supported by `/status` plus protocol evidence, not warning disappearance alone;
- the repository contains only the bounded review-side result, not duplicate machine configuration;
- unresolved Z.AI work is reduced to one precise upstream support request rather than another broad gateway project.
