---
title: LM4 — production canary + adaptive routing evidence
status: closed
as_of: 2026-08-23
source_task: docs/aoteru-lm4-production-canary-adaptive-routing.agent-task.md
---

# LM4 evidence

## Mechanism added

- `core.database.BenchmarkResult`: 6 additive nullable columns
  (`model_alias`, `run_kind`, `routing_decision_id`, `escalated`,
  `escalation_reason`, `human_correction_observed`), applied via the
  repo's existing SQLite in-code migration convention
  (`_migrate_add_benchmark_canary_columns`, same pattern as LM1's
  `raw_output_sha256` migration). `run_kind IS NULL` reads as "benchmark"
  (all pre-LM4 LM1/LM2 rows); `run_kind="canary"` marks a row as a real
  production-route exercise, distinguishing it from an offline candidate
  sweep without a second table.
- `scripts/run_lm4_production_canary.py`: new runner that exercises the
  five live `config/models.yaml` aliases through the **real production
  route** — text tasks call `src.estate_router.run_task()` directly (the
  actual routing+execution+`RoutingDecision`-telemetry path); the one
  vision task calls `resolve_route()` (same real routing decision) then
  `src.llm_core.llm_call` directly (the same provider-call layer
  `execute_local()` wraps, needed only because `run_task()`'s objective
  is a plain string and can't carry multimodal message content). Each
  `BenchmarkResult` row is linked to its real `RoutingDecision` row via
  `routing_decision_id`, and that `RoutingDecision` row's
  `verification_outcome` is updated with the task-specific deterministic
  score (upgrading `run_task()`'s own generic "non-empty output" gate).
  No parallel telemetry authority was created; both existing tables were
  extended as the task doc required.
- Canary pack: the frozen LM1 corpus (`evals/local_models/corpus.json`,
  unchanged) — reused directly as the "small representative canary pack"
  the task doc explicitly permits, since it already covers every required
  task class. No new corpus was manufactured.

## Coverage

14 distinct task/alias exercises + 1 extra recon-01 smoke test = 15 real
production-route calls, chosen so every task-class the task doc requires
is covered by the alias most relevant to routing for it (not every alias
through every task):

| alias | concrete model | tasks | result |
|---|---|---|---|
| local-fast | qwen3:8b | repo_reconnaissance x2, compact_summarisation | 3/3 pass |
| local-strong | gpt-oss:20b | fault_diagnosis, independent_review, long_context@32K | 3/3 pass |
| code-fast | ornith:9b | bounded_code_repair, tool_function_call_correctness, strict_json_schema_output | 3/3 pass |
| reasoning-strong | nemotron-3.5-lightning:30b-a3b | phd_scientific_reasoning, ros_log_test_interpretation | 2/2 pass |
| vision | gemma4:12b | document_image_understanding x3 independent trials | 3/3 pass |

15/15 pass, 0 fail, 0 error, 0 repeats needed (repeat-on-failure rule
never triggered). Main run `run_id=lm4-canary-18419152fb` (12 rows) +
2 vision re-trials run separately after the cache fix below
(`run_id=lm4-canary-8001bbd0ac`) + 1 earlier smoke-test row
(`lm4-canary-47002a9b4a`, recon-01, also pass) —
`evals/local_models/results/lm4-canary-18419152fb.jsonl` (updated to
list the corrected vision trials) and
`evals/local_models/results/artifacts/lm4-canary-*/` hold the exact
outputs/hashes across all three run_ids.

**Vision caution note (from the task doc):** the bound `gemma4:12b` is
the Ollama-library artifact, distinct from LM2's QAT-GGUF-direct
evidence, and LM3 bound it on a single equivalence trial. `llm_call`
memoizes identical (url, model, messages, temperature, max_tokens)
requests (`src.llm_core._response_cache`) — real production behaviour,
not a test artefact — so the first attempt at 3 "independent" vision
trials silently degenerated into one live call plus two 0ms cache
echoes. Caught by inspecting `wall_time_ms`, discarded (2 stale
`BenchmarkResult`/`RoutingDecision` rows deleted), and re-run with a
scoring-irrelevant per-trial nonce appended to the prompt so all 3 were
genuine independent inferences (7993ms, 2118ms, 3670ms — real variance).
Combined with LM3's own equivalence check, the bound artifact now has
4/4 independent production-path passes, not 1.

## Per-alias disposition

- **local-fast (qwen3:8b) — retain.** No regression vs LM1 evidence.
- **local-strong (gpt-oss:20b) — retain.** No regression; also cleared
  the one required longer-context task (32K haystack, needle recall
  correct at 45.6s).
- **code-fast (ornith:9b) — retain.** Matches LM2's 39/39 perfect record;
  first production-path exercise beyond LM3's single code_repair-01
  smoke.
- **reasoning-strong (nemotron-3.5-lightning:30b-a3b) — retain.** Matches
  LM2's 36/39 evidence; first production-path test of the ROS/log
  interpretation task class specifically (LM3's smoke only covered
  scientific reasoning).
- **vision (gemma4:12b) — retain, caution closed.** 4/4 independent
  production-path passes now on the bound artifact itself (see above) —
  no longer resting on LM3's single trial, without conflating it with
  LM2's separate llama.cpp-artifact evidence.
- **code-strong — insufficient evidence, unchanged (null).** No LM4
  production traffic or canary evidence targets this alias; no gap was
  observed in any exercised task class that `code-fast`,
  `local-strong`, or escalation couldn't have handled adequately. Per
  the task doc, not filled merely because it's null.

## Routing/escalation changes

None. Every live alias retained its current binding; no fallback,
demotion, or new escalation rule was justified by this evidence.

## Tests / regression / exposure evidence

- `pytest tests/test_estate_router.py tests/test_database_utcnow.py
  tests/test_model_context.py tests/test_local_model_benchmark.py
  tests/test_api_call_integration_routing.py tests/test_llm_core_ollama.py`
  — 104 passed, 0 failed (the one full relevant suite: every test file
  touching routing, the DB schema just changed, model-context bounding,
  the benchmark harness reused this pass, and the Ollama provider-call
  layer).
- Production Ollama: `systemctl is-active ollama` → active;
  `ss -tlnp | grep 11434` → `127.0.0.1:11434` only (loopback-only,
  unchanged from LM3).
- All five live aliases re-resolved live via
  `src.estate_router.resolve_alias()` immediately after the canary run;
  `code-strong` correctly still resolves `resolved: False`.
- `git rev-parse HEAD origin/dev` matched before this pass's commit
  (`d685fde`, the LM4 task-doc commit).

## Follow-up

None justified. No regression, no evidence-backed gap, no renewed
discovery need surfaced. Local-model programme (LM1→LM2→LM3→LM4) is
closed pending real production traffic accumulating enough
`RoutingDecision` volume for the contract's full replay/shadow
evaluator — that is future work, not a defect found here.
