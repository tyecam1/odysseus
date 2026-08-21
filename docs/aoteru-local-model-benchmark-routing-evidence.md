---
title: Aoteru local-model benchmark + routing evidence — LM1
status: compact-evidence
owner: odysseus
as_of: 2026-08-21
parent: docs/aoteru-local-model-benchmark-routing.agent-task.md
---

# LM1 — local-model benchmark + routing evidence

Compact durable record for LM1
(`docs/aoteru-local-model-benchmark-routing.agent-task.md`). Read that file
for the full contract; this is the evidence and decisions, not a repeat of
the design.

## Live-state preflight

`git pull --ff-only` clean at session start (`ac295b7`). Confirmed running
directly on the lab host (`hz2-workstation`, RTX 3080/10GiB, i9-12900K,
125GiB RAM), `odysseus-aoteru-lab.service` active/healthy throughout,
loopback-only (`127.0.0.1:7001`, no `0.0.0.0` listener). Read all four
required inputs; did not redo the 2026-08-20 research. HF auth: `hf auth
whoami` -> not logged in, no `HF_TOKEN`; the three first-round candidates'
official repos (`google/gemma-4-e4b`, `google/gemma-4-12b`,
`Qwen/Qwen3.5-9B`) are all `apache-2.0`, not gated — confirmed live via
anonymous `huggingface_hub` metadata calls, no token needed or used.
`obsidian-PhD`/S2-E1: `config/repositories.yaml` records both with
`remote: null` ("not yet known to this registry") — genuinely unavailable,
not merely unmounted, so no fetch was possible; task classes 7
(PhD/scientific reasoning) and 12 (ROS/log/test interpretation) use real
Odysseus-repo content as an explicitly-labelled proxy instead (see corpus).

## Existing Odysseus benchmark/eval authority (inspected before adding anything)

`evals/misumi/fixtures.json` + `scripts/run_misumi_evals.py` is the one
existing eval convention (assertion-based HTTP behaviour gate) — extended
by adding a sibling `evals/local_models/` directory and
`scripts/run_local_model_benchmark.py` in the same style, not a new
authority. `core.database.RoutingDecision` is the one existing routing
telemetry table; added `core.database.BenchmarkResult` alongside it
(same SQLite file, `init_db()` picked it up via `create_all`, additive
only) rather than overloading `RoutingDecision`'s semantics — a benchmark
sweep compares several concrete models against one frozen task
deterministically, which is a different thing from one live routed
production decision. `config/models.yaml` (`installed_candidates`,
`benchmark_candidates`) and `config/routing.yaml` (`quality_floors`)
remain the one alias/policy authority — extended in place, not duplicated.

## Harness

- `evals/local_models/corpus.json` — 13 tasks covering all 12 required
  task classes (one class, `bounded_code_repair`, plus the load-bearing
  `long_context_retrieval` task run at both 8K and 32K, giving 14
  executions per model). Every task carries a frozen `source_pointer`
  (`tyecam1/odysseus@ac295b7:path#Lx-Ly`, or an explicit
  `synthetic`/`proxy` label where no real pointer exists) and a
  deterministic scorer (`keyword_all`, `json_tool_call`, `json_schema`,
  `summary`, or `pytest_fixture`).
- `evals/local_models/fixtures/` — the bounded code-repair fixture
  (a real one-line-bug mutation of `core/database.py`'s
  `park_lease_is_stale`, with 3 pytest cases confirmed to fail on the
  buggy version before use), a synthetic status image for the
  document/image-understanding task, and the 8K/32K long-context haystack
  files (real repo docs concatenated, with a unique needle fact inserted).
- `scripts/run_local_model_benchmark.py` — calls `src.llm_core.llm_call`
  directly, the exact function `src.estate_router.execute_local` wraps for
  live production routing, so a benchmarked model is exercised through the
  same call path a routed task would use. Scores deterministically,
  persists to `BenchmarkResult`, and writes a JSONL export.
