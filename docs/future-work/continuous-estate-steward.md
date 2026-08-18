---
title: Continuous local estate steward
status: future-work
owner: odysseus
as_of: 2026-08-19
parent: docs/aoteru-estate-implementation-plan.md
---

# Continuous local estate steward

## Goal

Keep the strongest suitable **lab-local model permanently available as an idle/background estate steward**. Use spare compute to continuously reduce entropy across all registered repositories and both desktops without consuming paid-model quota or creating a second authority.

## Scope

The steward may continuously:

- audit registered repos, configs, docs, skills, MCPs, hooks, tasks and runtime state;
- detect duplicated capability, stale instructions, contradictory architecture, dead paths, drift and unfinished convergence;
- validate tests, schemas, links, capability truth, dependency/version state and backup/recovery posture;
- compress verbose/redundant documentation and generated state while preserving meaning/provenance;
- identify opportunities to merge, simplify, deduplicate or relocate capabilities to their canonical owner;
- compare lab/home inventories, services, models, clones and configuration for unnecessary divergence;
- maintain concise machine-readable findings, debt rankings and proposed patches;
- perform low-risk derived-state rebuilds and deterministic maintenance already authorised by each domain;
- use the home worker as an independent critic/verifier when useful and idle;
- contact the operator through WhatsApp only when a verified human permission/decision is genuinely required.

## Boundary

Default mode is **observe -> verify -> propose**, never free-running canonical modification.

- Read globally only through the estate registry/allowlists.
- Respect every repo's local instructions and authority.
- No mutation without the same parking lease, write scope and verification required for an interactive Aoteru task.
- Never auto-promote research evidence, memories, ontology, governance, credentials or external side effects.
- Never create a parallel queue, memory, router or architecture authority.
- Do not wake paid Claude/Codex merely to improve housekeeping. Escalate only when a queued finding is high-value and local verification cannot resolve it.
- Never ask for permission merely because the steward is uncertain; resolve uncertainty first where possible.

## Runtime

After `docs/aoteru-estate-implementation-plan.md` P10 passes:

1. Run as an Odysseus supervised background job on the lab PC.
2. Use a dedicated `estate-steward` capability alias resolved to the cheapest model that passes the steward benchmark; do not pin a brand permanently.
3. Operate at low priority and yield GPU/RAM immediately to interactive work.
4. Scan incrementally from Git commits, filesystem/runtime change events and prior steward checkpoints; never repeatedly reread entire repos.
5. Store only compact findings/state in Odysseus SQLite plus paths/hashes to supporting evidence.
6. Batch related findings into one convergence proposal rather than opening many micro-tasks.
7. Run an independent verifier before any proposed mutating maintenance is eligible for normal routing.

## Human approval escalation

WhatsApp is the preferred human-approval channel once a supported authenticated connector/gateway is available. Odysseus owns the approval protocol; the messaging transport remains replaceable.

Before contacting the operator, the steward must pass all checks:

1. **Concrete action** — exact intended change/action, target, scope and expected result.
2. **Policy check** — deterministic confirmation that current authority requires human approval.
3. **Necessity check** — no already-authorised lower-risk route can achieve the same goal.
4. **Correctness check** — proposal validated against current repo/runtime truth and relevant tests.
5. **Independent check** — a separate suitable verifier agrees both that the action is correct and that human permission is genuinely required.
6. **Rollback check** — recovery/rollback defined where applicable.
7. **Freeze** — immutable action payload/hash created; any material change invalidates approval.

Only then send one concise request:

```text
WHY: why this needs you
ACTION: exact bounded action
TARGET: repo/host/service
VALIDATED: checks/verifier passed
RISK: material risk only
ROLLBACK: recovery path or n/a
APPROVE: yes/no
ID: immutable action ID
```

Rules:

- silence is never approval;
- ambiguous replies are not approval;
- approval applies only to the exact action ID/scope presented;
- retain one durable pending request; do not repeatedly spam the same request;
- immediately before execution, re-check lease, target state, payload hash and preconditions;
- any material state/scope/diff change invalidates approval and requires revalidation.

## Approved autonomy

Once valid approval is received, the steward becomes autonomous **within that exact approved scope** and should complete the whole action without further routine human interaction.

It must:

1. acquire/verify the required parking lease and write authority;
2. execute the approved change using the cheapest adequate executor;
3. run all required tests, validation and domain gates;
4. repair failures autonomously while the repair remains inside the approved scope;
5. use independent verification before declaring success;
6. commit/push/open or update a PR when required by the target repo's normal workflow;
7. update implementation/task truth and provenance where required;
8. roll back automatically if the approved action fails safely and rollback is the defined recovery path;
9. return one concise completion/failure message through WhatsApp/Aoteru with evidence references.

Do not request permission again for ordinary implementation choices, debugging, tests, retries or bounded repairs already implied by the approved action. Ask again only if execution discovers a **new authority boundary, materially expanded scope, materially different risk, irreversible side effect, new credential/physical action, or invalidated action payload**.

## Output contract

Each finding is one structured record:

```text
repo/host | class | severity | evidence refs | canonical owner | proposed action | confidence | verification | status
```

Classes: `drift`, `duplication`, `stale`, `contradiction`, `test-failure`, `security`, `compression`, `convergence`, `dead-state`, `upgrade-candidate`.

Only surface findings to Aoteru when they are actionable, recurring or materially reduce risk/maintenance. Routine clean scans stay silent.

## Acceptance

- steward restarts automatically with the lab worker;
- idle operation does not materially degrade interactive latency;
- incremental scans cost substantially less than full rescans;
- every proposal resolves to evidence and one canonical owner;
- WhatsApp approval is requested only after policy, necessity, correctness and independent verification checks pass;
- approved action IDs cannot authorize materially changed work;
- after approval, bounded work proceeds autonomously through implementation, testing, verification and normal repo delivery;
- no unauthorised canonical write occurs in fault/adversarial tests;
- repeated runs reduce unresolved duplication/drift rather than create more review debt;
- home/lab divergence is visible and intentional or queued for convergence;
- paid-model use for estate housekeeping is exceptional and explicitly justified.