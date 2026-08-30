"""
update_database.py

This script updates the database schema by adding new columns to the sessions table
and populating them with appropriate values. It handles SQLite's limitations
with ALTER TABLE operations by checking if columns exist before attempting to add them.

The following columns are added:
- last_accessed (DateTime): Set to created_at for existing records
- is_important (Boolean): Set to False for existing records
- message_count (Integer): Calculated from the number of messages in chat_messages table

Usage:
    python update_database.py
"""

import sqlite3
import os
from datetime import datetime
from sqlalchemy import create_engine, inspect, text
from database import DATABASE_URL, SessionLocal, Base

def check_column_exists(engine, table_name, column_name):
    """Check if a column exists in a table."""
    inspector = inspect(engine)
    columns = inspector.get_columns(table_name)
    return any(col['name'] == column_name for col in columns)

def add_column_sqlite(db_path, table_name, column_name, column_type, default_value=None):
    """
    Add a column to a SQLite table by creating a new table, copying data, and renaming.
    This is necessary because SQLite has limited ALTER TABLE support.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get current table info
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = cursor.fetchall()
    column_names = [col[1] for col in columns]
    
    # Create new table with additional column
    new_table_name = f"{table_name}_new"
    
    # Build new column list
    new_columns = []
    for col in columns:
        new_columns.append(f"{col[1]} {col[2]}")
    
    # Add the new column
    new_column_def = f"{column_name} {column_type}"
    if default_value is not None:
        new_column_def += f" DEFAULT {default_value}"
    new_columns.append(new_column_def)
    
    # Create new table
    columns_sql = ", ".join(new_columns)
    create_sql = f"CREATE TABLE {new_table_name} ({columns_sql})"
    cursor.execute(create_sql)
    
    # Copy data from old table to new table
    column_names_str = ", ".join(column_names)
    insert_sql = f"INSERT INTO {new_table_name} ({column_names_str}) SELECT {column_names_str} FROM {table_name}"
    cursor.execute(insert_sql)
    
    # Drop old table and rename new table
    cursor.execute(f"DROP TABLE {table_name}")
    cursor.execute(f"ALTER TABLE {new_table_name} RENAME TO {table_name}")
    
    conn.commit()
    conn.close()

def add_table_sqlite(db_path, table_name, create_table_sql):
    """Create a table on an existing SQLite DB if it doesn't already exist."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(create_table_sql)
    conn.commit()
    conn.close()


def _upgrade_source_events_columns(engine, db_path):
    """Add the P1 external-ingest columns to a `source_events` table that
    pre-dates them.

    `source_events` already existed in this repo before P1 (an unrelated
    prior chat/session-provenance workstream), so `add_source_events_table`
    below returning early when the table already exists left every real
    deployment's table missing `payload_ref`/`received_at`/`status`/
    `prior_content_hash`/`revision_count` — `record_source_event()` would
    then fail with `OperationalError: no column named payload_ref`. This
    mirrors core/database.py's `_migrate_add_source_event_ingest_columns()`
    so both migration paths converge on the same schema. Additive/
    idempotent: only adds columns that are actually missing.
    """
    additions = [
        ("payload_ref", "TEXT", None),
        ("received_at", "DATETIME", None),
        ("status", "TEXT", "'received'"),
        ("prior_content_hash", "TEXT", None),
        ("revision_count", "INTEGER", "0"),
    ]
    added = []
    for column_name, column_type, default_value in additions:
        if check_column_exists(engine, "source_events", column_name):
            continue
        if db_path:  # SQLite
            add_column_sqlite(db_path, "source_events", column_name, column_type, default_value)
        else:  # Other databases
            with engine.connect() as conn:
                ddl = f"ALTER TABLE source_events ADD COLUMN {column_name} {column_type}"
                if default_value is not None:
                    ddl += f" DEFAULT {default_value}"
                conn.execute(text(ddl))
                conn.commit()
        added.append(column_name)

    if added:
        print(f"Migrated: added {added} columns to source_events")
        if db_path:
            conn = sqlite3.connect(db_path)
            try:
                conn.execute("UPDATE source_events SET status = 'received' WHERE status IS NULL")
                conn.execute("UPDATE source_events SET revision_count = 0 WHERE revision_count IS NULL")
                conn.commit()
            finally:
                conn.close()
        else:
            with engine.connect() as conn:
                conn.execute(text("UPDATE source_events SET status = 'received' WHERE status IS NULL"))
                conn.execute(text("UPDATE source_events SET revision_count = 0 WHERE revision_count IS NULL"))
                conn.commit()

    # Idempotent even if no columns were added: the unique index may still
    # be missing (e.g. a table that already had all 5 columns but not yet
    # the index).
    if db_path:
        conn = sqlite3.connect(db_path)
        try:
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS ix_source_events_source_external_unique "
                "ON source_events(source, external_id) WHERE external_id IS NOT NULL"
            )
            conn.commit()
        except Exception as e:
            print(f"source_events (source, external_id) unique index creation skipped: {e}")
        finally:
            conn.close()
    else:
        with engine.connect() as conn:
            conn.execute(text(
                "CREATE UNIQUE INDEX IF NOT EXISTS ix_source_events_source_external_unique "
                "ON source_events(source, external_id) WHERE external_id IS NOT NULL"
            ))
            conn.commit()