- `tests/test_local_model_benchmark.py` — 9 unit tests on the corpus shape
  and the deterministic scorers (no live model calls). All passing.
- `evals/local_models/results/lm1-full-export.jsonl` — the 140 raw result
  rows (see below) with full provenance, exported straight from
  `BenchmarkResult`.

### A real corpus bug found and fixed mid-run

The two `repo_reconnaissance` tasks originally asked a model to answer
from memorised knowledge of this private repo's internals without
supplying any source — unwinnable for any model (confirmed: all three
baselines failed both, identically, before the fix). Fixed by inlining the
actual function source into the prompt, so the task genuinely measures
comprehension of supplied code rather than memorisation. The pre-fix rows
were deleted, not kept as false evidence.

### A real production bug found and fixed mid-run

`src.llm_core.llm_call`'s Ollama branch always requested a model's **full
advertised context window** as `num_ctx`, regardless of actual prompt
size — for `qwen3.5:9b` (context length 262144) this meant an 8K-token
prompt still allocated a quarter-million-token KV cache, which is what
production `execute_local` does too, not just this harness. This made the
"8K/32K screening points" the strategy doc asks for meaningless as
originally wired, and caused real 180s timeouts. Fixed with a minimal,
backward-compatible addition: `llm_call(..., num_ctx: Optional[int] =
None)` — omitted, behaviour is byte-for-byte unchanged (still calls
`get_context_length()` as before); the harness now passes each task's
actual `context_point`. Confirmed backward-compatible: 150 focused tests
across every file that calls `llm_call` still pass, and a live
`run_task()` smoke test against production Ollama after the change
returned `pong` normally (4090ms, `deterministic_gate: pass`).

**Correction (2026-08-21 audit-repair pass,
`docs/aoteru-lm1-audit-repair-lm2-design.agent-task.md`):** this section's
heading overstated the fix. What actually shipped here was the optional
`num_ctx` *parameter* plus the harness passing it — production
`src.estate_router.execute_local()` still called `llm_call()` without
`num_ctx`, so the live smoke test above ran with the same unbounded
full-window request this section describes as the bug, and every real
routed task hit it until the audit-repair pass. See that task's evidence
for the actual production fix
(`src.model_context.select_bounded_context`, wired into `execute_local`).

### A second real production-adjacent bug found and fixed mid-run

The lab's single RTX 3080 is shared between production Ollama (11434) and
the second Ollama instance below (11435). Neither instance released a
model before the next was loaded; a lingering `qwen3:30b` (9.4GiB
resident) on production caused every following candidate call on **either**
instance to fail with a CUDA out-of-memory error. Fixed by adding an
explicit `keep_alive: 0` unload of every resident model on both instances
before each model's turn (and once more at the end of a run). Confirmed
fixed: the retry run after this fix completed cleanly.

## Hugging Face acquisition

No token used or needed — anonymous `huggingface_hub` access confirmed
live for all three official repos (`gated: False`, `apache-2.0`).
Resolved artefacts:

- **Gemma 4 E4B**: official repo `google/gemma-4-e4b`; official
  Google-published QAT Q4_0 GGUF exists at
  `google/gemma-4-E4B-it-qat-q4_0-gguf` (5.15GB). Actually run via Ollama
  library's own `gemma4:e4b` (8.0B params, Q4_K_M, 9.6GB, no vision in
  this packaging) — the HF repo is recorded as the upstream anchor; the
  Ollama-library artefact's exact revision mapping to it is **not proven**
  (recorded honestly as `unproven-ollama-library-mapping` in
  `evals/local_models/model_manifest.json`, not fabricated).
- **Gemma 4 12B**: official repo `google/gemma-4-12b`; official QAT Q4_0
  GGUF at `google/gemma-4-12B-it-qat-q4_0-gguf` (6.98GB + 0.18GB mmproj).
  Run via Ollama library `gemma4:12b` (11.9B params, Q4_K_M, 7.56GB,
  vision-capable) — same unproven-revision caveat as above.
