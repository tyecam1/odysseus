---
artifact_type: agent-task
task_schema: agent-task/v2
task_id: 2026-10-29-am-query-friction-and-claude-code-access
title: "Ship low-friction AM access and verify Aoteru API integration with Claude Code"
status: inbox
priority: high
task_type: implementation
created_by: chatgpt
created_at: 2026-10-29T14:04:00+00:00
updated_at: 2026-10-29T14:04:00+00:00
executor: claude_subscription
execution_mode: staged-implementation
architecture: single-plus-verifier
architecture_rationale: "One owner should finish the existing AM CLI PR and test the Claude Code integration against the same backend and permissions. Split only independent protocol review/evaluation into a bounded verifier; do not add a second routing authority, a duplicate agent queue or a premature gateway."
single_agent_baseline: "One Claude Code implementation owner checks live dev and PR #205, resolves the remaining CLI and authentication issues, verifies access on the operator laptop and backend, then establishes the smallest scoped Claude Code tool integration and records evidence."
execution_host: laptop
context_budget: medium
coordination_reason: "Requires observing Windows CLI ergonomics, live scoped Odysseus auth and Claude Code model/tool boundary while preserving Misumi persona-policy ownership."
requires_remote_compute: false
requires_local_model: false
requires_zotero: false
requires_mcp: true
requires_web: true
verification_route: V2_HUMAN_VERIFIED
risk_level: medium
approval_required: true
source_traceability_required: true
repo: tyecam1/odysseus
branch: ""
allowed_paths:
  - companion/laptop_client/**
  - integrations/claude/**
  - docs/**
  - tests/**
  - automation/review/**
  - scripts/**
  - routes/**
denied_paths:
  - "**/.env"
  - "**/secrets/**"
  - "**/*credential*"
  - "**/*password*"
  - "core/database.py"
inputs:
  - AGENTS.md
  - docs/aoteru-model-host-routing-contract.md
  - companion/laptop_client/aoteru.py
  - companion/laptop_client/pyproject.toml
  - companion/laptop_client/README.md
  - tests/test_laptop_client.py
  - integrations/claude/skills/odysseus/SKILL.md
  - docs/misumi-api.md
  - "Odysseus PR #205: chatgpt/am-unified-entry-20261029 (candidate, NOT deployed/merged at creation)"
  - "PR #205: docs/am-claude-code-integration-assessment-2026-10-29.md"
  - "Misumi docs/core/aoteru-routing-contract-v0.2.md (ratified persona-routing authority)"
  - https://code.claude.com/docs/en/mcp
  - https://code.claude.com/docs/en/llm-gateway
outputs:
  - verified AM command reachable from normal laptop shells without local Odysseus checkout
  - explicit, discoverable separation between Aoteru identity, Misumi domain/personas and Odysseus runtime
  - conversational query and governed task-execution commands with separate scope and authorization semantics
  - Claude Code calling the existing Aoteru/Misumi API via its least-friction permitted tool/skill or MCP path
  - evidence-backed feasibility verdict on using the Aoteru API as Claude Code model backend
  - minimal automated regression tests, real-host smoke evidence and rollback instructions
result_path: docs/am-access-integration-verification.md
review_report_path: automation/review/am-access-integration-verification.md
handoff_model: independent-code-review
operator_decision_path: ""
supersedes: []
duplicates: []
notes: "Operator request 2026-10-29. PR #205 already implements an initial CLI candidate. Shipping-first AGENTS.md priority (2026-10-17) remains binding: finish the PR before optional UX redesign, and do not displace accepted baseline work merely because this task is high priority. Do not falsely claim that a GitHub PR is an installed command."
---

# Low-friction Aoteru access through AM and Claude Code

## Objective

Make querying Aoteru as effortless as a normal terminal command, while stopping the persistent confusion between the personal assistant **Aoteru**, household/personal policy and specialist personas **Misumi**, and domain-neutral backend **Odysseus**. Investigate and, where supported, deliver access to the owner's Aoteru API *inside Claude Code*.

Aoteru is the human-facing assistant identity; Misumi remains canonical authority for household knowledge/persona policy; Odysseus owns API, routing, execution, auth and leases. `am` is a client command, not a new persona, backend, router or knowledgebase.

Normal operator behaviour:

```powershell
am "What's on the shopping list?"
am chat "Suggest dinner" --persona sanji
am chat "Continue" --session am-cli --json
am preflight "Review the open work" --repo odysseus
am ask "Review the open work" --repo odysseus
```

**Critical distinction:** `am "question"` invokes `POST /misumi/respond` and persona-aware conversation; `am ask` invokes `POST /api/estate/run` and governed task execution. The latter does not implicitly follow from merely requesting a conversational answer.

## Stage 0. Re-enter from live source

1. Inspect current `tyecam1/odysseus@dev`, current PR #205 and its CI, all matching task cards and deployed laptop/backend versions; previous chat and this card are only leads.
2. Run the required `am`/`aoteru preflight` (or `POST /api/estate/preflight`) and obey live worker, repo, model, lease and permission routing. Do not acquire a write lease implicitly.
3. Reconcile whether PR #205 has merged, changed, failed CI, or been superseded. Reuse or repair its existing changes rather than implementing a competing CLI.
4. Preserve the currently ratified `misumi` routing contract and separate `tyecam1/misumi` policy ownership. Any policy change must be proposed in the owning repository with the appropriate ratification; this task does not grant it.

