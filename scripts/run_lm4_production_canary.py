"""LM4 production canary runner
(docs/aoteru-lm4-production-canary-adaptive-routing.agent-task.md).

Exercises the *live* config/models.yaml capability aliases through the
*real* production routing path (`src.estate_router.resolve_route` /
`run_task`, against production Ollama on 127.0.0.1:11434) rather than a
second offline benchmark authority. Reuses the frozen LM1 corpus
(evals/local_models/corpus.json) as the "small representative canary
pack" the task explicitly permits instead of manufacturing a new one, and
reuses `scripts/run_local_model_benchmark.py`'s scorers/artifact writer
so canary evidence stays in the same `BenchmarkResult` shape as LM1/LM2 —
just tagged `run_kind="canary"` with a `model_alias` and
`routing_decision_id` linking each row back to the real
`RoutingDecision` row `resolve_route()` already wrote for that call.

Text tasks go through `estate_router.run_task()` directly (the actual
production call+telemetry path). The one vision task needs multimodal
message content `run_task()`'s plain-string objective can't carry, so
that leg calls `resolve_route()` (still the real routing decision) then
`src.llm_core.llm_call` directly — the same provider-call layer
`execute_local()` wraps — and updates the same `RoutingDecision` row
`resolve_route()` already created, rather than inventing a second
telemetry write path.
"""
from __future__ import annotations

import json
import sys
import time
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.database import SessionLocal, BenchmarkResult, RoutingDecision  # noqa: E402
from src.estate_router import run_task, resolve_route, _update_decision_outcome, _OLLAMA_BASE  # noqa: E402
from scripts.run_local_model_benchmark import (  # noqa: E402
    SCORERS, write_artifact, load_json, CORPUS_PATH, FIXTURES_DIR, RESULTS_DIR,
)

# alias -> [task_id, ...]. Deliberately partial coverage per alias (task
# doc: "do not force every alias through every task") — chosen so every
# required minimum task class (routine repo recon, bounded code repair,
# fault/log diagnosis, strict schema/tool-call, scientific/PhD reasoning,
# ROS/test interpretation, compact summarisation, vision, one
# longer-context task) is covered by the alias it's actually most
# relevant to routing for.
CANARY_PLAN: dict[str, list[str]] = {
    "local-fast": ["recon-01", "recon-02", "summarisation-01"],
    "local-strong": ["fault_diagnosis-01", "independent_review-01", "long_context-01"],
    "code-fast": ["code_repair-01", "tool_call-01", "json_schema-01"],
    "reasoning-strong": ["scientific_reasoning-01", "ros_log_test-01"],
    # vision runs doc_image-01 three times (not once) per the task doc's
    # explicit "Vision caution": the bound Ollama-library gemma4:12b
    # artifact differs from LM2's QAT-GGUF-direct evidence, so it earns
    # modestly broader canary coverage rather than being treated as
    # equally well established on a single trial.
    "vision": ["doc_image-01", "doc_image-01", "doc_image-01"],
}

RUN_ID = f"lm4-canary-{uuid.uuid4().hex[:10]}"


def _load_haystack(context_point: int | None) -> str | None:
    if context_point == 32000:
        return (FIXTURES_DIR / "long_context_01_32k.txt").read_text()
    if context_point == 8000:
        return (FIXTURES_DIR / "long_context_01_8k.txt").read_text()
    return None


def _objective_for(task: dict) -> str:
    prompt = task["prompt"]
    if "__LONG_CONTEXT_HAYSTACK__" in prompt:
        haystack = _load_haystack(task.get("context_point"))
        prompt = prompt.replace("__LONG_CONTEXT_HAYSTACK__", haystack or "")
    return prompt


def _score(task: dict, output: str) -> tuple[bool, str]:
    scorer = SCORERS[task["scoring"]["type"]]
    return scorer(output, task)


