# Global initialising prompt register

Status: active cross-repository operating contract  
Owner: `tyecam1/odysseus`

## Purpose

Maintain one global registry of trusted operator-authored session initialisers
across the user's active repositories, while preserving repository-local
authority.

The prompt system also preserves unusually valuable prompt designs as
**opportunistic exemplars**, regardless of task or domain, so novel prompting
ideas are not lost before they can be evaluated or distilled.

The register answers:

- which initialiser/version was used;
- where and when it was applied;
- what the session actually achieved;
- how well the session performed;
- whether repeated evidence justifies proposing a revised initialiser.

The exemplar store answers:

- which exact prompts were unusually worth preserving;
- why they were captured;
- which behaviours appear reusable;
- what execution/evaluation evidence later supported or weakened them.

It is not a second scheduler, memory authority, repository authority or prompt
self-modification system.

## Canonical surfaces

- registry: `config/initialising-prompts.yaml`
- prompt bodies: `docs/initialising-prompts/**`
- application traces: `evals/prompt-applications/**`
- prompt-evolution graphs: `evals/prompt-evolution/**`
- prompt exemplars: `evals/prompt-exemplars/**`

Repository-local files may point here but must not duplicate the registry.

## Prompt lifecycle

1. Register a stable `prompt_id`.
2. Store each prompt body as an immutable versioned file.
3. Select the active graph head from session/operator intent plus registered scope.
4. Use live repository authority to resolve factual drift; do not rewrite the active version.
5. On session close, append one application trace and rating.
6. Every application creates one prompt-evolution event.
7. Derive the smallest semantic improvement from observed performance: weak rating dimensions, failure tags, verification defects, missed executable work and explicit operator feedback.
8. If evidence supports a change, create a new immutable child version; otherwise add a reinforcement edge to the incumbent.
9. Validate protected invariants before a child can become active. Existing versions are never rewritten and failed candidates never replace the head.

## Opportunistic exemplar capture

Exemplar capture is deliberately **domain-agnostic and category-free**. A prompt
does not need to be a registered initialiser, belong to a known task class, or
have an existing component definition before it can be preserved.

### Capture trigger

During any task, assess prompts that are created, encountered, or materially
revised. Capture the exact prompt when:

1. the operator explicitly says it is worth preserving; **or**
2. the agent has high confidence that at least two aspects are unusually strong
   or novel, for example:
   - task framing or problem decomposition;
   - autonomy or long-horizon continuation;
   - verification/adversarial structure;
   - authority or constraint handling;
   - model/tool coordination;
   - context compression without loss of essential state;
   - search/retrieval strategy;
   - stopping or escalation logic;
   - creativity or another mechanism not already represented well in the gallery.

This is a judgement trigger, not a numeric reward model. Do not capture routine
prompts merely because they worked.

### Capture first, validate later

A prompt may be ingenious **before** execution evidence exists. Preserve it
immediately as a `candidate` exemplar rather than waiting for a successful
application and risking loss of the exact design.

Capture does not imply:

- scientific correctness;
- execution success;
- authority;
- promotion into an initializer;
- promotion into the component graph.

Later execution traces, evaluations, failures and explicit operator review may
change the exemplar status to `validated`, `mixed`, `superseded`, or
`rejected`. Never rewrite the original prompt body to make its history look
better.

### Required exemplar content

Each exemplar is one immutable Markdown record under
`evals/prompt-exemplars/**` containing:

- stable `exemplar_id`;
- capture date and basis;
- status;
- source/task context;
- exact prompt text;
- concise capture rationale;
- reusable behaviours worth testing;
- known task-specific assumptions or limitations;
- pointers to later applications/evaluations when available.

Do not store chain-of-thought, credentials, sensitive context or unnecessary
conversation transcript.

### Relationship to prompt evolution/components

The exemplar gallery is the **discovery layer**. It preserves novel prompt
designs before the system knows whether they deserve generalisation.

The prompt-evolution graph remains the **evidence layer** for registered
initialisers.

A future prompt-component graph may distil recurring behaviours from exemplars
and application traces, but it must preserve provenance back to the exact
exemplar(s). Components are downstream abstractions; they must never be a
precondition for capture.

A useful flow is therefore:

```text
novel prompt noticed
  -> exact candidate exemplar captured
  -> task/application evidence accumulates
  -> exemplar validated, narrowed or rejected
  -> reusable behaviour optionally distilled
  -> governed component/initializer evolution
```

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

## Prompt-evolution graph

The register is an evidence graph with three node classes: immutable
`prompt_version` nodes, rated `application` nodes, and `evolution_event`
nodes. Supported edges are `applied`, `observed`, `derived_child`,
`reinforced`, and `supersedes`.

Every substantive application closes one loop:

```text
prompt version
  -> application
  -> measured performance
  -> bounded improvement targets
  -> child prompt OR reinforcement
  -> protected-invariant validation
  -> next active head
```

Improvement is relative to observed failure, not generic polishing. Repeated
good performance reinforces an incumbent. Repeated failure on the same class
should strengthen or restructure that instruction rather than accrete duplicate
warnings.

The graph lives under `evals/prompt-evolution/**`; the deterministic helper is
`scripts/prompt_evolution.py`.

### Protected invariants

Evolution may never silently widen repository/filesystem/write scope; weaken
evidence, verification, stop, safety or approval gates; promote an advisory
model to acceptance authority; change model/provider identity rules without live
evidence; replace live repository state with prompt memory; convert access
failure into negative evidence; force unresolved scientific alternatives; or
remove required application tracing/evolution.

A candidate violating an invariant is blocked and the incumbent remains active.

## Learning and propagation

Prompt graph telemetry feeds the same continuous-improvement system as routing
telemetry. Aggregate by prompt id/version, ancestry, task class, failure tag and
rating dimension. Compare descendants against their parent/siblings, not
unrelated prompt scopes.

A validated evidence-derived child may become the next active head. The system
may not optimize ratings by making the task easier, suppressing failures or
reducing verification. Semantic drafting remains an agent task; graph structure,
provenance and invariant checks are mandatory.

## Cross-repository discovery

Registered repositories should expose only a lightweight pointer in their agent
startup instructions. Odysseus remains the single owner.

If Odysseus is temporarily unavailable, continue under the repository-local
authority and preserve the trace/exemplar payload for later append. Do not create
a local replacement registry.
