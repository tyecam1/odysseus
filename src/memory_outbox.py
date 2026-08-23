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

    Conflict check (Workstream I: "backup/restore and conflict checks"):
    an id present on *both* sides is not automatically "already present"
    — if the two sides independently diverged (e.g. each store's own copy
    was separately confirmed/rerouted after a prior partial sync, or one
    side's line was corrupted and silently reconstructed differently),
    skipping it as clean would permanently hide the divergence. Replay
    never overwrites an existing target record either way (target stays
    authoritative for an id it already has — resolving a real conflict is
    a human decision, not this function's), but a content mismatch is
    now counted and the affected ids are returned rather than folded
    silently into `already_present`.
    """
    result: Dict[str, Dict[str, int]] = {}
    for store in STORES:
        source_records, source_corrupt = source.raw_records(store)
        target_records, target_corrupt = target.raw_records(store)
        target_by_id = {r["id"]: r for r in target_records if isinstance(r.get("id"), str)}

        applied = 0
        conflicting_ids = []
        for record in source_records:
            record_id = record.get("id")
            if not isinstance(record_id, str):
                continue
            existing = target_by_id.get(record_id)
            if existing is None:
                target.append_record(store, record)
                target_by_id[record_id] = record
                applied += 1
                continue
            if existing != record:
                conflicting_ids.append(record_id)

        result[store] = {
            "source_count": len(source_records),
            "applied": applied,
            "already_present": len(source_records) - applied - len(conflicting_ids),
            "conflicting": len(conflicting_ids),
            "conflicting_ids": conflicting_ids,
            "source_corrupt_lines": source_corrupt,
            "target_corrupt_lines": target_corrupt,
        }
    return result
