---
artifact_type: agent-task
task_schema: agent-task/v1
task_id: 2026-08-23-aoteru-repo-aware-local-execution
title: "Aoteru repo-aware local execution"
status: ready
priority: high
task_type: finite-defect-fix
created_by: chatgpt
created_at: 2026-08-23T23:45:00+01:00
executor: claude-sonnet-5
execution_mode: finite-evidence-triggered-fix
repo: tyecam1/odysseus
branch: dev
---
# Aoteru repo-aware local execution

## Trigger

First real laptop use exposed a material defect after Workstream B activation.

From the Windows laptop, both:

- `aoteru ask "Review the current state of this repository and identify the highest-value next research action." --repo obsidian-phd --capability reasoning-strong`
- `aoteru ask "Summarise the current work item and its next action." --repo obsidian-phd --capability local-fast`

routed and executed successfully, but the local models replied that no repository/context had been supplied. The same repo-targeted paid Codex lane did inspect the real repository.

This is evidence-triggered corrective work, not a restart of `/loop`.

## Diagnosis to verify

Current thin client sends `repo` in the task envelope. Routing uses it for host/lease decisions. Paid Codex execution resolves the registered repo to a real cwd. Local execution currently sends only `objective` to `llm_call`, so `--repo` does not ground the local model in repository content.

A second defect is exposed by the same runs: the current deterministic gate passes any non-empty model output, so a generic refusal/request-for-context is recorded as `deterministic_gate=pass`.

## Mission

Make `aoteru ask ... --repo <repo-id>` semantically truthful for local execution with the smallest existing-authority-preserving change.

Do not create a second orchestrator, broad RAG system, repo copy, or autonomous loop.

## Required work

1. Deep-audit existing Odysseus context/retrieval/repository-reading surfaces before designing anything new. Reuse an existing bounded mechanism if one exists.
2. Preserve `config/repositories.yaml` + host-local root resolution as the only repo-path authority. Never trust a caller-supplied filesystem path.
3. For local execution with `repo` set, provide bounded, relevant, source-identifiable repository context sufficient for repo-aware questions. Do not dump the whole repository into the prompt.
4. If the repo cannot be resolved or useful context cannot be obtained, fail truthfully or return a clear context-unavailable state; never silently execute as if grounded.
5. Keep no-repo local prompts unchanged.
6. Improve execution verification so a response that explicitly says it lacks the requested repo/context cannot be recorded as a successful grounded repo answer merely because it is non-empty. Prefer deterministic, narrow checks; do not pretend to have a general semantic quality evaluator.
7. Keep paid Codex repo grounding unchanged unless a shared helper can reduce duplication safely.
8. Add focused regression tests covering local-fast and reasoning-strong repo-aware execution, unresolved repo failure, no-repo compatibility, and false-positive gate prevention.

## Live acceptance

After implementation/restart, from the real laptop run at minimum:

```powershell
aoteru ask "Summarise the current work item and its next action, citing the repository paths you used." --repo obsidian-phd --capability local-fast

aoteru ask "Review the current research state and identify the highest-value next action, citing the repository paths you used." --repo obsidian-phd --capability reasoning-strong
```

Acceptance requires:
- route remains canonical and local;
- answer demonstrates actual repository grounding with valid source paths/content;
- no generic "send me the repo/context" response;
- decision/result records grounding outcome truthfully;
- unresolved repo fails closed;
- no persistent laptop checkout or PhD content mutation;
- no paid call needed for acceptance.

## Stop condition

Stop after the focused defect is fixed, tested, live-proven from the laptop, and documented. Do not resume `/loop` or expand into unrelated UX, memory, evaluator, host, or model work.