- **Qwen3.5-9B**: official repo `Qwen/Qwen3.5-9B`, apache-2.0. Run via
  Ollama library `qwen3.5:9b` (9.7B params, Q4_K_M, 6.6GB) — pulled
  cleanly onto **production** Ollama, no runtime blocker.

## Runtime blocker: Gemma 4 requires a newer Ollama than production runs

Production Ollama is `0.19.0` (systemd-supervised, root-owned binary, no
passwordless sudo in this session). `ollama pull gemma4:e4b` /
`gemma4:12b` against it fail immediately: `412: The model you are
attempting to pull requires a newer version of Ollama.` Qwen3.5-9B has no
such requirement and pulled normally onto production.

Rather than touch the live production Ollama service without operator
authorisation, this pass downloaded the latest static Ollama release
(`v0.32.15`, official GitHub release tarball, sha-verified by the
release's own checksum mechanism) into a **user-local, non-root, non-
systemd** location and ran it as a second instance
(`OLLAMA_HOST=127.0.0.1:11435`, isolated `OLLAMA_MODELS` dir, in this
job's scratch tmp dir — nothing under this repo or under
`/etc/systemd`). Both Gemma 4 candidates were pulled and benchmarked
through that second instance instead. **This second instance was a
temporary benchmark-only resource and has been shut down** (process
killed, GPU confirmed clear) — it is not a persistent estate service and
is not registered in `config/estate.yaml`.

**Consequence**: Gemma 4 E4B and Gemma 4 12B evidence below is real and
measured through a production-equivalent execution path (same
`llm_call`/Ollama HTTP API, same model artefacts), but **neither model can
actually be bound in `config/models.yaml`** — production `execute_local`
always calls `127.0.0.1:11434`, where these models don't exist and can't
be pulled without the version upgrade. This is the one genuine
human-only blocker LM1 hit.

**Exact safe action that unblocks Gemma 4** (no token/credential
involved, so nothing to keep out of chat): the operator runs the same
Ollama upgrade already downloaded once this pass —
`curl -fsSL https://ollama.com/install.sh | sh` (or equivalent package
upgrade) — against the **production** install, then `sudo systemctl
restart ollama`, then re-`ollama pull gemma4:e4b`/`gemma4:12b` on
`127.0.0.1:11434`. Until then, `vision` and any Gemma-4-backed alias stay
`null`, correctly, not silently faked.

## Benchmark results

Single screening pass, all 6 models x 13 tasks (14 executions, long-context
run at both 8K/32K); Gemma 4 candidates additionally repeated 2 more times
(3 total trials) since they are the only plausible finalists. Full raw
data: `evals/local_models/results/lm1-full-export.jsonl` (140 rows) and
`core.database.BenchmarkResult` (`run_id` in `lm1-screening-1`,
`lm1-finalists-trial2`, `lm1-finalists-trial3`).

| task_class (task_id) | qwen3:8b | gpt-oss:20b | qwen3:30b | qwen3.5:9b | gemma4:e4b (3 trials) | gemma4:12b (3 trials) |
|---|---|---|---|---|---|---|
| repo_reconnaissance (recon-01) | pass 7.5s | pass 13.2s | pass 36.5s | pass 6.1s | pass 3/3 | pass 3/3 |
| repo_reconnaissance (recon-02) | pass 3.4s | pass 4.6s | pass 18.3s | pass 3.0s | pass 2/3 | pass 3/3 |
| bounded_code_repair | pass 5.6s | **fail*** 12.7s | pass 47.8s | pass 73.0s | pass 3/3 | **fail 3/3** |
| fault_diagnosis | pass 6.8s | pass 14.6s | pass 16.9s | **fail** 47.5s | pass 3/3 | pass 2/3 |
| tool_function_call_correctness | pass 1.6s | pass 3.4s | pass 8.7s | pass 4.0s | pass 3/3 | pass 3/3 |
| strict_json_schema_output | pass 2.0s | pass 7.3s | pass 9.5s | pass 10.7s | pass 3/3 | pass 3/3 |
| evidence_extraction_provenance | pass 3.3s | pass 19.4s | pass 16.5s | pass 41.8s | pass 3/3 | pass 3/3 |
| phd_scientific_reasoning (proxy) | pass 5.3s | pass 13.4s | pass 32.3s | pass 51.7s | **fail 2/3** | **fail 3/3** |
| long_context_retrieval @8K | pass 6.4s | pass 12.5s | pass 33.4s | pass 10.1s | pass 3/3 | pass 3/3 |
| long_context_retrieval @32K | pass 21.8s | **fail** 50.9s | **error/timeout** 180s | pass 32.0s | pass 3/3 | pass 3/3 |
| document_image_understanding | n/a (text-only) | n/a | n/a | n/a | n/a (no vision) | **pass 3/3 (only vision-capable model)** |
| compact_summarisation | pass 5.5s | pass 23.8s | pass 18.9s | pass 73.1s | pass 3/3 | pass 3/3 |
| independent_review | pass 2.6s | pass 10.6s | pass 19.7s | pass 49.8s | pass 3/3 | pass 3/3 |
| ros_log_test_interpretation (proxy) | pass 3.1s | pass 11.9s | pass 19.4s | pass 92.4s | pass 3/3 | pass 3/3 |

\* `gpt-oss:20b`'s `code_repair-01` failure is a corpus wording ambiguity
("return ONLY the corrected full contents of `park_lease_is_stale`"),
not necessarily a capability gap — the model returned only the function,
omitting the `Lease` class the test needs to import. Recorded as-is
(real result, not discarded) but flagged as a known corpus limitation
affecting this one data point; not repeated this pass since `gpt-oss:20b`
is an unaffected incumbent regardless of the outcome.

### Supplemental placement/VRAM measurement (one representative prompt per model, 8K context, same convention as P7)

| model | total size | VRAM resident | GPU % |
|---|---|---|---|
| qwen3:8b | 6.61GB | 6.61GB | 100% |
| gpt-oss:20b | 14.39GB | 9.12GB | 63.4% (partial CPU offload) |
| qwen3:30b | 19.69GB | 9.43GB | 47.9% (partial CPU offload) |
| qwen3.5:9b | 8.97GB | 8.97GB | 100% |
| gemma4:e4b | 3.23GB | 3.23GB | 100% |
| gemma4:12b | 8.07GB | 8.07GB | 100% |

## Alias vocabulary reconciliation

The strategy doc's candidate labels (`local-small`, `local-agent`,
`local-multimodal`, `local-code`, `local-strong`, `local-deep`,
`local-challenger`) and the live routing contract's aliases in
`config/models.yaml` (`local-fast`, `local-strong`, `code-fast`,
`code-strong`, `reasoning-strong`, `vision`, `embedding`, `reranker`) are
genuinely different vocabularies, as the LM1 contract flagged. Resolution:
**left the live aliases unchanged** (no rename/refactor, no second
permanent vocabulary) and recorded the correspondence directly in
`config/models.yaml`'s comments: `local-small -> local-fast`,
`local-agent`/`local-code -> code-fast`, `local-multimodal -> vision`,
`local-strong`/`local-deep -> local-strong`/`reasoning-strong`. No
migration is actually needed — the live vocabulary already accommodates
every LM1 candidate's role.

