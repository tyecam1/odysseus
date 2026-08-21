"""LM1 benchmark fixture — derived from core/database.py:788-793 @ ac295b7
(tyecam1/odysseus), with a deliberately injected bug for the bounded
code-repair task class. Not production code; never imported by the app.
"""
from datetime import datetime, timedelta

PARK_LEASE_STALE_SECONDS = 1800  # 30 min without a heartbeat renewal


class Lease:
    def __init__(self, heartbeat_at: datetime):
        self.heartbeat_at = heartbeat_at


def park_lease_is_stale(lease: "Lease", *, now: "datetime | None" = None) -> bool:
    """Return True when `lease` has gone stale (no heartbeat renewal within
    PARK_LEASE_STALE_SECONDS). BUG: comparison operator is inverted, so this
    currently reports staleness backwards."""
    now = now or datetime.utcnow()
    return (now - lease.heartbeat_at).total_seconds() < PARK_LEASE_STALE_SECONDS
