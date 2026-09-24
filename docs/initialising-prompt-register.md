# Global initialising prompt register

Status: active cross-repository operating contract  
Owner: `tyecam1/odysseus`

## Purpose

Maintain one global registry of trusted operator-authored session initialisers
across the user's active repositories, while preserving repository-local
authority.

The register answers:

- which initialiser/version was used;
- where and when it was applied;
- what the session actually achieved;
- how well the session performed;
- whether repeated evidence justifies proposing a revised initialiser.

It is not a second scheduler, memory authority, repository authority or prompt
self-modification system.

## Canonical surfaces

- registry: `config/initialising-prompts.yaml`
- prompt bodies: `docs/initialising-prompts/**`
- application traces: `evals/prompt-applications/**`

Repository-local files may point here but must not duplicate the registry.

## Prompt lifecycle

1. Register a stable `prompt_id`.
2. Store each prompt body as an immutable versioned file.
3. Select a version explicitly from session/operator intent plus registered
   scope. Never auto-apply an unrelated domain prompt.
4. Use live repository authority to resolve factual drift; do not rewrite the
   registered prompt during the session.
5. On session close, append one application trace.
6. Repeated trace evidence may justify a **new version**. Existing versions are
   never silently edited to improve their historical score.

## Application trace

One trace represents one substantive session/application, not one commit.

Required fields:

```yaml
schema_version: 1
application_id:
prompt_id:
prompt_version:
repository:
branch:
session_started_at:
session_ended_at:
start_commit:
end_commit:
outcome_status: complete | partial | blocked | failed
stop_reason:
commits: []
models_routes: []
verification: []
failure_tags: []
rating:
  scale: 1-5
  goal_progress:
  correctness_verification:
  authority_scope_discipline:
  routing_resource_efficiency:
  continuity_handoff_quality:
  agent_overall:
  operator_overall: null
  operator_note: null
prompt_revision_recommended: false
revision_reason:
evidence: []
```

No raw chain-of-thought, hidden reasoning, credentials, full transcripts or
sensitive prompt context belong in traces.

## Rating rubric

Use integers 1-5 for each dimension.

- **5** — exemplary: materially advances the goal, verified, efficient, no
  meaningful governance/continuity defect.
- **4** — strong: good progress with minor repairable inefficiency or drift.
- **3** — adequate: useful progress but a meaningful avoidable defect, stall or
  routing inefficiency occurred.
- **2** — weak: limited progress or major avoidable defect/rework.
- **1** — failed: session substantially missed its goal, violated authority, or
  produced unusable/unverified work.

`agent_overall` is the arithmetic mean of the five dimensions, rounded to one
decimal. Do not inflate it to reward effort or commit count.

`operator_overall` is null unless the operator explicitly rates the session.
Operator feedback may be appended as an amendment/pointer; never invent it.

## Learning and propagation

Prompt traces are telemetry inputs to existing improvement/routing loops. They
may support:

- identifying failure patterns;
- comparing prompt versions within the same task class;
- proposing a revised prompt;
- discovering that a prompt is too narrow, too permissive or too expensive;
- identifying model/routing mismatches.

They may **not** automatically:

- mutate an active prompt;
- promote a candidate prompt;
- change model/provider authority;
- weaken verification/evidence requirements;
- widen filesystem/repository permissions;
- override repository-local `AGENTS.md`, method or safety contracts.

Any revised initializer is a new version with its own provenance.

## Cross-repository discovery

Registered repositories should expose only a lightweight pointer in their agent
startup instructions. Odysseus remains the single owner.

If Odysseus is temporarily unavailable, continue under the repository-local
authority and preserve the trace payload for later append. Do not create a local
replacement registry.