def add_source_events_table(engine, db_path):
    """Add the source_events table for existing DBs that pre-date it
    (external-ingest SourceEvent adapter contract, P1). A neutral
    provenance/dedupe table future importers (Instagram, WhatsApp, ...)
    call through src/source_events.py.record_source_event() — this
    migration only creates the table shape; it never touches raw payload
    content, only a small pointer (`payload_ref`) + a sha256 checksum
    (`content_hash`), same as attachment_refs.py's philosophy for uploads.
    """
    inspector = inspect(engine)
    if "source_events" in inspector.get_table_names():
        # Table already existed (e.g. from the unrelated prior chat/session
        # provenance workstream) — it may pre-date the P1 columns below.
        _upgrade_source_events_columns(engine, db_path)
        return

    create_sql = """
        CREATE TABLE IF NOT EXISTS source_events (
            id TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            external_id TEXT,
            content_hash TEXT,
            domain TEXT NOT NULL DEFAULT 'neutral',
            sensitivity TEXT NOT NULL DEFAULT 'normal',
            payload TEXT,
            payload_ref TEXT,
            received_at DATETIME,
            status TEXT NOT NULL DEFAULT 'received',
            prior_content_hash TEXT,
            revision_count INTEGER NOT NULL DEFAULT 0,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL
        )
    """

    if db_path:  # SQLite
        print("Creating source_events table...")
        add_table_sqlite(db_path, "source_events", create_sql)
        conn = sqlite3.connect(db_path)
        try:
            conn.execute(
                "CREATE INDEX IF NOT EXISTS ix_source_events_source_external "
                "ON source_events(source, external_id)"
            )
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS ix_source_events_source_external_unique "
                "ON source_events(source, external_id) WHERE external_id IS NOT NULL"
            )
            conn.commit()
        finally:
            conn.close()
    else:  # Other databases
        with engine.connect() as conn:
            conn.execute(text(create_sql))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_source_events_source_external "
                "ON source_events(source, external_id)"
            ))
            conn.commit()


def update_database():
    """Update the database schema and populate new columns."""
    # Create engine from DATABASE_URL
    engine = create_engine(DATABASE_URL)

    # Extract database path from DATABASE_URL for SQLite
    db_path = None
    if "sqlite" in DATABASE_URL:
        db_path = DATABASE_URL.replace("sqlite:///", "")
        # Handle relative paths
        if not os.path.isabs(db_path):
            db_path = os.path.join(os.path.dirname(__file__), db_path)

    print(f"Updating database at: {DATABASE_URL}")
    
    # Start a transaction
    db = SessionLocal()
    try:
        # Add last_accessed column if it doesn't exist
        if not check_column_exists(engine, 'sessions', 'last_accessed'):
            print("Adding last_accessed column...")
            if db_path:  # SQLite
                add_column_sqlite(db_path, 'sessions', 'last_accessed', 'DATETIME')
            else:  # Other databases
                with engine.connect() as conn:
                    conn.execute(text("ALTER TABLE sessions ADD COLUMN last_accessed DATETIME"))
                    conn.commit()
        
        # Add is_important column if it doesn't exist
        if not check_column_exists(engine, 'sessions', 'is_important'):
            print("Adding is_important column...")
            if db_path:  # SQLite
                add_column_sqlite(db_path, 'sessions', 'is_important', 'BOOLEAN', '0')
            else:  # Other databases
                with engine.connect() as conn:
                    conn.execute(text("ALTER TABLE sessions ADD COLUMN is_important BOOLEAN DEFAULT FALSE"))
                    conn.commit()
        
        # Add source_events table if it doesn't exist (external-ingest
        # SourceEvent adapter contract, P1)
        add_source_events_table(engine, db_path)

        # Add message_count column if it doesn't exist
        if not check_column_exists(engine, 'sessions', 'message_count'):
            print("Adding message_count column...")
            if db_path:  # SQLite
                add_column_sqlite(db_path, 'sessions', 'message_count', 'INTEGER', '0')
            else:  # Other databases
                with engine.connect() as conn:
                    conn.execute(text("ALTER TABLE sessions ADD COLUMN message_count INTEGER DEFAULT 0"))
                    conn.commit()
        
        # Populate last_accessed with created_at for existing records where last_accessed is NULL
        print("Populating last_accessed column...")
        with engine.connect() as conn:
            conn.execute(text("""
                UPDATE sessions 
                SET last_accessed = created_at 
                WHERE last_accessed IS NULL
            """))
            conn.commit()
        
        # Populate is_important with FALSE for existing records where is_important is NULL
        print("Populating is_important column...")
        with engine.connect() as conn:
            conn.execute(text("""
                UPDATE sessions 
                SET is_important = 0 
                WHERE is_important IS NULL
            """))
            conn.commit()
        
        # Calculate and populate message_count from chat_messages table
        print("Calculating and populating message_count column...")
        with engine.connect() as conn:
            # First, set all message_count to 0
            conn.execute(text("UPDATE sessions SET message_count = 0"))
            
            # Then, count messages for each session and update
            conn.execute(text("""
                UPDATE sessions 
                SET message_count = (
                    SELECT COUNT(*) 
                    FROM chat_messages 
                    WHERE chat_messages.session_id = sessions.id
                )
            """))
            conn.commit()
        
        print("Database update completed successfully!")
        
    except Exception as e:
        print(f"Error updating database: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    update_database()
