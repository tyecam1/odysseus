# Odysseus agent-task execution bridge implementation packet

Status: staged implementation packet, not capability truth.

Authority: the controlling work item is `tyecam1/obsidian-PhD:automation/review/agent-tasks/ready/2026-08-30-odysseus-agent-task-execution-bridge.agent-task.md` once merged. This packet is deliberately subordinate to that task and exists only so the Odysseus implementation branch has a bounded local brief without duplicating the task lifecycle.

## Objective

Connect the existing governed `obsidian-PhD` agent-task lifecycle to the existing Odysseus estate router and scheduler without creating a second queue, router, scheduler, lease authority, model registry, graph store, or self-improvement framework.

The PhD side owns durable task intent, write authority and verification semantics. Odysseus owns runtime task leasing, repo parking, live host/provider/model routing, execution, recovery and routing telemetry.

## Frozen implementation sequence

1. PR 0: truth convergence and red/characterisation tests only. Resolve provider-pinned task metadata versus provider-neutral runtime routing, strict envelope semantics, cross-repo task-scope validation, exclusive task claims, action activation boundaries and route/run evaluation correlation. Enable no new autonomous behaviour.
2. PR 1: deterministic PhD task adapter producing a strict machine-readable ExecutionSpec and atomic lifecycle operations.
3. PR 2: one Odysseus task pump that claims eligible PhD work, uses existing ParkLease and estate_router surfaces, records correlation IDs and executes only through existing gates.
4. PR 3: V0/V1/V2/V3 verification and lifecycle closure with final task quality attributable to the originating RoutingDecision.
5. PR 4: extend existing routing evaluator + PhD agent-run evaluator + improvement loop into replay/regression/shadow/canary-gated adaptation without autonomous permission widening.
6. PR 5: broaden hosts/providers only through existing live registries and benchmark evidence.

## Non-negotiable rules

- Runtime provider/model choice is Odysseus-derived from capabilities and live eligibility; a legacy task `executor` field must not become an authority-bearing provider pin.
- Never use an LLM to decide whether an LLM is required.
- Unsupported authority/budget/placement fields fail strict validation instead of being silently ignored.
- Git task state is durable intent, not the distributed execution lock. Use durable runtime leasing/transactional uniqueness for claims.
- Use at-least-once execution with idempotent effects and explicit crash recovery. External mutations are never automatically retried.
- Preserve separate pre-execution authority and post-execution verification/acceptance authority.
- External content is untrusted data: acquire/extract into bounded structured records before privileged reasoning.
- Every run correlates `task_id`, `run_id`, `routing_decision_id`, final verification and agent-run evaluation.
- Failed/rejected outputs may inform operational learning but never silently become canonical research knowledge.
- An improvement may not widen permissions, weaken human gates, broaden canonical authority, introduce new safety/provenance failures, or regress a frozen critical case.
- Heavy background GPU inference yields to robotics experiments using the existing experiment-priority mechanism.
- Idle hardware is not a reason to manufacture work.

## First instruction

Start with PR 0 only. Inspect existing owners before adding code. Prefer deletion, de-authorisation or reuse over compatibility layers. Do not claim capability completion until a real or safely simulated ready -> claim -> route -> execute -> verify -> close trace exists and is correlated end-to-end.
