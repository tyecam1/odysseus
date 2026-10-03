---
artifact_type: agent-task
task_schema: agent-task/v2
task_id: 2026-10-02-home-worker-non-admin-identity
title: "Evaluate and migrate the home Aoteru worker to a dedicated non-administrator Windows identity"
status: inbox
priority: medium
task_type: implementation
created_by: claude
created_at: 2026-10-02T11:00:00+01:00
updated_at: 2026-10-03T15:00:00+01:00
executor: claude_subscription
execution_mode: review-first
architecture: single
architecture_rationale: "One identity/privilege boundary change on one host. Extend the existing runbook and forced-command setup; do not add a new worker protocol."
single_agent_baseline: "One implementation owner can create the account, move the per-user worker configuration, constrain the key and re-run the existing qualification steps."
execution_host: compute-box
context_budget: medium
coordination_reason: "Operator requirement during Stage 8 home enablement (Misumi long-horizon programme, 2026-10-02): the SSH worker runs as `User`, a local Administrator, which is acceptable for constrained deterministic/local compute but unnecessarily privileged for routine repo-writing automation."
requires_remote_compute: true
requires_local_model: false
requires_zotero: false
requires_mcp: false
requires_web: false
verification_route: V3_INDEPENDENT_MODEL_ADJUDICATION
risk_level: high
approval_required: true
source_traceability_required: true
repo: tyecam1/odysseus
branch: ""
allowed_paths:
  - docs/**
  - config/**
  - src/estate_worker*.py
  - tests/**
denied_paths:
  - "**/.env"
  - "**/secrets/**"
inputs:
  - docs/aoteru-home-worker-setup.md
  - docs/aoteru-multihost-execution-evidence.md
  - config/estate.yaml
outputs:
  - a dedicated non-administrator Windows account for the Aoteru worker, with per-user worker configuration
  - the worker key moved to that account's own authorized_keys, still forced-command and restricted
  - a reviewed access list (checkout, model/data directories) and an explicit statement of what it cannot touch
  - re-run qualification evidence under the new identity
result_path: ""
review_report_path: ""
handoff_model: gpt-5.6-sol
operator_decision_path: ""
supersedes: []
duplicates: []
notes: "Home currently qualifies for `deterministic` only. `codex-write` stays unqualified on home until this boundary is reviewed or the operator separately approves the administrator-backed write lane."
---

# Home worker: dedicated non-administrator identity

## Why

The home SSH worker authenticates as `User`, a local Administrator, through a key in
`C:\ProgramData\ssh\administrators_authorized_keys` (OpenSSH on Windows ignores the per-user file for administrators). A
compromised or buggy worker call therefore runs with administrator rights on a shared household desktop. That is
tolerable for the constrained qualification done in Stage 8 (deterministic work; the forced command and restrictions
bound what the key can start), but it is more privilege than routine repo-writing automation should have.

## Required work

1. Evaluate and, if sound, create a dedicated **non-administrator** Windows account for the worker. No membership of
   `Administrators`; no dependence on an ordinary interactive logon if avoidable.
2. Per-user worker configuration: the checkout, `venv`, `~/.aoteru` (capabilities, spool, sentinel) and any model/data
   paths under that account, with access **only** to what is required (the Aoteru checkout, the Ollama API on loopback,
   its own data directory). State explicitly what it cannot read or write (the household data, the other users'
   profiles, the Odysseus household runtime data root).
3. Move the worker key from `administrators_authorized_keys` to the account's own `authorized_keys`, keeping the forced
   command and `no-pty,no-port-forwarding,no-agent-forwarding,no-X11-forwarding`, with the ACL OpenSSH requires for a
   non-administrator account. Remove the old administrator entry only after the new path is proven.
4. Re-run the Stage 8 evidence under the new identity: pinned host key, `health` attestation (the machine fingerprint may
   differ by account: pin the new one), `inventory`, and the routing proof. The `local-fast` benchmark is re-run as part
   of this on a free GPU.
5. Record the S6.12 dependency: detached Windows runners (job objects) are not implemented, so nothing that needs
   them can be qualified on home regardless of identity.

## Not allowed

- No unrestricted key, no reuse of the worker key for another purpose, no change to unrelated SSH authorisation, no
  weakening of host-key pinning, no `StrictHostKeyChecking=no`.
- Do not add `codex-write` to home's `qualified_executors` as part of this task. That needs a separate review of the
  write lane (including S6.12) or the operator's explicit approval of an administrator-backed write lane.

## Acceptance

- The worker runs as a non-administrator and still passes `health`, `inventory` and the routing proof from lab.
- The administrator-backed entry is removed, and `administrators_authorized_keys` is otherwise unchanged.
- The reviewed access list and the re-run evidence are recorded in `docs/aoteru-multihost-execution-evidence.md`.

## Programme disposition (2026-10-03)

**State: open, deliberately not executed by the agent.** Creating a dedicated non-administrator Windows account on the household host, re-keying the worker and changing how the
home worker authenticates is a security-sensitive host change that needs the operator's explicit authorisation and a rollback session. Nothing depends on it for convergence: home is
an eligible worker for `deterministic` and `local` work under the existing administrator-scoped, forced-command key, and `codex-write` stays unqualified until this is done.
