---
artifact_type: workflow
task_schema: agent-task/v1
task_id: 2026-06-10-elongate-odysseus-timeouts
title: Elongate Odysseus timeouts
status: done
priority: high
task_type: implementation
created_by: human
created_at: 2026-06-10T00:00:00+01:00
executor: codex_subscription
execution_mode: handoff
requires_remote_compute: false
requires_local_model: false
requires_zotero: false
requires_mcp: false
requires_web: false
verification_route: V2_HUMAN_VERIFIED
risk_level: medium
approval_required: true
source_traceability_required: true
repo: tyecam1/obsidian-PhD
branch: ""
allowed_paths:
  - automation/review/agent-tasks/**/2026-06-10-elongate-odysseus-timeouts.agent-task.md
denied_paths:
  - 03-concept/**
  - 07-standards/**
  - 01-research-plan/**
  - 02-library/00-papers/**
  - 02-library/01-annotations/**
  - 02-library/02-evidence/**
  - 00-dashboards/**
inputs:
  - automation/config/settings.ini
  - automation/config/odysseus_actions.yaml
outputs:
  - automation/review/routine-reports/odysseus-timeouts/2026-06-16.odysseus-timeout-audit.md
  - automation/config/settings.ini
  - automation/config/settings.local.example.ini
  - automation/config/settings.local.example.rag.ini
result_path: automation/review/routine-reports/odysseus-timeouts/2026-06-16.odysseus-timeout-audit.md
review_report_path: automation/review/routine-reports/odysseus-timeouts/2026-06-16.odysseus-timeout-audit.md
handoff_model: codex_work_package
handoff_prompt_path: "automation/review/handoff-prompts/2026-06-10-elongate-odysseus-timeouts.codex-work-package.md"
operator_decision_path: ""
linked_pr: ""
supersedes:
  - automation/review/queues/agent-tasks/2026-06-10-elongate-odysseus-timeouts.codex-implementation.md
duplicates: []
notes: "Implemented by Codex on 2026-06-16 under explicit operator authorization after rebase, overriding the earlier allowed_paths blocker. Preserves bounded execution and stale-lock safety; see timeout audit report."
---

# Task: Elongate Odysseus timeouts

## Objective

Audit and lengthen all Odysseus/Oddyseus timeout settings that are causing agent runs, connector calls, MCP calls, remote-box jobs, model calls, or long-running vault automation tasks to fail prematurely.

This is an implementation task for Codex because it is deterministic repo/config work. It should not be routed to Claude unless there is an ambiguous architectural decision after the audit.

## Scope

Search the repository for timeout-related configuration and hardcoded values across:

- Odysseus/Oddyseus service startup and health checks;
- Codex task loops;
- Claude task loops;
- MCP server/client calls;
- connector calls;
- remote compute-box upkeep jobs;
- GitHub Actions workflows;
- model/API call wrappers;
- local HTTP clients;
- subprocess wrappers;
- polling loops;
- SSH/Tailscale/remote execution helpers;
- retrieval, extraction, enrichment, and review-pack generation jobs.

Search terms should include at minimum:

- `timeout`
- `TIMEOUT`
- `read_timeout`
- `connect_timeout`
- `request_timeout`
- `idle_timeout`
- `deadline`
- `max_wait`
- `wait_for`
- `sleep`
- `poll`
- `retry`
- `backoff`
- `TTL`
- `abort`
- `kill`
- `subprocess.run(`
- `communicate(timeout=`
- `httpx`
- `requests`
- `aiohttp`
- `uvicorn`
- `gunicorn`
- `systemd`

## Required implementation behaviour

Do not simply increase every numeric timeout blindly. First classify each timeout as one of:

1. **interactive UI timeout** — should remain responsive;
2. **health-check timeout** — should be long enough for remote services but still fail closed;
3. **model/API timeout** — should support long reasoning/extraction calls;
4. **subprocess/job timeout** — should support long vault jobs but avoid infinite hangs;
5. **polling interval** — may need backoff rather than elongation;
6. **lock/stale-job timeout** — must not be made so long that broken locks persist;
7. **CI timeout** — should match realistic remote execution time;
8. **security/session timeout** — do not lengthen without explicit justification.

Then update only the values that are plausibly too short for Odysseus-controlled research-engine work.

## Preferred design

Where possible, replace scattered magic numbers with named configuration defaults, for example:

- `ODYSSEUS_HTTP_TIMEOUT_SECONDS`
- `ODYSSEUS_MODEL_TIMEOUT_SECONDS`
- `ODYSSEUS_AGENT_JOB_TIMEOUT_SECONDS`
- `ODYSSEUS_REMOTE_COMMAND_TIMEOUT_SECONDS`
- `ODYSSEUS_MCP_TIMEOUT_SECONDS`
- `ODYSSEUS_CONNECTOR_TIMEOUT_SECONDS`
- `ODYSSEUS_HEALTHCHECK_TIMEOUT_SECONDS`
- `ODYSSEUS_POLL_INTERVAL_SECONDS`

Use environment-variable overrides where appropriate, but preserve safe defaults.

## Suggested default direction

Use judgement based on existing code, but the target policy should roughly be:

- short connection timeouts: keep moderate, e.g. 10–30 seconds;
- HTTP read/model calls: extend substantially, e.g. 5–30 minutes depending on call type;
- long agent jobs: extend to hours where jobs are intentionally asynchronous/review-side;
- health checks: extend enough for remote services to wake, but still bounded;
- locks: keep stale-lock protection, do not create day-long stale locks;
- UI requests: do not block the interface for long jobs; convert to job submission/status if needed.

## Deliverables

Produce a PR that includes:

1. timeout audit summary;
2. changed timeout defaults;
3. centralised timeout configuration if feasible;
4. environment-variable override documentation;
5. tests or validation commands;
6. before/after list of affected files;
7. explicit list of timeout values intentionally not lengthened and why.

## Hard constraints

- No canonical vault promotion.
- No secrets committed.
- No public Odysseus/MCP/model endpoint exposure.
- No disabling fail-closed behaviour.
- No infinite timeouts unless the job is explicitly designed as a durable queued background task with status files and stale-job recovery.
- No removal of lock/stale-job safety.
- No laptop-local model fallback.
- No direct mutation of Zotero, PDFs, or external services.

## Acceptance criteria

This task is complete when Odysseus-controlled tasks can run long enough for realistic vault review/extraction/orchestration jobs without premature timeout failure, while still preserving bounded execution, stale-job recovery, and clear failure reporting.

The PR must include a clear summary suitable for adding to `automation/docs/current-capabilities.md` only if a new capability is genuinely introduced. If only defaults/configuration changed, do not update capability claims.

## Suggested commit message

```text
config: lengthen Odysseus runtime timeouts

- audit existing timeout and polling settings
- centralise Odysseus timeout defaults where practical
- lengthen long-running agent/model/remote-job timeouts
- preserve fail-closed health checks, stale-lock recovery, and safe UI behaviour
```
