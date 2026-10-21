"""Export must return the whole archive up to EXPORT_MAX_LIMIT, not silently stop at QUERY_MAX_LIMIT.

Found by the 2026-10-06 backup restore drill: a restored archive of 220 permanent events exported 200 rows.
"""

import json

import pytest

from src import misumi_transcripts as svc
from tests.test_misumi_transcripts import enable_archive, make_db


@pytest.fixture()
def factory(tmp_path):
    engine, fac = make_db(tmp_path / "t.db")
    yield fac
    engine.dispose()


def _fill(factory, n):
    enable_archive(factory, "alice")
    with factory() as db:
        for i in range(n):
            svc.ingest_event(db, owner="alice", event_id=f"e{i:04d}", text=f"line {i}")


def test_export_is_not_truncated_at_the_query_page_size(factory):
    n = svc.QUERY_MAX_LIMIT + 20
    _fill(factory, n)
    with factory() as db:
        lines = svc.export_events(db, "alice").splitlines()
    assert len(lines) == n
    ids = [json.loads(line)["event_id"] for line in lines]
    assert ids == sorted(ids) and len(set(ids)) == n  # oldest first, no duplicates across page seams


def test_export_still_honours_an_explicit_smaller_limit(factory):
    _fill(factory, svc.QUERY_MAX_LIMIT + 20)
    with factory() as db:
        assert len(svc.export_events(db, "alice", limit=210).splitlines()) == 210
        assert len(svc.export_events(db, "alice", limit=3).splitlines()) == 3


def test_export_is_still_bounded_by_export_max_limit(factory, monkeypatch):
    monkeypatch.setattr(svc, "EXPORT_MAX_LIMIT", svc.QUERY_MAX_LIMIT + 5)
    _fill(factory, svc.QUERY_MAX_LIMIT + 20)
    with factory() as db:
        assert len(svc.export_events(db, "alice", limit=10**6).splitlines()) == svc.QUERY_MAX_LIMIT + 5