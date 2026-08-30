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
