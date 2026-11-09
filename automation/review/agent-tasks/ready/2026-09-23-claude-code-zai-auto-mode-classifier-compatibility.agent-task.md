---
artifact_type: agent-task
task_schema: agent-task/v2
task_id: 2026-09-23-claude-code-zai-auto-mode-classifier-compatibility
title: "Restore safe Auto Mode on Claude Code Z.AI GLM launchers after v2.1.319"
status: ready
priority: high
task_type: implementation
created_by: gpt-5.6-sol
created_at: 2026-09-23T12:18:00+01:00
updated_at: 2026-11-09
executor: codex_subscription
execution_mode: implementation
architecture: single-owner-plus-bounded-verifier
architecture_rationale: "One Codex owner should reproduce the v2.1.319 Auto Mode regression on both Windows GLM launchers, compare supported classifier and version-isolated alternatives, implement one minimal safe launcher-scoped remedy, and obtain independent real-path verification. Avoid a duplicate gateway or task owner."
single_agent_baseline: "A single high-reasoning coding agent should restore genuinely working unattended safe-tool approval on claude-glm and claude-glm-flash, without altering native claude, or demonstrate a narrow upstream blocker with a tested reversible operational fallback."
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
  - automation/review/agent-tasks/README.md
  - docs/aoteru-model-host-routing-contract.md
  - docs/subscription-model-currency-policy.md
  - config/models.yaml
  - https://code.claude.com/docs/en/auto-mode-classifier-billing
  - https://code.claude.com/docs/en/gateway
  - https://code.claude.com/docs/en/permission-modes
  - https://github.com/zai-org/feedback/issues/785
  - C:\Users\tyeca\.local\bin\claude-glm.ps1
  - C:\Users\tyeca\.local\bin\claude-glm-flash.ps1
outputs:
  - evidence-backed root-cause classification
  - smallest justified local launcher/configuration fix, if available
  - explicit upstream Z.AI compatibility blocker, if local remediation cannot enable server-side checks
  - regression evidence for both Z.AI-backed Claude Code launchers
  - a verified, reversible launcher-scoped workaround for v2.1.319 if upstream server-side review remains unsupported
  - explicit no-regression evidence for unmodified native claude
  - concise Z.AI support packet when upstream work is required
result_path: automation/review/2026-09-23-claude-code-zai-auto-mode-classifier-compatibility.md
review_report_path: automation/review/2026-09-23-claude-code-zai-auto-mode-classifier-compatibility.md
handoff_model: gpt-5.6-sol-independent-review
operator_decision_path: automation/review/2026-09-23-claude-code-zai-auto-mode-classifier-compatibility.md
supersedes: []
duplicates: []
notes: "2026-11-09 priority update: v2.1.319 now stops autonomous execution on api.z.ai. This supersedes the original non-fatal billed-classifier warning. Resolve the user-visible regression, not merely billing or warning suppression. No fake safeguard_results, no permission bypass, no effect on native claude. Coordinate with separate 2026-11-09 lab GLM worker qualification task; this card owns laptop interactive Auto Mode only."
---

# Restore safe Claude Code Auto Mode for Z.AI GLM launchers

## Current regression (operator report, 9 November 2026)

On Windows, `claude-glm` and `claude-glm-flash` are **distinct local launch commands** from normal `claude`. The operator observed Claude Code **v2.1.319** using `glm-5.3-flash[1m]` and the Z.AI Anthropic-compatible endpoint. During a legitimate Documents-directory reorganisation task, Auto Mode stopped with:

> Auto mode can't check actions in this session. Its safety check runs on the server, and your requests go through api.z.ai, which doesn't pass it through. Claude Code will now ask for your approval.

This is a **loss of autonomous safe operation**, not just an extra billing notice. The previous task packet below describes the September 2026 server-side classifier billing rollout; treat that as historical context, not current expected behaviour. Re-check the exact v2.1.319 change and current upstream docs/release notes, rather than trusting conversational claims. The prior suggested remedies have not been proven on the user's machine.

**Outcome priority:** restore working, real, classified Auto Mode for both GLM launchers without altering the ordinary Anthropic `claude` command. If that is impossible, demonstrate the most restrictive reversible functional fallback and isolate the upstream blocker.

## Regression-specific implementation contract

