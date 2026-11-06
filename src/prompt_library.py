"""Central prompt library behind every Odysseus pipeline.

One place for pipeline prompts, immutable versions, outcome counts and gated promotion.  It never rewrites prose (agents draft
children, as in src/prompt_evolution.py, whose provenance validation it reuses) and never stores source text: outcomes are counts.

Layout (repo):   prompts/library/<id>/v<N>.md          immutable, front matter: id, version, parent, reason
                 prompts/library/<id>/CURRENT          the promoted version number (Git history is the audit trail)
Layout (data):   <ODYSSEUS_DATA_DIR>/prompt-library/outcomes.jsonl   {id, version, ts, counts{...}}   counts only
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Optional

LIB = Path(__file__).resolve().parent.parent / "prompts" / "library"
_FM = re.compile(r"\A---\n(.*?)\n---\n", re.S)


def _outcomes_path() -> Path:
    base = Path(os.environ.get("ODYSSEUS_DATA_DIR", "data")) / "prompt-library"
    base.mkdir(parents=True, exist_ok=True)
    return base / "outcomes.jsonl"


def versions(prompt_id: str) -> list[int]:
    d = LIB / prompt_id
    return sorted(int(m.group(1)) for f in d.glob("v*.md") if (m := re.fullmatch(r"v(\d+)\.md", f.name))) if d.is_dir() else []


def current_version(prompt_id: str) -> int:
    f = LIB / prompt_id / "CURRENT"
    return int(f.read_text().strip()) if f.is_file() else max(versions(prompt_id))


def _read(prompt_id: str, version: int) -> tuple[dict, str]:
    raw = (LIB / prompt_id / f"v{version}.md").read_text(encoding="utf-8")
    m = _FM.match(raw)
    meta = dict(line.split(": ", 1) for line in m.group(1).splitlines() if ": " in line) if m else {}
    return meta, raw[m.end():] if m else raw


def get(prompt_id: str, version: Optional[int] = None) -> tuple[str, int]:
    """(text, version) of the promoted version, or of an explicit one."""
    v = version or current_version(prompt_id)
    return _read(prompt_id, v)[1].rstrip("\n"), v


def text(prompt_id: str) -> str:
    return get(prompt_id)[0]


def record(prompt_id: str, version: int, **counts: int) -> None:
    """Append outcome counts for a prompt version (parse failures, accepts, rejects...).  Never raw text."""
    try:
        with _outcomes_path().open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"id": prompt_id, "version": version, "ts": int(time.time()), "counts": counts}) + "\n")
    except OSError:
        pass                                   # telemetry must never break a pipeline


def summary(prompt_id: Optional[str] = None) -> dict:
    """Per prompt version: summed counts and rates, so a drafting agent can see which version is actually better."""
    out: dict = {}
    try:
        lines = _outcomes_path().read_text(encoding="utf-8").splitlines()
    except OSError:
        return out
    for line in lines:
        r = json.loads(line)
        if prompt_id and r["id"] != prompt_id:
            continue
        acc = out.setdefault(r["id"], {}).setdefault(r["version"], {})
        for k, n in r["counts"].items():
            acc[k] = acc.get(k, 0) + int(n)
    return out


def register_child(prompt_id: str, body: str, *, parent: int, reason: str) -> int:
    """Add an immutable child version drafted by an agent.  It is NOT current until promote() passes."""
    if parent not in versions(prompt_id):
        raise ValueError("unknown parent version")
    if not reason.strip():
        raise ValueError("a change reason is required")
    n = max(versions(prompt_id)) + 1
    (LIB / prompt_id / f"v{n}.md").write_text(f"---\nid: {prompt_id}\nversion: {n}\nparent: {parent}\nreason: {reason.strip()}\n---\n{body.rstrip()}\n",
                                              encoding="utf-8")
    return n


def promote(prompt_id: str, version: int, *, metric: str = "ok_rate", margin: float = 0.0) -> bool:
    """Make a child current only if its recorded outcomes beat its parent on `metric` (ok/total).  Deterministic, no model."""
    meta, _ = _read(prompt_id, version)
    s = summary(prompt_id).get(prompt_id, {})
    def rate(v: int) -> Optional[float]:
        c = s.get(v, {})
        return c.get("ok", 0) / c["total"] if c.get("total") else None
    child, parent = rate(version), rate(int(meta.get("parent", 0)))
    if child is None or parent is None or child < parent + margin:
        return False
    (LIB / prompt_id / "CURRENT").write_text(f"{version}\n")
    return True


def improvement_report() -> dict:
    """Weak spots per current version (high failure or rejection rate), for the routine improvement work item."""
    rep = {}
    for pid, by_v in summary().items():
        v = current_version(pid)
        c = by_v.get(v, {})
        total = c.get("total", 0)
        if total >= 20:
            weak = {k: round(c[k] / total, 3) for k in ("failed", "rejected", "escalated") if c.get(k, 0) / total > 0.15}
            rep[pid] = {"version": v, "total": total, "weak": weak}
    return rep
