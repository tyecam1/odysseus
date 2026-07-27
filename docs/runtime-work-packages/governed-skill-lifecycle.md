# Governed skill lifecycle

## Objective

Provide one dynamically loaded skill registry and lifecycle for source-derived and trajectory-derived skills.

## Lifecycle

Discovery or repeated successful trace, candidate draft, static safety lint, held-out comparison, permission review, human approval, deployment, usage monitoring, revision and retirement.

## Requirements

- versioned manifests with triggers, exclusions, dependencies, context cost, tools and permission profile;
- on-demand loading instead of global prompt accumulation;
- contrastive tests with and without the skill;
- collision, over-trigger, under-trigger and stale-dependency detection;
- no automatic installation from public catalogues;
- no one-run auto-promotion.

## Acceptance criteria

One low-risk skill is evaluated on held-out cases and can be enabled, disabled and rolled back without editing global instructions or losing its provenance.