## Promotion decisions

**Zero binding changes applied.** Evidence-backed reasoning per alias:

- **local-fast** (incumbent `qwen3:8b`): stays. `qwen3:8b` passed 13/13
  applicable tasks, at or near the fastest of any model on almost every
  task. The one candidate that could plausibly beat it on latency,
  `gemma4:e4b`, isn't production-deployable (see blocker) and has a real,
  repeated correctness gap on `phd_scientific_reasoning` (1/3 pass) that
  `qwen3:8b` doesn't share — a same-provider promotion would be a
  regression on that task class even before the deployability blocker.
- **local-strong** (incumbent `gpt-oss:20b`): stays. `qwen3:30b` (already
  installed, screened as a baseline) is more CPU-offloaded (47.9% vs
  63.4% GPU-resident), slower on most tasks, and timed out on
  `long_context_retrieval@32K` where `gpt-oss:20b` at least returned an
  answer (albeit a wrong one). No material advantage either way.
- **code-fast** (incumbent `null`): stays null. `qwen3.5:9b` is the only
  production-deployable candidate and passed the one
  `bounded_code_repair` task, but is markedly slower than every other
  model on nearly every task (fully GPU-resident yet 51-92s on several
  tasks — plausibly heavy default "thinking" verbosity) and failed
  `fault_diagnosis`. One task is not enough breadth to defend a binding
  regardless. `gemma4:e4b` passed `bounded_code_repair` 3/3 with
  excellent latency (6.9s) and would be the stronger real candidate, but
  is blocked by the same production-deployability gap.
