# Misumi persona model calibration

Status: observed / proposed. This document is evaluation evidence and a routing-design input. It does not ratify or deploy production routing changes.

## Finding

The current architecture already has the correct model-side abstraction in `config/models.yaml`: evidence-backed capability aliases such as `local-fast`, `local-strong`, `code-fast`, `reasoning-strong`, and `vision`. The persona policy in `config/misumi_persona_policy.json` separately defines roles, skill categories, blocked tools, and modes. That separation is sound.

The missing link is explicit, measurable **persona task class -> capability requirement -> evaluation -> routing policy**. Persona policy currently contains no capability requirements, and the model registry contains no persona coupling. This is preferable to hard-coded persona/model bindings, but it means persona-specific model calibration is not yet operational.

A second gap is that `config/misumi_persona_policy.json` is presently policy data rather than an evidenced model-calibration control surface. Production routing must not infer that an important-sounding persona deserves a stronger model.

## Calibration rule

Keep persona identity independent from model identity.

```text
persona -> task class -> required capabilities -> cheapest validated capability alias
        -> deterministic/persona validator -> evidence-triggered fallback
```

Use existing capability aliases. Do not create persona-specific model aliases.

Escalation remains governed by `config/routing.yaml` triggers. A persona may request stronger capability only because a task class requires it or a validator/evidence trigger fires, never because of fictional rank or persona prestige.

## Initial task-class matrix

These are proposed evaluation targets, not production bindings.

| Persona | Canonical task classes | Default capability target to evaluate first | Fallback condition | Core metrics |
|---|---|---|---|---|
| Aoteru | intent routing; conflict/coherence review; ratification classification | `local-fast` for classification/routing; `local-strong` only for unresolved multi-constraint coherence | unresolved ambiguity, conflicting evidence, quality floor failure | routing accuracy, false escalation, authority classification, coherence |
| Lelouch | workflow decomposition; runbook execution; tool-plan generation | `local-fast`; `code-fast` where code/tool schema generation is intrinsic | deterministic gate/tool-plan validation failure | sequence correctness, precondition coverage, schema adherence, forbidden action rate |
| Kurisu | evidence extraction; provenance/uncertainty classification; document synthesis | `local-fast`; `local-strong` for long/contradictory evidence sets | provenance/contradiction validator failure, context limit | provenance fidelity, uncertainty preservation, contradiction recall, unsupported assertion rate |
| Misato | household care/routine assistance | `local-fast` | safety ambiguity or conflicting evidence | constraint adherence, unnecessary escalation, action usefulness |
| Jin | music/record/event selection | `local-fast` | retrieval insufficiency, unresolved ambiguity | retrieval grounding, preference fit, unsupported fact rate |
| Sanji | meal planning; stock substitution; shopping delta | `local-fast` | dietary/safety ambiguity, constraint failure | inventory grounding, constraint adherence, waste minimisation, unsupported ingredient rate |
| L | anomaly/budget mechanism diagnosis | `local-fast` for extraction; `local-strong` for multi-record diagnosis | conflicting evidence or diagnostic gate failure | evidence-chain fidelity, false-positive mechanism rate, confidence calibration |
| Ginko | environment/plant observation classification | `local-fast`; `vision` only when image interpretation is required | image task, safety ambiguity | observation grounding, uncertainty, classification accuracy, hazard overclaim rate |
| Ichigo | overdue/urgent-loop triage | `local-fast` | safety ambiguity or authority uncertainty | urgency classification, closure evidence, false closure rate |
| Giorno | bounded improvement proposal generation | `local-fast`; `local-strong` only after weak proposal evaluation | quality gate failure on evidence/risk/rollback completeness | proposal completeness, novelty-with-need, rollback quality, overengineering rate |
| Erwin | priority/risk/cost-of-delay ranking | `local-fast`; `local-strong` for genuinely coupled strategic trade-offs | conflicting evidence, unresolved ambiguity | ranking stability, evidence coverage, risk omission, unnecessary escalation |

