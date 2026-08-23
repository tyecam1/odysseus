"""memory_outbox.py — idempotent replay between two `MisumiMemory` stores
(Workstream E, docs/aoteru-long-horizon-autonomous-convergence.agent-task.md;
canonical plan §6: "events accepted while the primary memory leader is
unavailable... replay idempotent outbox events by stable UUID/hash").

Does NOT introduce a new store or authority — `src/misumi_memory.py`'s
append-only JSONL capsule/open_loop/handoff stores remain the only memory
representation (same discipline `core.database.SourceEvent`'s own
docstring already states for provenance). While home is the unavailable
primary, this lab-local `MisumiMemory` instance already accepts every
write directly — nothing here changes that; captures never block or
queue. What's missing, and what this module provides, is the other half:
moving what accumulated locally into a future primary (home, once
promoted) without creating duplicates if the same replay is run more than
once — a crash mid-replay, a retried sync, or an operator re-running the
command by hand must all be safe.

Idempotency key: `MisumiMemory.capture()` already stamps every record
with a UUID-based `id` (`_new_id`), and every store folds latest-by-id.
Replay therefore only needs to skip any id the target already has —
no separate hash/dedup table required.
"""
from __future__ import annotations

from typing import Dict

from src.misumi_memory import MisumiMemory

STORES = ("capsules", "open_loops", "handoffs")


def replay(source: MisumiMemory, target: MisumiMemory) -> Dict[str, Dict[str, int]]:
    """Copy every record from `source` into `target` that `target` does
    not already have (by id), for all three stores. Safe to call
    repeatedly — a second call with nothing new in `source` applies
    zero records. Corrupt lines in either store are already dropped by
    `MisumiMemory._fold` (via `raw_records`) and reported back here
    rather than silently ignored, so an operator can tell "nothing to
    replay" apart from "some source lines didn't parse".
    """
    result: Dict[str, Dict[str, int]] = {}
    for store in STORES:
        source_records, source_corrupt = source.raw_records(store)
        target_records, target_corrupt = target.raw_records(store)
        known_ids = {r["id"] for r in target_records if isinstance(r.get("id"), str)}

        applied = 0
        for record in source_records:
            record_id = record.get("id")
            if not isinstance(record_id, str) or record_id in known_ids:
                continue
            target.append_record(store, record)
            known_ids.add(record_id)
            applied += 1

        result[store] = {
            "source_count": len(source_records),
            "applied": applied,
            "already_present": len(source_records) - applied,
            "source_corrupt_lines": source_corrupt,
            "target_corrupt_lines": target_corrupt,
        }
    return result
