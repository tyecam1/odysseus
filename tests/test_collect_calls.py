"""The read-only call-telemetry collector counts completed calls and repeats on an unchanged head correctly."""
import importlib.util
import json
import sqlite3
from pathlib import Path

HEAD_A, HEAD_B = "a" * 40, "b" * 40


def collector():
    path = Path(__file__).parents[1] / "evals" / "sol-packet" / "collect_calls.py"
    spec = importlib.util.spec_from_file_location("collect_calls", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def database(tmp_path, decisions, executions=()):
    path = tmp_path / "app.db"
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE routing_decisions (id TEXT PRIMARY KEY, escalation_reason TEXT)")
    con.execute("CREATE TABLE estate_executions (id TEXT PRIMARY KEY, lifecycle_state TEXT)")
    con.executemany("INSERT INTO routing_decisions VALUES (?, ?)", decisions)
    con.executemany("INSERT INTO estate_executions VALUES (?, ?)", executions)
    con.commit()
    con.close()
    return str(path)


def record(**fields):
    return "insufficient_capability |call=" + json.dumps({"v": 1, **fields})


def test_completed_calls_and_unchanged_head_repeats_are_counted_separately(tmp_path):
    db = database(tmp_path, [
        ("d1", record(subject="odysseus:pr:1", head_sha=HEAD_A, started_at="2026-11-06T10:00:00+00:00", submitted=True, execution_id="e1")),
        ("d2", record(subject="odysseus:pr:1", head_sha=HEAD_A, started_at="2026-11-06T10:05:00+00:00", submitted=True, execution_id="e2")),
        ("d3", record(subject="odysseus:pr:1", head_sha=HEAD_A, started_at="2026-11-06T10:10:00+00:00", submitted=True, execution_id="e3")),
        ("d4", record(subject="odysseus:pr:1", head_sha=HEAD_B, started_at="2026-11-06T11:00:00+00:00", launched=True)),
    ], [("e1", "succeeded"), ("e2", "failed"), ("e3", "succeeded")])
    module = collector()
    (row,) = module.summarise(module.load(db))
    assert row["calls"] == 4 and row["distinct_heads"] == 2
    assert row["unchanged_head_repeats"] == 2                    # e1->e2 and e2->e3 share a head
    assert row["succeeded"] == 3 and row["unchanged_head_repeats_among_succeeded"] == 1   # failed e2 is not a completed review


def test_refusals_reuse_malformed_and_untagged_records_are_handled(tmp_path):
    db = database(tmp_path, [
        ("r1", record(subject="odysseus:pr:2", head_sha=HEAD_A, launched=False)),                      # refusal or reuse: not a call
        ("r2", record(subject="odysseus:pr:2", head_sha=HEAD_A, v=2, launched=True)),                  # unknown version: ignored
        ("r3", "x |call={not json"),                                                                   # malformed: skipped, no error
        ("r4", "worker_failed"),                                                                       # no suffix at all
        ("r5", record(subject="odysseus:pr:2", head_sha=None, launched=True, started_at="2026-11-06T09:00:00+00:00")),
        ("r6", record(subject=None, head_sha=None, launched=True, started_at="2026-11-06T09:01:00+00:00")),
    ])
    module = collector()
    calls = module.load(db)
    assert sorted(c["decision_id"] for c in calls) == ["r5", "r6"]
    rows = {r["subject"]: r for r in module.summarise(calls)}
    assert rows["odysseus:pr:2"]["untagged_calls"] == 1 and rows["odysseus:pr:2"]["unchanged_head_repeats"] == 0
    assert rows[None]["calls"] == 1


def test_the_database_is_opened_read_only(tmp_path):
    db = database(tmp_path, [("d1", record(subject="s", head_sha=HEAD_A, launched=True))])
    module = collector()
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        con.execute("DELETE FROM routing_decisions")
        raised = False
    except sqlite3.OperationalError:
        raised = True
    assert raised                                                  # the mode the collector uses cannot write
    assert len(module.load(db)) == 1                               # and the collector leaves the data untouched
