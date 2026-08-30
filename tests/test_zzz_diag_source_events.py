"""Temporary CI diagnostic — see docs/aoteru-external-knowledge-ingestion-programme-state.md.
Always fails on purpose so pytest prints its captured output regardless of
outcome (a prior version had no assertion and silently told us nothing).
"""


def test_diag_source_events_table_state():
    from core.database import engine, SourceEvent, Base, SessionLocal
    from sqlalchemy import inspect as sa_inspect

    lines = []
    tables = sorted(sa_inspect(engine).get_table_names())
    lines.append(f"engine.url={engine.url!r}")
    lines.append(f"engine.pool.__class__={engine.pool.__class__!r}")
    lines.append(f"has_source_events_via_inspect_engine={'source_events' in tables}")
    lines.append(f"has_source_events_via_metadata={'source_events' in Base.metadata.tables}")

    db = SessionLocal()
    try:
        session_bind = db.get_bind()
        lines.append(f"session_bind={session_bind!r}")
        lines.append(f"session_bind_is_engine={session_bind is engine}")
        try:
            count = db.execute(
                __import__("sqlalchemy").text("SELECT COUNT(*) FROM source_events")
            ).scalar()
            lines.append(f"raw_select_via_session_ok=True count={count}")
        except Exception as e:
            lines.append(f"raw_select_via_session_FAILED={type(e).__name__}: {e}")
        try:
            orm_count = db.query(SourceEvent).count()
            lines.append(f"orm_query_via_session_ok=True count={orm_count}")
        except Exception as e:
            lines.append(f"orm_query_via_session_FAILED={type(e).__name__}: {e}")
    finally:
        db.close()

    try:
        with engine.connect() as conn:
            r = conn.execute(
                __import__("sqlalchemy").text("SELECT COUNT(*) FROM source_events")
            ).scalar()
            lines.append(f"raw_select_via_engine_connect_ok=True count={r}")
    except Exception as e:
        lines.append(f"raw_select_via_engine_connect_FAILED={type(e).__name__}: {e}")

    assert False, "DIAGNOSTIC (always fails on purpose):\n" + "\n".join(lines)