1. **Live entry points and environment.** On the actual Windows laptop, resolve the full command chains for `claude`, `claude-glm`, and `claude-glm-flash`, including PowerShell function/alias/shim/script, Claude binary selected, flags, parent/child environment and effective model identity. The previously recorded `C:\Users\tyeca\.local\bin\claude-glm.ps1` and `claude-glm-flash.ps1` paths are leads, not assumptions. Read current `AGENTS.md`, task ownership and preflight contracts. Never expose secrets. Confirm whether an existing change, task or branch already fixed the regression before editing.
2. **Reproduce deterministically.** On both launchers, record the exact Claude Code version, `/status` permission mode, `Auto mode server` state, harmless classified shell operation, behaviour on an operation requiring confirmation and debug classifier events. Compare with the unmodified native `claude` entry. Redact local paths/private filenames where appropriate. Never run a destructive operation to prove a denial.
3. **Test supported fixes, not presumed fixes.** In an isolated child-process environment, first test current Claude Code with `CLAUDE_CODE_AUTO_MODE_SERVER=0` and inspect whether a **genuine separate classifier request and valid decision** occur through the GLM endpoint. Only if necessary evaluate `CLAUDE_CODE_AUTO_MODE_MODEL`, checking the current supported model identifier and response format rather than guessing aliases. If classification fails, distinguish request rejection, model selection, thinking payload incompatibility, classifier output parse failure and Claude Code feature/config gating.
4. **Test version-isolated rollback.** If the current version cannot classify safely, test a locally isolated known pre-regression Claude Code version (candidate: `2.1.318`) through each existing GLM launcher **without downgrading the globally used `claude`**. Compare actual results and safe denial behaviour. Choose a maintained, documented version-isolation mechanism only if it works. Include how to remove the pin and resume current releases. A previous-version assumption is not acceptance evidence.
5. **Adjudicate alternatives by evidence.** Assess official current support for Z.AI server-side `safeguards`/`safeguard_results` transparently, but do not pretend a local shim can manufacture valid safety review. Compare local-classifier current version, isolated version pin, and tightly scoped `acceptEdits`/allowlisting as a **different, non-Auto permission mode**. Never use `--dangerously-skip-permissions`, blanket `Bash(*)`, fabricated classifications or permissive fallback while describing it as Auto Mode.
6. **Implement the smallest reversible change.** Mutate only the two proven GLM launcher entry points or their established shared launcher authority. Do not globally set Claude environment variables, change native `claude`, replace model route/authentication, add another proxy or copy credentials into Git. If an upstream patch resolves the issue, remove obsolete workarounds. Preserve original launchers and capture exact rollback steps.
7. **Real-path acceptance.** Verify independent standard GLM and Flash sessions can autonomously execute an ordinary safe tool operation, correctly ask/deny when approval is genuinely required, process a benign file edit, preserve intended model identities and authentication, and restart successfully. Verify native `claude` remains unchanged. Record before/after `/status`, debug events, tool outcomes, chosen classifier version/model, additional classifier billing/latency if measurable, and source-backed limitation. An unexplained disappearance of a warning is not sufficient.
8. **Cross-task boundary.** The separate `2026-11-09-qualify-glm-and-glm-flash-on-lab-odysseus` card owns Linux lab and backend `/api/estate/run` model qualification. Do not widen this laptop Claude Code issue to that integration; share findings as dependencies only.

**Stop rule:** Close only on verified safe autonomy for both GLM launchers, or a reproducible upstream blocker plus a tested non-deceptive alternative, exact next trigger, and rollback. Do not declare a prompt-heavy manual approval workflow to be a working Auto Mode fix.

## Historical trigger (September 2026)

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

The task succeeds when the November regression-specific acceptance above is met. Server-side no-charge review is desirable but **not required**: a verified safe separate classifier is an acceptable solution. If the upstream route still cannot support Auto Mode, preserve a clear, tested least-permissive fallback and a precise support packet; do not mark Auto Mode restored.

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

Within `tyecam1/odysseus`, write only the bounded review-side evidence/results declared by this task; historical `obsidian-PhD` ownership references are not write authority. Do not commit machine-specific secrets or duplicate launcher copies into the vault.

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

- the November 2026 v2.1.319 regression is reproduced and assessed separately for both local launcher commands;
- actual classified safe tool execution and correct guarded behaviour are verified, or Auto Mode remains explicitly unresolved with a tested honest fallback;
- current-version local classifier and isolated previous-version approaches are compared using real results, not just suggested commands;
- native `claude` settings, auth and executable remain unchanged;
- a real-path rollback works and stale pins or unnecessary global env changes are absent;

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
