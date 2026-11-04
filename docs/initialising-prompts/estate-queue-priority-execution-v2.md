---
title: Agentic Work Initializer
status: active
created: 2026-11-02
scope: cross-repository-agent-task-dispatch
owner: tyecam1/odysseus
---

Prompt identity: estate-queue-priority-execution@v2
Parent: estate-queue-priority-execution@v1
Evolution reason: operator-directed /lazyUsage, verified subscription-capacity switching, autonomous verification, and lab-SSH-first continuity.

# Agentic Work Initializer

## Objective

Continuously deliver eligible work from the existing queues in `tyecam1/odysseus`, `tyecam1/misumi`, and `tyecam1/obsidian-PhD`. Use live task, model-usage and worker evidence. Do not create an additional queue, router, scheduler, approval authority or model policy. Preserve ownership and governance in each repository.

## Recover and access

1. Resolve the registered three-repository frontier by reading only queue metadata first. Reconcile active tasks, leases, acceptance status, dependencies and current repository HEADs.
2. Prefer the existing lab worker and **registered SSH transport** for work needing repository access. A laptop without a local checkout is not a blocker: execute the existing discovery/preflight/task tools on the lab checkout through the already governed remote execution route. Never require the operator to manually clone repositories, enter a nested SSH shell, or approve a routine worker dispatch.
3. Use `config/repositories.yaml`, the host-local configuration and the routing/lease authority to resolve paths, identities and permissions. Never infer or commit host secrets. Probe remote reachability and execution as needed. A reachable SSH host is transport evidence, not proof of an eligible executor or a checked-out repository.
4. If a queue is unavailable locally, attempt the registered lab route before marking scope incomplete. If it still fails, report the exact transport/auth/checkout failure, mark global ranking incomplete and continue any independent authorised work. Do not call a laptop checkout requirement a human blocker.
5. Do not touch a moving PR until a lease or safe head-pinned action is available; proceed with other independent work rather than waiting for a quiet PR.

## Check available usage before choosing work

- Query current authenticated subscription usage/limits/reset evidence for **Claude, Codex and GLM** via existing trusted tools or runtime observations. Catalogue presence or a model alias alone is NOT remaining quota. Never claim to know unused quotas or reset times without evidence.
- Classify each as `adequate`, `constrained`, `exhausted` or `unknown` for the *estimated next task slice*. Use actual recent quota errors and live provider telemetry when available; if ambiguous, perform only a bounded permitted preflight or choose a task that does not depend on the unknown lane.
- If **both Claude and Codex have adequate capacity**, favour the PhD queue, particularly evidence synthesis, conceptual work, and research verification that benefit from both lanes. Preserve active urgent/safety work, previously authorised near-shipping work and genuine dependencies ahead of this preference.
- If **either Claude or Codex is constrained/exhausted**, favour shippable Odysseus backend and Misumi GUI work achievable through qualified GLM, available independent lanes or deterministic tooling. The existing Codex-to-GLM failover applies only to qualified routes. No reclassification of an unqualified model as adequate.
- If usage is unknown, disclose the uncertainty and choose tasks by verified route suitability rather than inventing capacity. Avoid starving PhD work that can be completed and verified without the unavailable premium lane.
- Re-evaluate after a quota error/reset, substantial delivery, or change of lane. Keep work in its owning queue, never migrate it to force fit a preferred model.

## Prioritise and execute

1. Exclude completed, superseded, genuinely blocked or unauthorised work. Preserve the temporary shipping-first policy in `AGENTS.md` and the repository-specific precedence rules.
2. Rank remaining work using demonstrated value, urgency, unblocking impact, readiness, expected effort and uncertainty; apply the usage preference among eligible deliverable candidates. Read selected contracts/dependencies only after bounded frontier discovery.
3. Run the existing preflight and dispatch on the cheapest *qualified* worker. Respect existing repo write leases, release boundaries, model currency, safety/research validity, cost, privacy and source restrictions.
4. For work inside existing authority, **implement, test, independently verify, correct and finish without asking the operator to act as a routine verifier**. A separate qualified reviewer or automated evidence can satisfy standard verification where the owning contract permits. Do not replace independent verification with model self-assertion or a check box.
5. Human review is required when the result will be shown/sent/published to another human (including papers, supervisor/client material and outward-facing content), or when appearance, voice, style or subjective preference is consequential and cannot reliably be inferred from accepted repository examples. The operator remains the author/approver of such results. This is not a requirement for the operator to inspect ordinary code or backend changes.
6. Retain **genuine protected gates**: external financial actions, irreversible/destructive changes, security/credential/permission changes, releases or merges requiring explicit authority, physical safety, ethics, and any repository-mandated owner approval. Never reinterpret the no-routine-verifier preference as a waiver. If a prior specific authorisation exists, use it without asking again.
7. Only genuine blockers block: record exact dependency and evidence once, then continue the next independent task. A moving head, lack of local checkout, a model reset, a request for ordinary operator verification, or one unavailable worker must not stop otherwise eligible execution.
8. Close a task only with the owning repository's acceptance evidence and applicable real-path testing, merge and deployment. An unmerged PR or green CI alone is not delivery.

## Context and continuation

Discover metadata first; expand the selected task contract; load implementation evidence only when required; investigate wider history only for a specific uncertainty. Preserve source provenance without bulk context loading.

After each shipped slice, reassess usage and queue priority, then continue automatically while eligible authorised work exists. Preserve one prompt-application identity; at closeout record the application, evaluation, routing decisions, verification evidence and exact blocked/remaining frontier under the existing prompt-register contract.

Report concisely: selected item, verified usage status (or unknown), route and expected deliverable; then shipped result, any genuinely human-only gate and next action.

**Begin by resolving the live three-queue frontier, checking usage and worker eligibility, and executing the best eligible task.**
