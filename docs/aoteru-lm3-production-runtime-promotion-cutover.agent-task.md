---
artifact_type: agent-task
task_schema: agent-task/v1
task_id: 2026-08-23-aoteru-lm3-production-runtime-promotion-cutover
title: "Upgrade production local runtime and cut over LM2-qualified aliases"
status: ready
priority: high
task_type: production-runtime-promotion-cutover
created_by: chatgpt
created_at: 2026-08-23T01:31:00+01:00
executor: claude-sonnet-5
execution_mode: infrastructure-cutover
resource_profile: standard
risk_level: medium
approval_required: false
source_traceability_required: true
requires_local_model: true
requires_remote_compute: false
requires_web: false
repo: tyecam1/odysseus
branch: dev
inputs:
  - docs/aoteru-lm2-model-discovery-evidence.md
  - docs/aoteru-lm2-quant-runtime-discovery.agent-task.md
  - docs/aoteru-local-model-benchmark-routing-evidence.md
  - docs/aoteru-model-host-routing-contract.md
  - config/models.yaml
outputs:
  - production Ollama upgraded and verified, or exact human-only sudo boundary
  - only LM2-qualified production artifacts installed
  - evidence-backed alias bindings applied only after production-path smoke passes
  - compact cutover evidence document
notes: "Do not re-run LM2. This task is a production-runtime and alias cutover only. Preserve rollback at every step."
---
# LM3 — production runtime + promotion cutover

## Goal

Remove the single infrastructure blocker identified by LM2, then promote only the three configurations that already cleared LM2 evidence gates:

- `code-fast -> ornith:9b`
- `reasoning-strong -> nemotron-3.5-lightning:30b-a3b`
- `vision -> gemma4:12b`

Keep incumbent bindings unchanged:

- `local-fast -> qwen3:8b`
- `local-strong -> gpt-oss:20b`

LM3 is **not another benchmark phase**. Reuse LM2 evidence; perform only the minimum production-path qualification needed to prove the upgraded runtime can actually serve each promoted model correctly.

## Preflight

1. `git pull --ff-only`; confirm clean `dev` and that `origin/dev` contains LM2 completion commit `ddb5ec37f55a21a802a938a4cdfef4e286a06607` or a direct descendant.
2. Read this task and the five inputs above. Do not redo model discovery, quant sweeps, or family screening.
3. Capture current production state before mutation:
   - Ollama version, binary path, systemd unit/status;
   - current production model inventory;
   - `config/models.yaml` bindings/state;
   - `odysseus-aoteru-lab.service` health;
   - listeners/private exposure;
   - current `local-fast` and `local-strong` live smokes.
4. Record a compact rollback manifest sufficient to restore the previous Ollama/runtime state and alias config if the upgrade fails.
5. Confirm no temporary LM2 Ollama/llama.cpp processes remain and no unrelated GPU workload is active.

## Privilege boundary

Test noninteractive privilege only with a bounded `sudo -n true`.

- If it succeeds, continue autonomously.
- If sudo requires human authentication, do not bypass, request, print, capture or persist any password. Complete every nonprivileged precheck and stop only at the exact minimal operator commands required to upgrade/restart production Ollama safely.
- After the operator action, the same session should resume from verification; do not restart LM3 from scratch.

## Runtime upgrade

Upgrade **production Ollama** from the current blocked version to a current stable version that supports the three LM2-qualified families. Prefer the existing supported installation/update mechanism already used on this host; do not replace the runtime architecture merely because scratch llama.cpp was used for LM2.

Requirements:

1. Preserve service ownership, loopback-only exposure and existing model storage where possible.
2. Do not introduce a second persistent Ollama service.
3. Restart production Ollama under systemd after upgrade.
4. Verify:
   - service active;
   - expected version running;
   - bound to loopback/private interface only as before;
   - incumbent `qwen3:8b` and `gpt-oss:20b` still load and answer;
   - Odysseus local execution still reaches production Ollama.
5. If incumbent compatibility regresses, rollback before any alias promotion.

## Install only qualified models

Acquire/install only the three LM2 winners, sequentially, one model at a time:

1. `ornith:9b`
2. `nemotron-3.5-lightning:30b-a3b`
3. `gemma4:12b`

Use the exact production-deployable artifacts/identifiers supported by the upgraded Ollama and trace them back to the LM2 evidence/model registry. If the exact LM2-tested artifact cannot be reproduced in production, do **not** assume equivalence: record the mismatch and leave that alias unbound unless a tiny equivalence check can defensibly establish parity.

Do not pull rejected LM2 candidates.

Keep `installed_candidates.state` accurate after each step.

## Production qualification and binding

For each candidate independently:

1. confirm the production runtime can load it;
2. run the smallest production-path smoke through Odysseus needed to prove the target capability:
   - `code-fast`: one bounded code-repair/task-structure check drawn from the existing frozen corpus;
   - `reasoning-strong`: one reasoning task from the existing frozen corpus;
   - `vision`: one existing image-understanding fixture through the real production path;
3. verify non-empty/valid output and the existing deterministic/task-specific gate;
4. only then update the corresponding alias binding in `config/models.yaml`;
5. immediately exercise routing through that alias and persist the outcome;
6. if any production smoke fails, rollback **that alias/model only** and continue with the others where safe.

Do not rerun the 3-trial LM2 matrices. LM2 already established comparative quality; LM3 establishes deployability and routing correctness.

## Regression gates

After all candidate attempts:

1. `local-fast` still routes to and executes `qwen3:8b` successfully.
2. `local-strong` still routes to and executes `gpt-oss:20b` successfully.
3. Every newly bound alias routes to its intended concrete model and executes through production Ollama.
4. Odysseus service remains healthy.
5. Ollama and Aoteru listeners remain private/loopback-only; no new `0.0.0.0` exposure, Funnel or public route.
6. Relevant SQLite routing/model state is consistent.
7. Run focused tests for routing/model/context/runtime paths plus one final relevant integration suite. Do not spend time on unrelated known baseline failures.

## Evidence and config

Create/update a compact `docs/aoteru-lm3-production-runtime-promotion-evidence.md` recording:

- before/after Ollama versions;
- exact operator action if sudo was required;
- exact production artifact/model identifiers installed;
- per-alias production smoke + bind/rollback result;
- incumbent regression results;
- service/private-exposure evidence;
- tests;
- any aliases still intentionally null and why.

Update `config/models.yaml` state/bindings only to reflect verified production truth. Do not edit LM2 evidence to make historical temporary-runtime tests look like production tests.

## Stop / handoff

Stop only when one of these is true:

1. runtime upgraded, all safe candidate promotions attempted, regression gates passed, evidence committed/pushed;
2. a genuine human-only sudo boundary remains after all possible nonprivileged work;
3. upgrade causes an architecture/safety regression that requires rollback and explicit operator review.

If blocked on sudo, report only:
- why the boundary is genuine;
- exact minimal operator commands;
- one-line continuation instruction.

If complete, commit cohesive changes to `dev`, push `origin/dev`, confirm local/remote HEAD match, and report only:
- Ollama before/after version;
- promoted aliases and exact production models;
- any failed/deferred alias and reason;
- incumbent regression status;
- service/private-exposure status;
- tests;
- final SHA.