The table deliberately starts most work at `local-fast`. Existing LM4 evidence shows that alias passed production canaries for repository reconnaissance and compact summarisation. It does **not** prove all persona task classes above. Those cells remain evaluation hypotheses until persona-specific batteries pass.

## Minimum evaluation battery

Each persona task class needs at least:

1. one normal representative case;
2. one adversarial authority/boundary case;
3. one uncertainty or missing-evidence case;
4. one historical failure/regression case once such a failure exists;
5. deterministic validation where the expected structure/decision can be encoded.

Record per run:

- persona and task class;
- capability alias and concrete model resolved at run time;
- model/config version;
- input fixture id and provenance;
- validator result;
- task-specific metric values;
- latency and token/cost observations where available;
- fallback/escalation event and trigger;
- code/config commit;
- timestamp/freshness;
- status (`observed`, `proposed`, `ratified`, etc.).

A routing change is eligible for review only when the candidate passes the applicable historical regression corpus and improves or preserves the relevant quality metrics. Cost/latency improvements do not excuse quality regression.

## Improvement graph contract

The operational graph should use the following minimal node types:

`Persona`, `Purpose`, `TaskClass`, `CapabilityRequirement`, `CapabilityAlias`, `ConcreteModel`, `Evaluation`, `Metric`, `FailureMode`, `ImprovementCandidate`, `Validator`, `RoutingDecision`, `Regression`, `Evidence`.

Required edges:

```text
Persona -serves-> Purpose
Persona -performs-> TaskClass
TaskClass -requires-> CapabilityRequirement
CapabilityRequirement -targets-> CapabilityAlias
CapabilityAlias -resolves_to-> ConcreteModel
Evaluation -tests-> (TaskClass, CapabilityAlias, ConcreteModel)
Evaluation -observes-> (Metric, FailureMode)
Validator -checks-> Evaluation
ImprovementCandidate -addresses-> FailureMode
RoutingDecision -supported_by-> Evidence
Regression -introduced_by-> change
```

Runtime-controlling assertions require provenance, freshness and status. Graph-derived routing must fail closed when evidence is absent or stale. The graph is evidence/control metadata, not a second household knowledge source of truth.

## Operationalisation audit

| Existing component | Current role | Gap to close |
|---|---|---|
| `config/models.yaml` | evidence-backed capability/model registry | add machine-readable evaluation references only when backed by real batteries; do not add persona bindings |
| `config/routing.yaml` | escalation/budget/verification policy | add task-class quality floors only when enough evidence exists; current `null` is correct |
| `config/misumi_persona_policy.json` | persona role/skills/tool authority | add task-class/capability requirements only after schema/consumer is implemented and tested |
| local-model eval harness | model comparison evidence | extend with persona/task-class fixtures and permanent historical regressions |
| persona evolution loop in Misumi repo | prompt candidate/evaluation/promotion | connect evaluation evidence to the graph, while retaining interactive user promotion gate |
| estate routing decision log | runtime model/host decisions | ensure persona/task class, validator outcome and fallback trigger are recorded for calibration aggregation |

## No-backwards-progression gate

A permanent regression fixture must be added whenever a material persona/routing failure is found and fixed. It may be superseded only by an equivalent or stricter fixture, never deleted because implementation changed.

Candidate routing/config changes must be evaluated against:

- persona task-class battery;
- authority/ratification tests;
- prior routing tests;
- historical fixed failures;
- provenance/uncertainty tests where applicable;
- relevant local-model production canaries.

Material trade-offs remain `proposed` and require review/ratification under the existing contracts.

## Next executable implementation slice

1. Add a machine-readable persona evaluation-spec file containing task classes, metrics and candidate capability aliases, explicitly marked non-routing/proposed.
2. Add schema validation that every active persona in `misumi_persona_policy.json` has an evaluation spec and that every referenced capability alias exists in `config/models.yaml`.
3. Extend the local-model evaluation harness with a small first battery for Aoteru, Lelouch and Kurisu.
4. Record evaluation outputs as graph/evidence records with provenance, timestamp and commit.
5. Only after evidence exists, prepare a separate reviewed production-routing proposal. Do not mutate production persona routing in the calibration implementation branch.
