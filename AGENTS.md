# Delegation invariant

For every substantive task unit: decompose it, resolve authority and repo,
inspect live eligible workers/executors, dispatch to the cheapest adequate
lane, verify, and escalate only on recorded evidence.

Before starting bounded implementation, refactoring, debugging, test
authoring, review, repository reconnaissance, batch, scan, test, index,
evaluation, or simulation work, run:

```text
aoteru preflight "<task>" [--repo <repo-id>]
```

The equivalent backend call is `POST /api/estate/preflight`. Follow its live
recommendation. Codex implementation requires an existing active repo write
lease; preflight and execution must never acquire one implicitly. Dispatch it
with the equivalent `POST /api/estate/run` envelope or:

```text
aoteru ask "<task>" --repo <id> --capability code-strong --allow-paid --implementation
```

Retain work in the controller only for intent, architecture or methodological
judgement, ambiguity resolution, cross-worker synthesis, arbitration, or final
acceptance. Record a concrete `nondelegation_reason` whenever retaining an
otherwise eligible unit.

`docs/aoteru-model-host-routing-contract.md` is the routing and authority
contract. Do not duplicate or override it here.


## Global initialising prompt register

Odysseus owns the cross-repository initialising-prompt register:

- registry: `config/initialising-prompts.yaml`
- contract: `docs/initialising-prompt-register.md`
- immutable prompt bodies: `docs/initialising-prompts/**`
- append-only application traces: `evals/prompt-applications/**`

At the start of a substantive session, check whether the target repository/task matches an active registered initialiser. If the operator supplied a registered initialiser, resolve it by `prompt_id` + `version`; do not silently substitute another version.

At substantive session closeout, record one application trace when a registered initialiser was actually used. The trace records repository/branch, start/end commits, outcome, stop reason, models/routes used, verification evidence, and a rubric-based agent rating. Operator rating is separate and optional; never invent it. Ratings are improvement telemetry only: they may justify proposing a new prompt version, but they never mutate an existing prompt, widen authority, or override repository-local instructions.

Repository-local agents must not create competing prompt registries. They may carry a lightweight pointer to this global register.
