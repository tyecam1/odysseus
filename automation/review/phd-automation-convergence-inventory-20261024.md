# PhD Scripts/automation shared-backend candidate inventory — 2026-10-24

Evidence for the downstream capability convergence pass named in
`docs/aoteru-repository-ownership-trajectory.md`. Baselines:
`obsidian-PhD/main@b548c3d`, `odysseus/dev@c175948` (post #148).
Classification: 112 entries inventoried — 110 files + 2 directories;
**98 PhD-domain (retain, no action)**, **14 shared-backend candidates**,
**0 demonstrably redundant (no retire candidates)**. "y" = a current
non-test caller exists in the PhD repo (not a deployment check).

| Module | What it does | Odysseus equivalent | Live callers | Verdict |
|---|---|---|---|---|
| agent_run_evaluator.py | Cross-harness run schema, sanitisation, replay, comparison ratchet | src/routing_evaluator.py (partial: routing only) | y | migrate |
| agent_task_dispatch.py | Selects inbox tasks, stages Claude candidates (no execution) | src/delegation_preflight.py, estate_router.py (candidate format differs) | y | wrap |
| agent_task_lint.py | Task schema/lifecycle/executor/scope validation | No matching frontmatter linter in src/ | y | wrap |
| audit_worker.py | Replays handoff unittests, audits changed paths | src/estate_worker.py (partial) | y | wrap |
| claude_job.py | Bounded jobs, model-lane pins, output/branch collection | src/task_scheduler.py, estate_router.py (no identical adapter) | y | wrap |
| engine_objective_validator.py | Generic agent loss/integrity/credit-assignment record validation | src/routing_evaluator.py (partial) | y | migrate |
| fire_post_run_artifact_triage.py | Scoped artifact commit/push + Routine API invocation | src/git_finalizer.py, task_scheduler.py (adapter absent) | y | wrap |
| improvement_loop.py | Fitness reports → lessons/iterations/skill drafts | src/prompt_evolution.py (partial) | y | wrap |
| local_model_guard.py | Host/endpoint policy, model-tag attestation | src/estate_router.py, endpoint_resolver.py (sentinels differ) | y | wrap |
| model_runtime.py | Model selection, Ollama calls, JSON parsing, readiness | src/llm_core.py, endpoint_resolver.py, estate_router.py | y | wrap |
| observability.py | Sanitised inference/flow traces, JSONL, Langfuse export | routing telemetry only (no general layer) | y | migrate |
| session_closeout.py | Cross-harness focus/verification/uncertainty closeout | runtime work package only (no implementation) | y | migrate |
| skill_lifecycle.py | Staged skill manifests, provenance, held-out validation | services/memory/oss_skill_ingestion.py (partial, different contract) | y | migrate |
| sleep_consolidation.py | Sanitised records → domain-separated memory candidates | services/memory/service.py (no consolidation validator) | y | migrate |

Reading per the trajectory's placement rule:
- "wrap" = genuinely PhD-facing interface with partial backend overlap; keep
  the PhD entry point, converge the shared seam behind Odysseus when the
  backend equivalence is proven. Do not migrate for filename similarity.
- "migrate" = semantics are genuinely backend-wide, but every item still has
  live PhD callers; migration requires the trajectory's proof-before-retire
  step (replacement proven, consumers checked) and is NOT authorised as a
  silent mid-stage move.
- No item is demonstrably redundant; nothing should be deleted on this
  evidence alone.

Method: read-only inventory by the Sol lane (gpt-6.1-sol, codex 0.163.0)
against live GitHub state, 2026-10-24; findings re-checked by the controller
before recording. Category-A list (98) intentionally omitted as PhD-domain
provenance retained in place.

## Migration verdict — 2026-10-26 review of the six "migrate" candidates

Re-checked against live `dev` and `obsidian-PhD@main` (post #629): none of the
six candidates (`agent_run_evaluator.py`, `engine_objective_validator.py`,
`observability.py`, `session_closeout.py`, `skill_lifecycle.py`,
`sleep_consolidation.py`) currently meets the placement conditions. No
demonstrated backend replacement exists (`src/routing_evaluator.py` remains
routing-only; `src/misumi_observability.py` is domain-specific, not a general
layer); every candidate still has live PhD callers; PhD-side automation development remains
active in the same package family (#629 extended the supervision updater and added `supervision_update_extractor.py`, though none of the six named modules was touched), so the practical coupling surface is not shrinking;
and cross-repo owner approvals for a semantics-preserving migration are not in
place. Migration today would be inventory-statistic-driven. Re-assess only when
a backend replacement has passed the PhD consumers' own tests and both
repository owners have approved the move.