def _persist(alias: str, task: dict, corpus_id: str, concrete_model: str,
             routing_decision_id: str, result: dict, retries: int) -> None:
    model_cfg = {
        "concrete_model": concrete_model,
        "runtime": "ollama",
        "runtime_version": "0.32.15 (production)",
        "base_url": _OLLAMA_BASE,
    }
    raw_output_pointer, raw_output_sha256 = write_artifact(RUN_ID, corpus_id, alias, task, model_cfg, result)
    db = SessionLocal()
    try:
        row = BenchmarkResult(
            id=str(uuid.uuid4()),
            run_id=RUN_ID,
            corpus_id=corpus_id,
            task_id=result["task_id"],
            task_class=task["task_class"],
            source_pointer=task.get("source_pointer"),
            concrete_model=concrete_model,
            runtime="ollama",
            runtime_version="0.32.15 (production)",
            runtime_base_url=_OLLAMA_BASE,
            context_point=result.get("context_point"),
            wall_time_ms=result.get("wall_time_ms"),
            score=result.get("score"),
            retries=retries,
            status=result["status"],
            reason=(result.get("reason") or "")[:2000],
            raw_output_pointer=raw_output_pointer,
            raw_output_sha256=raw_output_sha256,
            model_alias=alias,
            run_kind="canary",
            routing_decision_id=routing_decision_id,
            escalated=result["status"] != "pass",
            escalation_reason=None if result["status"] == "pass" else "quality_floor_not_met",
        )
        db.add(row)
        db.commit()
    finally:
        db.close()


def _update_routing_verification(decision_id: str, verification_outcome: str) -> None:
    if decision_id.startswith("decision-unrecorded-"):
        return
    db = SessionLocal()
    try:
        row = db.query(RoutingDecision).filter(RoutingDecision.id == decision_id).first()
        if row is not None:
            row.verification_outcome = verification_outcome
        db.commit()
    finally:
        db.close()


def run_text_task(alias: str, task: dict, corpus_id: str, retries: int = 0) -> dict:
    envelope = {
        "task_class": task["task_class"],
        "objective": _objective_for(task),
        "complexity": "routine",
        "consequence": "low",
        "requirements": {"capabilities": [alias]},
    }
    route = run_task(envelope)
    decision_id = route.get("decision_id", "")
    concrete_model = (route.get("route") or {}).get("concrete_model")

    if not route.get("executed"):
        result = {
            "task_id": task["task_id"], "status": "error",
            "reason": f"not executed: {route.get('error') or route.get('execution_error') or 'route not resolved'}",
            "score": "error", "wall_time_ms": None, "context_point": task.get("context_point"),
        }
        print(f"[{alias}] {task['task_id']} -> NOT EXECUTED ({result['reason'][:100]})")
        _persist(alias, task, corpus_id, concrete_model or "unresolved", decision_id, result, retries)
        return result

    execution = route["execution"]
    output = execution.get("output") or ""
    wall_ms = execution.get("latency_ms")
    if not execution.get("ok"):
        ok, reason = False, f"execution failed: {execution.get('error')}"
    else:
        ok, reason = _score(task, output)

    result = {
        "task_id": task["task_id"], "status": "pass" if ok else "fail", "reason": reason,
        "score": "pass" if ok else "fail", "wall_time_ms": wall_ms,
        "context_point": task.get("context_point"), "raw_output": output,
    }
    _update_routing_verification(decision_id, "pass" if ok else "fail")
    _persist(alias, task, corpus_id, concrete_model, decision_id, result, retries)
    print(f"[{alias}] {task['task_id']} -> {result['status']} ({str(reason)[:100]})")
    return result


