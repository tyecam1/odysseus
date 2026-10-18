"""Household GPU contention as an up-front routing/admission signal.

Context: ``docs/aoteru-multihost-execution-evidence.md`` (Stage 8). Home is a shared household gaming desktop.
While a game held about 92% of the GPU, routed ``local-inference`` was still admitted and then timed out after
120 s (0 pass / 3 fail), which reads like a model failure but is an admission failure. The existing
``gpu_yield`` signal (``estate_router.experiment_priority_active``) cannot see this: it reads per-process memory
from ``nvidia-smi --query-compute-apps``, and on Windows (WDDM) that column is ``[N/A]`` for every process.

This module extends that one health signal; it adds no router, scheduler, lease or store.

* The **worker** reports raw readings only (``sample_gpu``): utilisation and memory from
  ``nvidia-smi --query-gpu``, which works on Windows. The worker is spawned per call, so it holds no state and
  "sustained" is judged from several samples taken inside one call.
* The **router/canary** classify (``classify_gpu_load``) with a per-host threshold from ``config/estate.yaml``
  (``worker.gpu_admission``). A host with no such block is untouched (state ``disabled``).
* Load that the host's own in-flight estate executions explain is never "household contention".
* A missing, unreadable or stale reading is ``unknown``, never ``free``. Admission is observation only: nothing
  here touches, signals or stops another process.
"""

from __future__ import annotations

import subprocess
import time
from datetime import datetime, timezone
from typing import Callable, Optional

NVIDIA_SMI_QUERY = [
    "nvidia-smi",
    "--query-gpu=utilization.gpu,memory.used,memory.total",
    "--format=csv,noheader,nounits",
]
DEFAULT_SAMPLES = 3
DEFAULT_INTERVAL_S = 0.4
DEFAULT_BUSY_UTIL_PCT = 60.0
DEFAULT_MAX_READING_AGE_S = 60.0


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_gpu_query(text: str) -> list[Optional[dict]]:
    """One entry per output line, in GPU index order. A line whose fields are not all numbers
    (``[N/A]``, ``[Not Supported]``, ``[Unknown Error]``) yields ``None`` so that index positions are kept and
    an unreadable GPU is never mistaken for an idle one."""
    gpus: list[Optional[dict]] = []
    for line in (text or "").splitlines():
        if not line.strip():
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) != 3:
            gpus.append(None)
            continue
        try:
            util, used, total = (float(p) for p in parts)
        except ValueError:
            gpus.append(None)
            continue
        if total <= 0 or used < 0 or not 0 <= util <= 100:
            gpus.append(None)
            continue
        gpus.append({"util_pct": util, "mem_used_mib": used, "mem_total_mib": total})
    return gpus


def sample_gpu(
    *,
    samples: int = DEFAULT_SAMPLES,
    interval_s: float = DEFAULT_INTERVAL_S,
    run: Callable = subprocess.run,
    sleep: Callable[[float], None] = time.sleep,
) -> dict:
    """Take ``samples`` readings of GPU 0 (the device Ollama uses by default), ``interval_s`` apart.
    ``available`` is False when any reading is missing or unreadable, so a partial picture is never used."""
    taken: list[dict] = []
    error: Optional[str] = None
    for index in range(max(1, int(samples))):
        if index:
            sleep(interval_s)
        try:
            proc = run(NVIDIA_SMI_QUERY, capture_output=True, text=True, timeout=5)
        except Exception as exc:  # binary missing, permissions, timeout
            error = f"nvidia-smi unavailable: {exc.__class__.__name__}"
            break
        if proc.returncode != 0:
            error = f"nvidia-smi exited {proc.returncode}"
            break
        gpus = parse_gpu_query(proc.stdout)
        if not gpus or gpus[0] is None:
            error = "nvidia-smi returned no readable values for GPU 0"
            break
        taken.append(gpus[0])
    return {
        "available": error is None and bool(taken),
        "error": error,
        "samples": taken if error is None else [],
        "interval_s": interval_s,
        "taken_at": _utcnow(),
    }


def _age_s(taken_at: object, now: Optional[datetime]) -> Optional[float]:
    if not isinstance(taken_at, str):
        return None
    try:
        stamp = datetime.fromisoformat(taken_at)
    except ValueError:
        return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return ((now or datetime.now(timezone.utc)) - stamp).total_seconds()


def classify_gpu_load(
    reading: object,
    *,
    in_flight: object,
    config: object,
    now: Optional[datetime] = None,
) -> dict:
    """``state`` is one of ``disabled`` (host not configured), ``unknown`` (no usable reading; NOT free),
    ``free`` or ``busy``. Only ``busy`` withholds work."""
    if not isinstance(config, dict) or config.get("enabled") is False:
        return {"state": "disabled", "reason": "GPU admission is not configured for this host"}
    threshold = float(config.get("busy_util_pct", DEFAULT_BUSY_UTIL_PCT))
    min_free = config.get("min_free_vram_mib")
    max_age = float(config.get("max_reading_age_s", DEFAULT_MAX_READING_AGE_S))

    if not isinstance(reading, dict) or not reading.get("available") or not reading.get("samples"):
        why = reading.get("error") if isinstance(reading, dict) else None
        return {"state": "unknown", "reason": f"no usable GPU reading ({why or 'worker reported none'}); not treated as free"}
    age = _age_s(reading.get("taken_at"), now)
    if age is None or age > max_age or age < -5:
        return {"state": "unknown", "reason": "GPU reading is stale or has no valid timestamp; not treated as free"}

    samples = reading["samples"]
    sustained_util = min(float(s["util_pct"]) for s in samples)  # busy only if EVERY sample is busy
    last = samples[-1]
    used, total = float(last["mem_used_mib"]), float(last["mem_total_mib"])
    free_mib = total - used
    view = {
        "util_pct": sustained_util,
        "mem_used_mib": used,
        "mem_total_mib": total,
        "reading_age_s": round(age, 1),
        "sample_count": len(samples),
    }

    busy_by_util = sustained_util >= threshold
    busy_by_memory = isinstance(min_free, (int, float)) and free_mib < float(min_free)
    if not (busy_by_util or busy_by_memory):
        return {"state": "free", "reason": "GPU load is below the busy threshold", **view}

    in_flight_ids = list(in_flight) if isinstance(in_flight, (list, tuple)) else []
    if in_flight_ids:
        return {
            "state": "free",
            "reason": f"GPU load is attributable to {len(in_flight_ids)} estate execution(s) in flight on this host",
            **view,
        }
    cause = (
        f"{sustained_util:.0f}% utilisation sustained over {len(samples)} samples"
        if busy_by_util
        else f"only {free_mib / 1024:.1f} GB VRAM free (needs {float(min_free) / 1024:.1f} GB)"
    )
    return {
        "state": "busy",
        "reason": f"household GPU busy: {cause}, {used / 1024:.1f} of {total / 1024:.1f} GB VRAM used, no estate work in flight",
        **view,
    }