- **vision** (incumbent `null`): stays null, **despite** `gemma4:12b`
  being the strongest evidence-backed result in this whole pass — the
  only vision-capable local model evaluated, and it passed its one
  vision task 3/3 while also passing 11/13 of the text tasks 3/3 (its
  repeatable weaknesses: `bounded_code_repair` 0/3,
  `phd_scientific_reasoning` 0/3). Not bound because it cannot actually
  be reached by production `execute_local` yet. This is the single most
  actionable pending decision once the Ollama blocker clears.
- **reasoning-strong**: stays null — out of LM1's first-round scope, no
  candidate targeted it.

`config/models.yaml` was updated to: (1) correct `benchmark_candidates`,
which had drifted to a stale P7-era list unrelated to the actual
2026-08-20 strategy doc's second-round shortlist — replaced with
`Qwen3.6-35B-A3B`/`Nemotron-3.5-Lightning-30B-A3B`/`Qwen3.8-27B`, matching
the current research doc exactly (LM2 scope, not evaluated this pass);
(2) record `qwen3.5:9b`, `gemma4:e4b`, `gemma4:12b` under
`installed_candidates` with the deployability caveat inline. No alias
`binding:` line was changed. `config/routing.yaml`'s `quality_floors`
stays `null` — deliberately: a handful of models' binary pass/fail
results, even over 3 trials for the finalists, aren't enough breadth to
defend a numeric floor any future model would be judged against.

## Tests / live regression evidence

- New: `tests/test_local_model_benchmark.py`, 9/9 passing (corpus shape +
  deterministic scorers, no live model calls).
- Focused: every test file that calls `src.llm_core.llm_call` plus
  `tests/test_estate_router.py` — 150/150 passing after the `num_ctx`
  addition.
- Full suite: `python -m pytest -q --continue-on-collection-errors` ->
  **4893 passed, 4 skipped, 12 failed, 4 collection errors** (~118s). All
  12 failures + 4 errors match the exact pre-existing, independently-
  confirmed-unrelated set from
  `docs/aoteru-lab-execution-convergence-evidence.md` finding #8 (10x MCP
  SDK `list_tools` AttributeError across 3 servers + the already-documented
  `test_upload_handler_atomicity.py` filesystem-state flake, which that
  same prior evidence recorded as sometimes 1/2 sometimes 2/2 depending on
  state — here it was 2/2, within the previously-observed range). None of
  the 16 touched/failing paths overlap this pass's changed files
  (`core/database.py`, `src/llm_core.py`, `config/*.yaml`,
  `scripts/run_local_model_benchmark.py`, `evals/local_models/**`,
  `tests/test_local_model_benchmark.py`).
- Live e2e smoke, production Ollama, after all code changes:
  `run_task({"task_class": "lm1-live-smoke", "objective": "Reply with
  exactly the single word: pong", "requirements": {"capabilities":
  ["local-fast"]}})` -> `route: local/qwen3:8b`, `executed: true`,
  `output: "pong"`, `latency_ms: 4090`, `deterministic_gate: pass`.
  `systemctl is-active odysseus-aoteru-lab.service` -> `active`;
  `GET /api/health` -> `200`; `127.0.0.1:7001` only, zero `0.0.0.0:7001`
  listeners.

