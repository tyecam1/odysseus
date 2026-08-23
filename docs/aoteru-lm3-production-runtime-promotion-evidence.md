# LM3 — production runtime + promotion cutover: evidence

Task: `docs/aoteru-lm3-production-runtime-promotion-cutover.agent-task.md`.
Status: **complete**. Production Ollama upgraded, all three LM2-qualified
aliases bound and routing-verified, incumbents regression-clean, tests
pass. This document replaces the earlier preflight-only version (same
file, updated in place per the task's own convention, not a second doc).

## Preflight (completed before the sudo boundary)

- `git pull --ff-only` on `dev`: fast-forwarded `ddb5ec3` -> `f1e731d`
  (adds this task doc only). `f1e731d` is a direct descendant of LM2's
  completion commit `ddb5ec37f55a21a802a938a4cdfef4e286a06607`.
- Host confirmed as the lab worker (`hz2-workstation`), the only verified
  execution host per `config/estate.yaml`.
- Production Ollama state before any change: version `0.19.0`, binary
  `/usr/local/bin/ollama` (root:root, sha256
  `67d6bab88e63718d52782ee59db0e40436b35865f424b0ab13d9598e54d6e13a`),
  systemd unit `User=ollama`/`Group=ollama`/no `OLLAMA_HOST`, listener
  `127.0.0.1:11434` only, GPU idle, no leftover LM1/LM2 scratch processes,
  `odysseus-aoteru-lab.service` healthy, `config/models.yaml` unchanged
  since LM2.
- Incumbent live smokes through the real production path
  (`src.estate_router.run_task`): `local-fast -> qwen3:8b` and
  `local-strong -> gpt-oss:20b` both executed, gate `pass`.
- Full detail/rollback manifest for this stage is unchanged from the
  original preflight pass; see git history of this file (commit
  `96a1760`) for the verbatim record.

## Privilege boundary and operator action

`sudo -n true` failed noninteractively (password required); this session
reported the exact minimal operator commands and stopped rather than
bypass sudo. **The operator ran the upgrade interactively** (outside this
session — confirmed by the live state below); no password was seen,
requested, or persisted by this session at any point.

## Runtime upgrade verification

- `ollama --version`: **`0.19.0` -> `0.32.15`**.
- `systemctl is-active ollama.service`: `active`, single process
  (`/usr/local/bin/ollama serve`, new PID since the restart).
- Unit file unchanged in every field that matters: `User=ollama`,
  `Group=ollama`, `ExecStart=/usr/local/bin/ollama serve`,
  `Restart=always`, no `OLLAMA_HOST` override (only the `PATH=` value in
  `Environment=` differs, cosmetic/harmless). Not a second/duplicated
  service.
- Listener: still `127.0.0.1:11434` only (`ss -tlnp`) — no `0.0.0.0`
  exposure introduced by the upgrade.
- Pre-existing model inventory (`qwen3:8b`, `gpt-oss:20b`, `qwen3:30b`,
  `qwen3.5:9b`, `qwen3.6:35b`, embedding/reranker,
  `dmem-box-attest-20260802:sentinel`) all still listed; nothing removed.
- Incumbent regression re-run through `src.estate_router.run_task` after
  the upgrade: `local-fast -> qwen3:8b` gate `pass`, `local-strong ->
  gpt-oss:20b` gate `pass` — identical outcome to the pre-upgrade smoke.
- `odysseus-aoteru-lab.service` still `active`; Odysseus local execution
  confirmed reaching the upgraded production Ollama (the smokes above
  route through the real `execute_local` -> `llm_call` -> `127.0.0.1:11434`
  path, not a direct Ollama call).

No rollback was needed — the upgrade did not regress incumbent
compatibility.

## Per-alias production qualification and binding

All three LM2 winners were installed **sequentially, one at a time**,
each pulled directly by its Ollama-library tag, qualified with exactly
one production-path smoke drawn from the frozen corpus
(`evals/local_models/corpus.json`), then bound. LM2's 3-trial matrices
were **not** re-run — only enough evidence to prove the upgraded runtime
serves each model correctly.

### `code-fast -> ornith:9b`

- Pulled: `ollama pull ornith:9b` succeeded cleanly (5.6GB). `ollama show`:
  `requires 0.30.11` (production is 0.32.15, well above).
  Same artifact LM2 screened (39/39 across 3 trials on a temporary
  instance) — no substitution.
- Smoke: `code_repair-01` (bounded code-repair fixture) through
  `src.estate_router.execute_local("ornith:9b", ...)` against production
  `127.0.0.1:11434`. Output extracted and run against the real
  `test_lease.py` pytest fixture: **3/3 passed**, latency 9.9s.
- Bound in `config/models.yaml`; immediately re-exercised via
  `run_task({"requirements": {"capabilities": ["code-fast"]}})` ->
  resolved `ornith:9b`, executed, gate `pass`.
- `installed_candidates` state for `ornith:9b`: `benchmark-only` ->
  `production-installed`.

### `reasoning-strong -> nemotron-3.5-lightning:30b-a3b`

- Pulled: `ollama pull nemotron-3.5-lightning:30b-a3b` succeeded cleanly
  (25GB). `ollama show`: `requires 0.32.9` (production 0.32.15). Same
  artifact LM2 screened (36/39 across 3 trials) — no substitution.
- Smoke: `scientific_reasoning-01` (PhD evidence-rubric reasoning task)
  through `execute_local` against production. Keyword gate (`authoritative`
  + `synthesis` + one of `reality check`/`reality-check`/`implementation`)
  **passed**, latency 34.9s — consistent with LM2's ~29s average.
- No incumbent existed for this alias (previously `null`), so nothing to
  regress. Bound in `config/models.yaml`; re-exercised via `run_task` ->
  resolved `nemotron-3.5-lightning:30b-a3b`, executed, gate `pass`.
- `installed_candidates` state: `benchmark-only` -> `production-installed`.

### `vision -> gemma4:12b`

- **Artifact mismatch, disclosed rather than assumed away**: LM2's
  promotable vision evidence (37/42, vision 3/3) ran the *official QAT
  Q4_0 GGUF* directly via a scratch llama.cpp server — not an Ollama
  artifact at all. That exact artifact was not reproduced in production
  this pass.
- Pulled instead: `ollama pull gemma4:12b`, the Ollama-library build
  (Q4_K_M, 7.6GB, `requires 0.30.5`, architecture `gemma4`, 11.9B params,
  vision capability present per `ollama show`) — same family/param count
  as LM2's tested artifact, different quantization/packaging.
- Per the task's explicit instruction ("if the exact LM2-tested artifact
  cannot be reproduced in production, do not assume equivalence... unless
  a tiny equivalence check can defensibly establish parity"), ran that
  check: `doc_image-01` (read a VRAM figure off a synthetic status image)
  through `execute_local("gemma4:12b", <text+image content>)` against
  production. Output: *"The 'Peak VRAM this run' value shown is 7421
  MiB."* — keyword gate (`7421`) **passed**, latency 8.4s.
- This single production-path pass is the basis for the binding, not
  LM2's llama.cpp numbers directly — `config/models.yaml` says so
  explicitly on both the `capabilities.vision` entry and the
  `installed_candidates.gemma4:12b` entry, and the `gemma4:12b-qat-gguf-direct`
  row is left as-is (benchmark-only, distinct artifact, not claimed
  equivalent).
- Bound in `config/models.yaml`; re-exercised via
  `run_task({"objective": <text+image>, "requirements": {"capabilities":
  ["vision"]}})` -> resolved `gemma4:12b`, executed, gate `pass`.
- `installed_candidates` state for `gemma4:12b`: `benchmark-only` ->
  `production-installed`. `gemma4:12b-qat-gguf-direct` unchanged
  (`benchmark-only`, explicitly not reused for this binding).

No alias was deferred — all three LM2 winners qualified and bound.

## Regression gates (post-cutover)

1. `local-fast -> qwen3:8b`: executes, gate `pass`. ✅
2. `local-strong -> gpt-oss:20b`: executes, gate `pass`. ✅
3. `code-fast -> ornith:9b`, `reasoning-strong ->
   nemotron-3.5-lightning:30b-a3b`, `vision -> gemma4:12b`: each routes to
   its intended concrete model and executes through production Ollama. ✅
4. `odysseus-aoteru-lab.service`: `active` throughout. ✅
5. Listeners: Ollama still `127.0.0.1:11434` only; Odysseus backend still
   `127.0.0.1:7001` only. No `0.0.0.0`, no new Funnel/public route. ✅
6. SQLite `RoutingDecision` rows for the alias exercises above all show
   `status=complete`, `deterministic_gate=pass` with real latencies —
   consistent, no orphaned/failed rows from this pass. ✅
7. Tests: `tests/test_estate_router.py`, `tests/test_model_context.py`,
   `tests/test_api_call_integration_routing.py`,
   `tests/test_chat_image_routing.py` — **76/76 passed**. Full repo suite
   (excluding 4 files that fail to even collect due to a pre-existing,
   unrelated `mcp` SDK version mismatch — `Server.list_tools` —
   independent of this task): **4901 passed, 4 skipped, 11 failed**. The
   11 failures are the same pre-existing `mcp` `list_tools` issue
   (`test_imap_leak_fixes.py`, 10 cases) plus one unrelated
   `test_upload_handler_atomicity.py` case — none touch routing, models,
   estate config, or context selection. Not investigated further per the
   task's "do not spend time on unrelated known baseline failures."

## `config/models.yaml` changes

- `capabilities.code-fast`: `null` -> `ornith:9b`.
- `capabilities.reasoning-strong`: `null` -> `nemotron-3.5-lightning:30b-a3b`.
- `capabilities.vision`: `null` -> `gemma4:12b`.
- `capabilities.local-fast` / `capabilities.local-strong`: unchanged.
- `installed_candidates`: `ornith:9b`, `nemotron-3.5-lightning:30b-a3b`,
  `gemma4:12b` moved `benchmark-only` -> `production-installed`, each
  note updated to record the LM3 production pull/smoke/bind rather than
  rewriting the original LM2 evidence. `gemma4:12b-qat-gguf-direct`
  clarified as a distinct, not-reproduced-in-production artifact.
- No LM2 evidence document was edited to retroactively look like a
  production test.

## No aliases left deferred

All three targeted aliases (`code-fast`, `reasoning-strong`, `vision`)
are bound and verified. `code-strong` remains `null` (out of scope for
this task — no LM2 winner targeted it).
