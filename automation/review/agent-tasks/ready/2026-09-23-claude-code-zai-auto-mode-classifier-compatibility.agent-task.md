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
execution_mode: evidence-first-bounded-implementation
architecture: single-owner-plus-bounded-verifier
architecture_rationale: "One coding owner diagnoses both Windows launcher paths, tests only supported remedies, and implements a reversible change; independent verification checks safety, model isolation and rollback. No duplicate gateway."
single_agent_baseline: "Restore genuinely classified, autonomous tool execution for both Z.AI launchers while preserving native claude; otherwise substantiate the upstream limitation and tested least-permissive fallback."
execution_host: laptop
context_budget: medium
coordination_reason: "Both affected launchers share the local Claude Code runtime and endpoint, so diagnosis, changes and proof should have a single accountable owner."
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
branch: dev
related_tasks:
  - 2026-11-09-qualify-glm-and-glm-flash-on-lab-odysseus
allowed_paths:
  - automation/review/**
denied_paths:
  - "**/.env"
  - "**/secrets/**"
  - "**/*credential*"
  - "**/*password*"
inputs:
  - AGENTS.md
  - automation/review/agent-tasks/README.md
  - docs/aoteru-model-host-routing-contract.md
  - docs/subscription-model-currency-policy.md
  - https://code.claude.com/docs/en/permission-modes
  - https://code.claude.com/docs/en/auto-mode-classifier-billing
  - https://github.com/zai-org/feedback/issues/785
  - 'C:\Users\tyeca\.local\bin\claude-glm.ps1 (verify live path)'
  - 'C:\Users\tyeca\.local\bin\claude-glm-flash.ps1 (verify live path)'
outputs:
  - verified root cause of v2.1.319 Auto Mode failure
  - reversible launcher-scoped fix or exact upstream blocker plus tested operational fallback
  - real-path regression tests for standard GLM, GLM Flash and native claude
  - redacted evidence, tradeoffs and rollback instructions
result_path: automation/review/2026-09-23-claude-code-zai-auto-mode-classifier-compatibility.md
review_report_path: automation/review/2026-09-23-claude-code-zai-auto-mode-classifier-compatibility.md
handoff_model: independent-qualified-review
operator_decision_path: automation/review/2026-09-23-claude-code-zai-auto-mode-classifier-compatibility.md
supersedes: []
duplicates: []
notes: "Existing September task updated 2026-11-09 for newly blocking v2.1.319 regression. Historical task details remain in Git history. Laptop interactive Auto Mode only; lab Odysseus GLM worker qualification has a separate owner."
---

# Restore Claude Code Auto Mode for Z.AI launchers

## Observed failure

On 9 November 2026, Claude Code **v2.1.319** running through the separate Windows command `claude-glm-flash` (`glm-5.3-flash[1m]`, `api.z.ai`) stopped autonomous shell operations and announced that server-side safety checks were unavailable through the provider, so it would require manual approval. The work was a reversible Documents-folder reorganisation with a proposed dry run. The sibling `claude-glm` launcher must be tested independently; do not assume it fails identically.

This is **loss of functioning safe Auto Mode**, not the earlier September warning about chargeable separate classifiers. The original September task already owns the fault. Do not create another queue item.

## Objective and boundaries

Restore **real, safety-classified autonomous execution** on `claude-glm` and `claude-glm-flash`, preserving each model's intended identity, authentication and the unaffected native `claude` launcher. Prefer the smallest reliable, reversible, provider-specific solution. Cost-free server-side classification is optional; correct safety behaviour is mandatory.

Read current `AGENTS.md`, live `dev`, existing task/result evidence and authorised preflight first. This is a Windows laptop launcher problem, **not** lab-host GLM qualification or a requirement to introduce Odysseus into the network request path. Do not assume wrappers, endpoints, binary versions or configuration from this packet are still correct. Never expose secrets.

## Execution

1. **Reproduce.** Resolve the full command chains and isolated environment variables for `claude`, `claude-glm`, `claude-glm-flash` using `Get-Command -All`, script inspection and effective process settings. Capture version, model and endpoint host, `/status` Auto Mode state, safe tool execution and redacted classifier debug signals for both GLM commands. Confirm the native `claude` baseline.
2. **Verify upstream contract.** Read current Claude Code release notes and Auto Mode/permission documentation, plus current Z.AI issues. Determine whether v2.1.319 intentionally disabled an automatic fallback, whether local classifier requests remain supported and what the server-side `safeguards`/`safeguard_results` mechanism needs. Distinguish confirmed upstream behaviour from hypothesis.
3. **Test current-version local classification.** In an ephemeral child-process environment, try `CLAUDE_CODE_AUTO_MODE_SERVER=0` for each launcher. Inspect real classifier requests, returned decisions, tool actions and error logs. If necessary, test `CLAUDE_CODE_AUTO_MODE_MODEL` using verified current model IDs and supported response formats, not guessed `[1m]` aliases. Classify failure as launcher/env, server-gateway, model thinking/request format, classifier parsing, or platform gating.
4. **Test isolated pre-regression version if needed.** Trial `@anthropic-ai/claude-code@2.1.318` or the last demonstrably working release **only for the GLM entry points**, leaving the normal `claude` installation untouched. Verify classifier decisions and safe behaviour, not just version startup. If successful, implement a documented isolated version pin with an update/removal path and no global downgrade.
5. **Compare alternatives and implement.** Select the least-complex verified option: current-version local classifier, isolated pinned Claude Code version, or (only if Auto Mode cannot be restored) tightly scoped `acceptEdits` plus necessary explicit permissions. The last is **not Auto Mode** and must never be claimed as such. Do not fabricate `safeguard_results`, disable all permissions, use `--dangerously-skip-permissions`, globally allow `Bash(*)`, silently change providers or build an unnecessary proxy.
6. **Regress and roll back.** In independent standard-GLM and Flash sessions verify a harmless classified shell command runs without routine prompts, a benign file edit succeeds, and a potentially risky operation is prompted/denied before execution. Do not execute destructive commands for testing. Verify correct models, auth, restart and no change to native `claude`. Quantify extra classifier calls/latency if measurable. Run applicable tests and demonstrate actual rollback.
7. **Report.** Write the minimum evidence-backed result at `result_path`: versions, command chain and request-path classification, comparison matrix, log excerpts without secrets, exact changes, acceptance results for all three launchers, limitations, maintenance cost, rollback and upstream support packet if needed. Do not submit an external support request without applicable authorization.

## Acceptance and stop

- Both independent Z.AI launchers genuinely recover safe, classified autonomous tool use; `/status`, debug evidence and tool behaviour agree. Native `claude` remains unchanged.
- If Z.AI/Claude Code fundamentally prevents safe Auto Mode, record a **reproducible exact blocker**, a tested least-permissive usable alternative, the explicit fact that Auto Mode remains unavailable, and the event that should trigger re-testing. Do not mark this as fully restored.
- No safety bypass, fabricated approval, credential exposure, duplicate router, uncontrolled global environment change or permanently pinned stale version without a documented update path.
- A verified result or evidence-backed upstream blocker and handoff is required before changing task status. Independent review must validate the outcome, not merely the disappearance of a warning.
