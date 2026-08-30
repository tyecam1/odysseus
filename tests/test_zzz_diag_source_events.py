"""Temporary CI diagnostic — see docs/aoteru-external-knowledge-ingestion-programme-state.md.
No fixtures, no dependency on tests/test_source_events.py's autouse fixture
(which itself errors before running, so it never got to report anything).
"""


def test_diag_source_events_table_state():
    from core.database import engine, SourceEvent, Base
    from sqlalchemy import inspect as sa_inspect

    tables = sorted(sa_inspect(engine).get_table_names())
    print(f"DIAG engine.url={engine.url!r}")
    print(f"DIAG table_count={len(tables)}")
    print(f"DIAG has_source_events={'source_events' in tables}")
    print(f"DIAG SourceEvent.__table__.name={SourceEvent.__table__.name!r}")
    print(f"DIAG metadata_has_source_events={'source_events' in Base.metadata.tables}")
    print(f"DIAG first_20_tables={tables[:20]}")
    print(f"DIAG last_20_tables={tables[-20:]}")

    # Try creating it directly, right here, to see if that raises anything
    # create_all()'s own exception handling might be swallowing.
    try:
        SourceEvent.__table__.create(bind=engine, checkfirst=True)
        print("DIAG direct_create_all_ok=True")
    except Exception as e:
        print(f"DIAG direct_create_FAILED={type(e).__name__}: {e}")

    tables_after = sorted(sa_inspect(engine).get_table_names())
    print(f"DIAG has_source_events_after_direct_create={'source_events' in tables_after}")
