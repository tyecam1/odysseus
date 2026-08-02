# Prompt and skill library ingestion — implementation plan

Status: implementation plan for `feat/prompt-library-ingestion-20260802`.
Owner repository: `tyecam1/odysseus`.

## The problem this solves

A register that records what external prompt/skill sources exist is not an
ingestion system. It cannot answer "is this safe to run", "has it changed since
we looked", or "did adapting it actually help". This change builds the pipeline
that can.

## Pipeline stages (all of them, in order)

```
discover → snapshot → identify → licence-check → hash → quarantine
  → security-scan → classify → deduplicate → evaluate → adapt → review
  → activate | reject
```

Each stage is a separate, independently testable function. A candidate carries
a status naming the last stage it **completed**. A candidate that has not
reached `activate` is not usable — there is no partial-trust state.

### Stage semantics that must be enforced in code, not prose

- **snapshot** — the fetched bytes are stored immutably with their hash. Later
  stages read the snapshot, never the network. Re-fetching creates a *new*
  snapshot, never mutates one.
- **identify** — a candidate whose owner-qualified repository URL cannot be
  resolved to exactly one repository is `unresolved-identity` and **stops
  here**. A bare repository name is not an identity.
- **licence-check** — absent, ambiguous, or non-commercial/no-derivatives
  licences mean **defer or reject**. There is no "probably fine". A missing
  LICENSE file is not permission.
- **quarantine** — snapshot contents are inert data in a quarantine store.
  Nothing under quarantine is on any import path, prompt path, or skill search
  path. Prove this with a test that asserts the quarantine root is not
  reachable from the skill loader.
- **security-scan** — scan for prompt-injection patterns, instructions that
  attempt to redefine the agent's role or permissions, embedded credentials,
  and executable payloads. A scan that cannot run must report `not-scanned`,
  never `clean`.
- **evaluate** — against a **local held-out baseline** that existed before the
  candidate was seen. The candidate must not be able to contribute cases to the
  set it is judged on.
- **adapt** — prefer extracting a small principle over copying a large prompt.
  The adapted artifact records what it was derived from, and the derivation
  survives adaptation.
- **activate** — only from `review`, only with a licence permitting the actual
  use, only with a clean scan, only with an evaluation result.

## Required metadata (every field, every candidate)

```
repository_owner, repository_name, commit_or_release, licence,
retrieved_date, source_path, source_hash, intended_capability,
required_tools, required_permissions, assumed_environment,
prompt_injection_risk, overlapping_local_skill, evaluation_corpus,
adaptation_decision, status, retirement_condition
```

A missing field blocks progression. It does not default.

## Hard rules

- no bulk installation — one candidate at a time, each with its own record;
- no unverified source activation;
- no root-instruction mutation — an imported artifact may never modify
  `AGENTS.md`-class files, system prompts, or operating contracts;
- **no permission widening** — an imported skill may only request permissions
  already granted to its capability family; a request for more is a rejection
  reason, not a prompt to the operator;
- no second skill registry — activation registers into the *existing* registry;
- no prompt becomes memory authority;
- imported text is **untrusted data**, never instruction. Anything the pipeline
  reads from a snapshot is quoted, escaped, or fenced when it reaches a model,
  and never concatenated into a system prompt;
- licence ambiguity means defer or reject.

## Offline behaviour

The sandbox may have no network. That must produce an explicit
`discover: not-run` / `snapshot: not-fetched` state that blocks the candidate,
**not** an empty result that reads like "nothing found". Support ingesting from
a local directory snapshot so the pipeline is testable and demonstrable
offline, and label such candidates with the local provenance honestly.

## Deliver one real adapted capability

After the pipeline's tests pass, take **`mattpocock/skills`** through it end to
end. It is the only register candidate classified `adapt-pattern` with a
resolved identity and an MIT licence.

Requirements for that run:

- extract a small, named principle — not a copied prompt;
- evaluate the adapted capability against a held-out local baseline that
  predates the candidate;
- record the measured delta. **If it does not beat the baseline, reject it and
  record that.** A pipeline that has never rejected anything has not been
  tested.

Do not claim the pipeline complete with only a schema and a register.

## Tests that must exist

- a candidate with a bare repository name stops at `identify`;
- a candidate with no LICENSE file cannot reach `activate`;
- a CC-BY-NC-ND candidate cannot reach `activate`;
- quarantined content is not reachable from the skill loader (assert the path
  is absent from the loader's search roots);
- a security scan that fails to run yields `not-scanned`, and `not-scanned`
  blocks activation;
- an imported artifact attempting to modify a root instruction file is rejected;
- an imported skill requesting a permission outside its family is rejected;
- a candidate cannot add cases to its own evaluation corpus;
- re-fetching produces a new snapshot and leaves the old hash intact;
- a missing required metadata field blocks progression;
- with no network, `discover` reports `not-run` and no candidate silently
  advances;
- the end-to-end `mattpocock/skills` run reaches a terminal state with a
  recorded evaluation delta.

## Adversarial properties the verifier will attack

- Can an unscanned candidate render as clean?
- Can a candidate supply its own evaluation evidence?
- Can quarantined text reach a system prompt?
- Can a licence check pass on absence of evidence?
- Can `not-run` be read as "nothing found"?
- Can activation happen without a licence, a scan, or an evaluation?
- Can a rejected candidate leave residue on a load path?
