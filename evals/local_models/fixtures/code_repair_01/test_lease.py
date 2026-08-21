from datetime import datetime, timedelta

from lease import Lease, park_lease_is_stale, PARK_LEASE_STALE_SECONDS


def test_fresh_heartbeat_not_stale():
    now = datetime.utcnow()
    lease = Lease(heartbeat_at=now - timedelta(seconds=60))
    assert park_lease_is_stale(lease, now=now) is False


def test_old_heartbeat_is_stale():
    now = datetime.utcnow()
    lease = Lease(heartbeat_at=now - timedelta(seconds=PARK_LEASE_STALE_SECONDS + 60))
    assert park_lease_is_stale(lease, now=now) is True


def test_boundary_not_yet_stale():
    now = datetime.utcnow()
    lease = Lease(heartbeat_at=now - timedelta(seconds=PARK_LEASE_STALE_SECONDS - 5))
    assert park_lease_is_stale(lease, now=now) is False
