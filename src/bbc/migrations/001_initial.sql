PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS canonical_state (
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    state_json TEXT NOT NULL,
    state_hash TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (entity_type, entity_id)
);

CREATE TABLE IF NOT EXISTS state_events (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    event_type TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    actor TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    previous_hash TEXT,
    event_hash TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS audit_events (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    actor TEXT NOT NULL,
    capability_id TEXT NOT NULL,
    target TEXT NOT NULL,
    inputs_hash TEXT NOT NULL,
    result TEXT NOT NULL CHECK (result IN ('succeeded', 'failed', 'denied')),
    evidence_json TEXT NOT NULL,
    rollback_ref TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    previous_hash TEXT,
    event_hash TEXT NOT NULL UNIQUE
);

CREATE INDEX IF NOT EXISTS idx_state_events_entity ON state_events(entity_type, entity_id, sequence);
CREATE INDEX IF NOT EXISTS idx_audit_events_capability ON audit_events(capability_id, sequence);

CREATE TRIGGER IF NOT EXISTS state_events_no_update
BEFORE UPDATE ON state_events BEGIN
    SELECT RAISE(ABORT, 'state events are immutable');
END;

CREATE TRIGGER IF NOT EXISTS state_events_no_delete
BEFORE DELETE ON state_events BEGIN
    SELECT RAISE(ABORT, 'state events are immutable');
END;

CREATE TRIGGER IF NOT EXISTS audit_events_no_update
BEFORE UPDATE ON audit_events BEGIN
    SELECT RAISE(ABORT, 'audit events are immutable');
END;

CREATE TRIGGER IF NOT EXISTS audit_events_no_delete
BEFORE DELETE ON audit_events BEGIN
    SELECT RAISE(ABORT, 'audit events are immutable');
END;