## Deferred / LM2

- Gemma 4 E4B / Gemma 4 12B promotion, pending the Ollama-version operator
  action above. Evidence already collected (3 trials each) so LM2 can
  promote on this pass's evidence alone once the blocker clears, without
  re-benchmarking.
- `code-fast`/`local-strong` deserve a wider task corpus (more than one
  `bounded_code_repair` task) before any binding, evidence-backed or not.
- Second-round candidates (`Qwen3.6-35B-A3B`, `Nemotron-3.5-Lightning-
  30B-A3B`, `Qwen3.8-27B`) — deliberately not evaluated, out of LM1 scope.
- `llama.cpp`/`llama-bench` supplemental instrumentation from the strategy
  doc — not built this pass; the Ollama-native placement measurement above
  covered the same "processor placement and context" requirement at much
  lower implementation cost for LM1's bounded scope.
- `gpt-oss:20b`'s `code_repair-01` corpus-wording ambiguity — worth a
  corpus wording fix in LM2, not urgent (it doesn't affect any promotion
  decision this pass).

## Audit-repair pass (2026-08-21,
docs/aoteru-lm1-audit-repair-lm2-design.agent-task.md)

A follow-up audit found four real validity/reproducibility gaps in the LM1
pass above. All four confirmed and repaired; LM1 is now closed.

- **A1 — production context sizing.** Confirmed:
  `src.estate_router.execute_local()` still called `llm_call()` without
  `num_ctx`, so every real routed task (not just this harness before its
  own fix) requested a model's full advertised window regardless of
  prompt size — see the correction note on the "real production bug"
  section above. Fixed by adding `src.model_context.select_bounded_context()`
  (the one canonical context-selection policy: smallest context bucket
  that covers the actual prompt + headroom, capped at the model's real
  window so long-context tasks are unaffected) and wiring it into
  `execute_local`. Live-verified: `run_task(local-fast)` against
  production Ollama now shows `context_length: 4096` in `ollama ps`
  for a short prompt on `qwen3:8b` (advertised/known window far larger),
  where it previously requested the full window. 3 new focused tests
  (`tests/test_estate_router.py`), all passing.
- **A2 — benchmark-output reproducibility.** Confirmed:
  `scripts/run_local_model_benchmark.py` stripped `raw_output` from the
  JSONL export (correct) but never populated
  `BenchmarkResult.raw_output_pointer` (bug) — every one of this pass's
  140 raw model outputs was discarded after scoring, with no way to
  independently rescore or dispute a result afterward. Fixed by adding
  `write_artifact()`: an immutable, self-contained per-(run_id, model,
  task_id[, context_point]) JSON artefact under
  `evals/local_models/results/artifacts/` carrying the exact output, its
  SHA-256, and full corpus/source/model/runtime provenance; SQLite keeps
  only the pointer + hash (`raw_output_sha256`, new column, additive
  migration) via a new `raw_output_pointer`/`raw_output_sha256` pair on
  every future row. Re-running the same (run_id, task) is idempotent; a
  hash mismatch on an existing artefact raises rather than silently
  overwriting prior evidence. This pass's 140 historical rows (whose raw
  outputs were never captured, so cannot be reconstructed) are now
  explicitly labelled `raw_output_pointer = "output-unavailable"` rather
  than left ambiguously `null` — not re-run, per the audit task's
  instruction. 6 new focused tests (`tests/test_local_model_benchmark.py`)
  plus a live validation run (see A3) confirming the mechanism end-to-end.