def run_vision_task(alias: str, task: dict, corpus_id: str, retries: int = 0, trial: int = 1) -> dict:
    import base64
    from src.llm_core import llm_call
    from src.model_context import select_bounded_context

    route = resolve_route({
        "task_class": task["task_class"],
        "complexity": "routine", "consequence": "low",
        "requirements": {"capabilities": [alias]},
    })
    decision_id = route.get("decision_id", "")
    concrete_model = (route.get("route") or {}).get("concrete_model")
    if not route.get("ok") or not concrete_model:
        result = {
            "task_id": task["task_id"], "status": "error",
            "reason": f"route not resolved: {route.get('error')}",
            "score": "error", "wall_time_ms": None, "context_point": task.get("context_point"),
        }
        print(f"[{alias}] {task['task_id']} -> NOT EXECUTED ({result['reason'][:100]})")
        _persist(alias, task, corpus_id, concrete_model or "unresolved", decision_id, result, retries)
        return result

    img_path = REPO_ROOT / task["image_path"]
    b64 = base64.b64encode(img_path.read_bytes()).decode("ascii")
    # src.llm_core.llm_call memoizes identical (url, model, messages, temp,
    # max_tokens) requests (_response_cache) — a real production behaviour,
    # not a test artefact, but it means repeat trials of the *identical*
    # prompt would silently degenerate into "run once, report thrice".
    # A trial-number nonce appended to the (scoring-irrelevant) prompt text
    # busts that cache key so each trial is a genuine independent
    # inference — needed here specifically because the "Vision caution"
    # section asks for real repeat-trial coverage, not a cached echo.
    prompt = task["prompt"] if trial == 1 else f"{task['prompt']} (independent trial {trial}/3)"
    messages = [{
        "role": "user",
        "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
        ],
    }]
    num_ctx = select_bounded_context(_OLLAMA_BASE, concrete_model, messages)
    started = time.monotonic()
    try:
        output = llm_call(_OLLAMA_BASE, concrete_model, messages, timeout=90, num_ctx=num_ctx)
        error = None
    except Exception as e:
        output, error = "", str(e)
    wall_ms = int((time.monotonic() - started) * 1000)

    if error:
        ok, reason = False, error
    else:
        ok, reason = _score(task, output)

    result = {
        "task_id": task["task_id"], "status": "pass" if ok else "fail", "reason": reason,
        "score": "pass" if ok else "fail", "wall_time_ms": wall_ms,
        "context_point": task.get("context_point"), "raw_output": output,
    }
    _update_decision_outcome(
        decision_id, status="complete" if ok else "failed",
        deterministic_gate="pass" if ok else "fail",
        latency_ms=wall_ms, escalation_reason=None if ok else "quality_floor_not_met",
    )
    _update_routing_verification(decision_id, "pass" if ok else "fail")
    _persist(alias, task, corpus_id, concrete_model, decision_id, result, retries)
    print(f"[{alias}] {task['task_id']} -> {result['status']} ({str(reason)[:100]})")
    return result


def main():
    corpus = load_json(CORPUS_PATH)
    corpus_id = corpus["corpus_id"]
    tasks_by_id = {t["task_id"]: t for t in corpus["tasks"]}

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / f"{RUN_ID}.jsonl"
    summary: dict[str, dict[str, int]] = {}

    with out_path.open("w", encoding="utf-8") as out_f:
        for alias, task_ids in CANARY_PLAN.items():
            summary[alias] = {"pass": 0, "fail": 0, "error": 0}
            for i, task_id in enumerate(task_ids):
                task = dict(tasks_by_id[task_id])
                # vision runs the SAME task 3x by design (trial repeats for
                # broader coverage); every other alias/task pair is unique.
                if alias == "vision":
                    trial = i + 1
                    if trial > 1:
                        task["task_id"] = f"{task['task_id']}-trial{trial}"
                    result = run_vision_task(alias, task, corpus_id, trial=trial)
                else:
                    result = run_text_task(alias, task, corpus_id)
                    # Repeat rule: a first-pass failure/error gets exactly one
                    # repeat to distinguish noise from a real regression —
                    # not swept further (task doc's own "enough to
                    # distinguish noise" bound).
                    if result["status"] != "pass":
                        print(f"  -> repeating {alias}/{task_id} once (first pass was {result['status']})")
                        result = run_text_task(alias, task, corpus_id, retries=1)
                summary[alias][result["status"]] = summary[alias].get(result["status"], 0) + 1
                record = {"run_id": RUN_ID, "alias": alias, **{k: v for k, v in result.items() if k != "raw_output"}}
                out_f.write(json.dumps(record) + "\n")

    print("\n=== LM4 canary summary ===")
    print(f"run_id={RUN_ID}")
    for alias, counts in summary.items():
        print(f"{alias}: {counts}")


if __name__ == "__main__":
    main()
