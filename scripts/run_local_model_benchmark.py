"""LM1 estate benchmark runner
(docs/aoteru-local-model-benchmark-routing.agent-task.md).

Executes the frozen corpus in evals/local_models/corpus.json against one or
more local models, through the exact same provider-call layer production
routing uses (`src.llm_core.llm_call` — the function
`src.estate_router.execute_local` itself wraps), scores each task
deterministically, and persists results to `core.database.BenchmarkResult`
plus a machine-readable JSONL file under evals/local_models/results/.

This is deliberately the Odysseus-native harness the LM1 contract asks for
extended, not a new benchmark authority: it reuses the same execution
abstraction, the same SQLite database, and the same evals/ directory
convention `scripts/run_misumi_evals.py` already established.
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.database import SessionLocal, BenchmarkResult  # noqa: E402
from src.llm_core import llm_call  # noqa: E402

import httpx  # noqa: E402


def unload_all(base_url: str) -> None:
    """Force-evict every model currently resident on `base_url`'s Ollama
    instance (`keep_alive: 0`). The single physical RTX 3080 is shared
    between production Ollama (11434) and this pass's second, user-local
    instance (11435, gemma4 candidates only) — without an explicit unload
    between models, a still-resident model on either instance starves the
    other of VRAM (observed live this pass: a lingering qwen3:30b caused
    every following candidate call, on both instances, to fail with a CUDA
    out-of-memory error)."""
    try:
        resp = httpx.get(f"{base_url}/api/ps", timeout=10)
        resp.raise_for_status()
        for m in resp.json().get("models", []):
            try:
                httpx.post(f"{base_url}/api/generate", json={"model": m["name"], "keep_alive": 0}, timeout=30)
            except Exception:
                pass
    except Exception:
        pass

CORPUS_PATH = REPO_ROOT / "evals" / "local_models" / "corpus.json"
MANIFEST_PATH = REPO_ROOT / "evals" / "local_models" / "model_manifest.json"
RESULTS_DIR = REPO_ROOT / "evals" / "local_models" / "results"
ARTIFACTS_DIR = RESULTS_DIR / "artifacts"
FIXTURES_DIR = REPO_ROOT / "evals" / "local_models" / "fixtures"


def write_artifact(run_id: str, corpus_id: str, model_key: str, task: dict, model_cfg: dict, result: dict) -> tuple[str, str]:
    """Persist one execution's exact output as an immutable per-run artefact
    (LM1 audit-repair: `raw_output` was previously discarded after scoring —
    stripped from the JSONL export and never written to
    `BenchmarkResult.raw_output_pointer` — so no independent rescoring or
    dispute-resolution was possible after the fact).

    Returns (pointer, sha256) where ``pointer`` is a repo-relative path.
    The artefact is a small self-contained JSON document carrying enough
    corpus/source/model/runtime provenance to independently rescore the
    output without needing the SQLite row at all; SQLite only keeps the
    pointer + hash, not the transcript, per the task's "keep telemetry
    compact" requirement.

    Immutable: a pre-existing artefact for the same (run_id, model_key,
    task_id[, context_point]) is never silently overwritten. If the new
    output's hash disagrees with what's already on disk, that is a data
    integrity conflict and raises rather than corrupting prior evidence.
    """
    import hashlib

    output = result.get("raw_output") or ""
    sha256 = hashlib.sha256(output.encode("utf-8")).hexdigest()

    ctx = result.get("context_point")
    filename = f"{task['task_id']}__{ctx}.json" if ctx else f"{task['task_id']}.json"
    model_dir = ARTIFACTS_DIR / run_id / model_key
    model_dir.mkdir(parents=True, exist_ok=True)
    path = model_dir / filename

    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if existing.get("output_sha256") != sha256:
            raise RuntimeError(
                f"benchmark artefact integrity conflict at {path}: existing "
                f"sha256={existing.get('output_sha256')} != new sha256={sha256} "
                "(artefacts are immutable; use a new run_id for a genuine rerun)"
            )
        pointer = str(path.relative_to(REPO_ROOT))
        return pointer, sha256

    artifact = {
        "run_id": run_id,
        "task_id": task["task_id"],
        "task_class": task["task_class"],
        "corpus_id": corpus_id,
        "source_pointer": task.get("source_pointer"),
        "model_key": model_key,
        "concrete_model": model_cfg.get("concrete_model"),
        "upstream_repo": model_cfg.get("upstream_repo"),
        "upstream_revision": model_cfg.get("upstream_revision"),
        "artifact": model_cfg.get("artifact"),
        "quantization": model_cfg.get("quantization"),
        "runtime": model_cfg.get("runtime", "ollama"),
        "runtime_version": model_cfg.get("runtime_version"),
        "runtime_base_url": model_cfg.get("base_url"),
        "context_point": ctx,
        "status": result.get("status"),
        "score": result.get("score"),
        "output_sha256": sha256,
        "raw_output": output,
    }
    path.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    pointer = str(path.relative_to(REPO_ROOT))
    return pointer, sha256


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def extract_code_block(text: str) -> str:
    m = re.search(r"```(?:python)?\s*\n(.*?)```", text, re.DOTALL)
    return m.group(1) if m else text


def score_keyword_all(output: str, task: dict) -> tuple[bool, str]:
    low = output.lower()
    keywords = task["scoring"].get("keywords", [])
    missing = [k for k in keywords if k.lower() not in low]
    ok = not missing
    ka = task["scoring"].get("keyword_any")
    if ok and ka:
        ok = any(k.lower() in low for k in ka)
        if not ok:
            return False, f"none of keyword_any present: {ka}"
    return ok, ("pass" if ok else f"missing keywords: {missing}")


def score_json_tool_call(output: str, task: dict) -> tuple[bool, str]:
    s = task["scoring"]
    text = output.strip()
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return False, "no JSON object found in output"
    try:
        obj = json.loads(m.group(0))
    except Exception as e:
        return False, f"invalid JSON: {e}"
    if obj.get("name") != s["expected_name"]:
        return False, f"wrong tool name: {obj.get('name')!r}"
    args = obj.get("arguments") or {}
    for k, v in s.get("required_arguments", {}).items():
        if args.get(k) != v:
            return False, f"required arg {k!r} mismatch: {args.get(k)!r} != {v!r}"
    return True, "pass"


def score_json_schema(output: str, task: dict) -> tuple[bool, str]:
    s = task["scoring"]
    text = output.strip()
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return False, "no JSON object found in output"
    try:
        obj = json.loads(m.group(0))
    except Exception as e:
        return False, f"invalid JSON: {e}"
    for key, spec in s["required_keys"].items():
        if key not in obj:
            return False, f"missing key: {key}"
        val = obj[key]
        if spec == "str" and not isinstance(val, str):
            return False, f"{key} not a string"
        if spec == "bool" and not isinstance(val, bool):
            return False, f"{key} not a bool"
        if isinstance(spec, list) and val not in spec:
            return False, f"{key}={val!r} not in {spec}"
    for key, expected in (s.get("expected_values") or {}).items():
        if obj.get(key) != expected:
            return False, f"{key}={obj.get(key)!r} expected {expected!r}"
    return True, "pass"


def score_summary(output: str, task: dict) -> tuple[bool, str]:
    s = task["scoring"]
    words = output.strip().split()
    if len(words) > s["max_words"]:
        return False, f"{len(words)} words > max {s['max_words']}"
    return score_keyword_all(output, task)


def score_pytest_fixture(output: str, task: dict) -> tuple[bool, str]:
    s = task["scoring"]
    src_dir = REPO_ROOT / s["fixture_dir"]
    code = extract_code_block(output).strip()
    if not code:
        return False, "no code extracted from output"
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        shutil.copytree(src_dir, tmp, dirs_exist_ok=True)
        (tmp / s["target_file"]).write_text(code, encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", s["test_file"]],
            cwd=tmp, capture_output=True, text=True, timeout=60,
        )
        ok = proc.returncode == 0
        tail = (proc.stdout or "")[-400:]
        return ok, ("pass" if ok else f"pytest failed: {tail}")


SCORERS = {
    "keyword_all": score_keyword_all,
    "json_tool_call": score_json_tool_call,
    "json_schema": score_json_schema,
    "summary": score_summary,
    "pytest_fixture": score_pytest_fixture,
}


def build_messages(task: dict, haystack_override: str | None = None) -> list[dict]:
    prompt = task["prompt"]
    if "__LONG_CONTEXT_HAYSTACK__" in prompt:
        prompt = prompt.replace("__LONG_CONTEXT_HAYSTACK__", haystack_override or "")
    if task.get("requires_vision"):
        img_path = REPO_ROOT / task["image_path"]
        b64 = base64.b64encode(img_path.read_bytes()).decode("ascii")
        return [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
            ],
        }]
    return [{"role": "user", "content": prompt}]


def run_one(model_cfg: dict, task: dict, run_id: str, corpus_id: str,
            haystack_override: str | None = None, context_point: int | None = None) -> dict:
    if task.get("requires_vision") and not model_cfg.get("vision"):
        return {
            "task_id": task["task_id"], "status": "na", "reason": "model has no vision capability",
            "score": "na", "wall_time_ms": None,
        }
    messages = build_messages(task, haystack_override)
    ctx = context_point or task.get("context_point")
    started = time.monotonic()
    try:
        output = llm_call(model_cfg["base_url"], model_cfg["concrete_model"], messages, timeout=180,
                           num_ctx=ctx)
        error = None
    except Exception as e:
        output = ""
        error = str(e)
    wall_ms = int((time.monotonic() - started) * 1000)

    if error:
        return {
            "task_id": task["task_id"], "status": "error", "reason": error,
            "score": "error", "wall_time_ms": wall_ms, "raw_output": "",
        }

    scorer = SCORERS[task["scoring"]["type"]]
    ok, reason = scorer(output, task)
    return {
        "task_id": task["task_id"], "status": "pass" if ok else "fail", "reason": reason,
        "score": "pass" if ok else "fail", "wall_time_ms": wall_ms, "raw_output": output,
        "context_point": context_point or task.get("context_point"),
    }


def persist(run_id: str, corpus_id: str, task: dict, model_key: str, model_cfg: dict, result: dict):
    raw_output_pointer, raw_output_sha256 = write_artifact(run_id, corpus_id, model_key, task, model_cfg, result)
    db = SessionLocal()
    try:
        row = BenchmarkResult(
            id=str(uuid.uuid4()),
            run_id=run_id,
            corpus_id=corpus_id,
            task_id=result["task_id"],
            task_class=task["task_class"],
            source_pointer=task.get("source_pointer"),
            concrete_model=model_cfg["concrete_model"],
            upstream_repo=model_cfg.get("upstream_repo"),
            upstream_revision=model_cfg.get("upstream_revision"),
            artifact=model_cfg.get("artifact"),
            quantization=model_cfg.get("quantization"),
            runtime=model_cfg.get("runtime", "ollama"),
            runtime_version=model_cfg.get("runtime_version"),
            runtime_base_url=model_cfg.get("base_url"),
            context_point=result.get("context_point"),
            wall_time_ms=result.get("wall_time_ms"),
            score=result.get("score"),
            status=result["status"],
            reason=(result.get("reason") or "")[:2000],
            raw_output_pointer=raw_output_pointer,
            raw_output_sha256=raw_output_sha256,
        )
        db.add(row)
        db.commit()
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", required=True, help="comma-separated model_manifest.json keys")
    parser.add_argument("--tasks", default=None, help="comma-separated task_ids to filter, default all")
    parser.add_argument("--run-id", default=None)
    args = parser.parse_args()

    corpus = load_json(CORPUS_PATH)
    manifest = load_json(MANIFEST_PATH)["models"]
    run_id = args.run_id or f"lm1-{uuid.uuid4().hex[:10]}"
    corpus_id = corpus["corpus_id"]

    model_keys = [m.strip() for m in args.models.split(",") if m.strip()]
    task_filter = set(t.strip() for t in args.tasks.split(",")) if args.tasks else None

    haystack_8k = (FIXTURES_DIR / "long_context_01_8k.txt").read_text()
    haystack_32k = (FIXTURES_DIR / "long_context_01_32k.txt").read_text()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / f"{run_id}.jsonl"
    summary = {}

    with out_path.open("w", encoding="utf-8") as out_f:
        for model_key in model_keys:
            if model_key not in manifest:
                print(f"SKIP unknown model key: {model_key}")
                continue
            model_cfg = manifest[model_key]
            unload_all("http://127.0.0.1:11434")
            unload_all("http://127.0.0.1:11435")
            summary[model_key] = {"pass": 0, "fail": 0, "na": 0, "error": 0}
            for task in corpus["tasks"]:
                if task_filter and task["task_id"] not in task_filter:
                    continue
                if task["task_id"] == "long_context-01":
                    for cp, haystack in ((8000, haystack_8k), (32000, haystack_32k)):
                        result = run_one(model_cfg, task, run_id, corpus_id, haystack, cp)
                        persist(run_id, corpus_id, task, model_key, model_cfg, result)
                        record = {"run_id": run_id, "model": model_key, **result}
                        record.pop("raw_output", None)
                        out_f.write(json.dumps(record) + "\n")
                        summary[model_key][result["status"]] = summary[model_key].get(result["status"], 0) + 1
                        print(f"[{model_key}] {task['task_id']}@{cp} -> {result['status']} ({result['reason'][:80]})")
                    continue
                result = run_one(model_cfg, task, run_id, corpus_id)
                persist(run_id, corpus_id, task, model_key, model_cfg, result)
                record = {"run_id": run_id, "model": model_key, **result}
                record.pop("raw_output", None)
                out_f.write(json.dumps(record) + "\n")
                summary[model_key][result["status"]] = summary[model_key].get(result["status"], 0) + 1
                print(f"[{model_key}] {task['task_id']} -> {result['status']} ({str(result['reason'])[:80]})")

    unload_all("http://127.0.0.1:11434")
    unload_all("http://127.0.0.1:11435")

    print("\n=== summary ===")
    print(f"run_id={run_id}")
    for model_key, counts in summary.items():
        print(f"{model_key}: {counts}")


if __name__ == "__main__":
    main()