- **A3 — estate corpus fidelity.** Confirmed: `phd_scientific_reasoning`
  and `ros_log_test_interpretation` used explicitly-labelled proxy content
  (this repo's own docs), not real `obsidian-PhD`/S2-E1 material, because
  both repos were genuinely unregistered (`config/repositories.yaml`
  `remote: null`) at LM1 time. GitHub read access to both
  (`tyecam1/obsidian-PhD`, `tyecam1/s2-e1-ros2-measurement-spine`) was
  available this pass. Replaced both fixtures in place with frozen,
  real-source excerpts and a rubric/atom defined before any candidate
  output was seen: `scientific_reasoning-01` now quotes the user's real
  PhD evidence-tier rubric and Claim C3 verbatim
  (`tyecam1/obsidian-PhD@731fcd8:01-research-plan/00-RC/evidence
  requirements.md#L2-L7,L56-L62`) and requires naming the three real
  evidence tiers; `ros_log_test-01` now quotes a real ROS 2 topic table
  and a real pytest unit test verbatim
  (`tyecam1/s2-e1-ros2-measurement-spine@6c4efdf:docs/ros2_measurement_
  graph.md#L9-L13;tests/test_manifest_validation.py#L59-L69`) and requires
  exact topic/message-type/error-substring recall. Both repos read-only,
  neither mutated. Validation run against the `local-fast` incumbent
  (`qwen3:8b`, run_id `lm1-a3-validation-1`): both pass, with genuinely
  on-topic answers (verified by reading the stored output artefacts, not
  just the pass/fail gate). Old proxy results for these two tasks are not
  reinterpreted as evidence for the new, stronger task classes — the prior
  screening pass's `phd_scientific_reasoning`/`ros_log_test_interpretation`
  rows remain proxy-only evidence for whatever they actually measured.
- **A4 — inventory semantics.** Confirmed: `config/models.yaml`'s
  `installed_candidates` mixed two different states — models genuinely
  pullable/runnable on production Ollama, and Gemma 4 E4B/12B, which were
  only ever run through a temporary, already-torn-down second Ollama
  instance and cannot currently be routed to at all — under one list
  literally named "installed", disambiguated only by an inline comment.
  No code was found reading this field (`src.estate_router.resolve_alias`
  reads only `capabilities:`), so the fix is config-only: each entry is
  now `{model, state, note?}` with `state` one of `production-installed`
  / `benchmark-only` / `candidate` / `unavailable`, reusing the existing
  list-of-dicts registry shape rather than adding a parallel registry.
  Gemma 4 E4B/12B are now explicitly `state: benchmark-only`.

Verification after all four repairs: focused tests for every touched file
pass; full suite `python -m pytest -q --continue-on-collection-errors` ->
**4901 passed, 4 skipped, 11 failed, 4 collection errors (118s)** — the
same pre-existing, independently-confirmed-unrelated failure set as
before this pass (10x MCP SDK `list_tools` AttributeError across 3
servers + the already-documented `test_upload_handler_atomicity.py`
filesystem-state flake); none of the 15 failing/erroring test paths
overlap this pass's changed files. Live e2e smoke, production Ollama,
after all repairs: `run_task({"task_class": "lm1-a5-closure-smoke",
"objective": "Reply with exactly the single word: pong", "requirements":
{"capabilities": ["local-fast"]}})` -> `executed: true`, `output: "pong"`,
`latency_ms: 2610`, `deterministic_gate: pass`.
`systemctl is-active odysseus-aoteru-lab.service` -> `active`;
`GET /api/health` -> `200`; `127.0.0.1:7001`/`127.0.0.1:11434` only, zero
`0.0.0.0` listeners.

**LM1 is closed as of this audit-repair pass.** The full LM1 benchmark
matrix was not re-run: none of the four repairs invalidate a promotion
decision made above (the zero-binding-changes conclusion stands; A1's
context-sizing fix changes production `execute_local` behaviour going
forward but does not change which model wins any task-class comparison
recorded above, since the harness itself already passed explicit
`context_point` values per task before this repair).

## Final HEAD

Committed to `dev`; see commit immediately following this file's addition
for the exact SHA (`git log -1`).
