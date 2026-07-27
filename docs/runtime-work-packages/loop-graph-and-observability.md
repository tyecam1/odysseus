# Loop graph and operator observability

## Objective

Expose how objectives, contexts, skills, tools, services, stores, validators, permissions and human gates interact without exposing private content.

## Required views

- active run timeline;
- parent/child agent and tool spans;
- context composition and budget;
- permission grants and denials;
- evaluator scores and blocking failures;
- retry, branch, rollback and cancellation;
- degraded dependencies;
- generated graph of forward and feedback loops.

## Acceptance criteria

The operator can answer why a run failed, what it read, what it attempted to change, which gate blocked it and what evidence supports completion. Sanitisation tests prevent secrets, raw private prompts and unrestricted document contents from entering the normal trace store.