## Stage 1. Finish and verify the AM command

1. Deliver `am` as the short installable command, retaining `aoteru` as a compatibility entry and `~/.aoteru/client.json` as the existing config location. Preserve the stdlib-only client where possible.
2. Prove installation/update, PATH resolution, quoting, Unicode, multiline input and predictable errors on the owner's actual Windows PowerShell environment. Test `pipx` and a checkout-free fallback; do not treat Linux CI as Windows acceptance.
3. Verify an ordinary question uses the ratified automatic lead-persona router, optional explicit persona selection, owner-scoped session continuity, sources/provenance on `--json`, and no unintended estate execution.
4. Verify `am ask`, `preflight`, `auto`, `lab`, `home`, lease/status and `sync` retain their previous meanings. Test missing backend, denied token, unknown persona, unavailable host, timeout and nonzero execution result.
5. Remove concrete remaining invocation friction discovered in measured smoke tests, but avoid speculative renaming of scripts, config locations, legacy protocol IDs or host services. Ensure `am --help` succinctly distinguishes chat from work execution.
6. Keep credentials private and owner-scoped. `misumi:execute` is required for default persisting chat; `estate:execute` for estate execution, with `estate:read` for read/preflight as required. Never echo bearer tokens or bypass a denial.

## Stage 2. Native access inside Claude Code

There are **two different integration questions**. Test them independently, not as interchangeable marketing claims.

**A. Aoteru as a Claude Code tool (preferred).**

- Inspect the existing `integrations/claude/skills/odysseus` and `am sync` installed skill. Prefer the existing scoped tool mechanism; add a minimal MCP wrapper only if it demonstrably reduces friction or improves discoverability.
- Prove from a normal Claude Code session that an explicit operator query can call `am chat` / scoped `/misumi/respond`, receive source/provenance, and return to Claude without misrepresenting the assistant identity or widening permissions.
- Keep automatic domain selection and persona routing server-side. Do not duplicate persona manifests, memory, task queue or routing heuristics inside the Claude skill.
- Distinguish a successful CLI subprocess/tool response from Claude Code itself being powered by the Aoteru model.

**B. Aoteru API as Claude Code's model provider (investigate, not assumed).**

- Check current official Claude Code gateway documentation and the *actual* Odysseus route/response formats.
- Determine if the API provides Anthropic Messages-compatible `/v1/messages`, headers, request/response shapes, tools/tool IDs, SSE streams, timeouts, model aliases and error semantics. Existing `/misumi/respond` and `/api/estate/run` are not wire-compatible solely because they accept HTTP POST.
- Record whether the technical integration is *officially supported*, *achievable only through an adapter*, *unsupported* or *unverified*. Existing FCC compatibility does not establish that this API will work.
- Do **not** implement a production model gateway unless the tool route has failed an articulated user requirement, a minimum compatible proxy is justified by evidence, and all security, cost, stream/tool-use and rollback gates are met. A feasibility finding is a valid deliverable.

## Stage 3. Acceptance and closeout

- [ ] PR #205 (or an explicitly identified successor) passes relevant CI, review and merge checks. No unreviewed duplicate CLI implementation.
- [ ] `am` and legacy `aoteru` are both callable on the actual laptop, preserve existing settings, and handle common PowerShell input safely.
- [ ] Real `am "question"` invokes Aoteru conversation with correct routing, session behaviour and source/provenance; `am ask` remains a separate governed execution path.
- [ ] Tests demonstrate scope isolation, access denial, non-execution from chat, backward compatibility, and no credential exposure.
- [ ] Claude Code successfully invokes an authenticated Aoteru query via the existing scoped tool path (or a justified minimal MCP bridge) on a real session. If the operator has not enabled permissions or the host is unreachable, record the exact blocked action rather than claiming success.
- [ ] A Claude Code *model-provider* feasibility table cites the precise protocol gaps, support policy and tests. No claim of direct API compatibility without an end-to-end tool/streaming proof.
- [ ] User-facing documentation states the names/roles plainly and gives the shortest working commands.
- [ ] Result includes actual versions, commit(s), tests, deployment evidence, limitations and rollback. An open PR, passing unit tests or a documented plan alone is not shipped.

## Priority, scope and stopping

Follow the 2026-10-17 **shipping-first** instruction in `AGENTS.md`. First finish existing PR #205 and obtain real-host proof. Next enable Claude Code tool access with the smallest change. Only then consider further ergonomics, and do not build a model-proxy architecture without measured need. A credential or operator-interaction gate blocks only that action; continue independent code, test and documentation verification.

No cross-repository copy of Misumi or PhD knowledge, no second routing authority, no unattended token provisioning, no firewall changes and no silent production cutover. Preserve the user's requested simplicity as the outcome, not as an excuse to weaken controls.
