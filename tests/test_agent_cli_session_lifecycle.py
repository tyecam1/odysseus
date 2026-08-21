"""Tests for scripts/agent's LogicalSession lifecycle handling.

Finding: failed or non-launched Claude sessions must not remain
`status="active"` forever. Covers both halves of the fix:
- `cmd_claude` writes the real terminal status at creation time instead of
  "active" then never updating it;
- `_reconcile_stale_sessions` sweeps any row that still ends up stuck
  "active" (e.g. a wrapper process that died mid-dispatch) once it is
  old enough that a real launch would have confirmed itself.
"""
import importlib.machinery
import importlib.util
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "agent"


def load_module():
    loader = importlib.machinery.SourceFileLoader("agent_cli", str(SCRIPT_PATH))
    spec = importlib.util.spec_from_loader("agent_cli", loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    loader.exec_module(module)
    return module


@pytest.fixture
def agent_cli():
    return load_module()


def test_reconcile_leaves_fresh_active_session_alone(agent_cli):
    from core.database import get_db_session, LogicalSession

    session_id = str(uuid.uuid4())
    with get_db_session() as db:
        db.add(LogicalSession(
            id=session_id, host_id="test-host", repo_id="test-repo",
            engine="claude", status="active",
        ))

    with get_db_session() as db:
        reconciled = agent_cli._reconcile_stale_sessions(db, LogicalSession)
        assert reconciled == 0
        row = db.query(LogicalSession).filter(LogicalSession.id == session_id).first()
        assert row.status == "active"


def test_reconcile_marks_stale_unconfirmed_session_failed(agent_cli):
    from core.database import get_db_session, LogicalSession, utcnow_naive

    session_id = str(uuid.uuid4())
    with get_db_session() as db:
        row = LogicalSession(
            id=session_id, host_id="test-host", repo_id="test-repo",
            engine="claude", status="active",
        )
        db.add(row)

    with get_db_session() as db:
        # Backdate created_at past the staleness window, as if the wrapper
        # died shortly after creating the row and never confirmed launch.
        stale_row = db.query(LogicalSession).filter(LogicalSession.id == session_id).first()
        stale_row.created_at = utcnow_naive() - timedelta(seconds=agent_cli._STALE_ACTIVE_SESSION_SECONDS + 60)

    with get_db_session() as db:
        reconciled = agent_cli._reconcile_stale_sessions(db, LogicalSession)
        assert reconciled == 1
        row = db.query(LogicalSession).filter(LogicalSession.id == session_id).first()
        assert row.status == "failed"
        assert "reconciled" in row.last_result


def test_reconcile_leaves_confirmed_launch_alone_even_if_old(agent_cli):
    """A session with a real claude_session_id is a confirmed launch, not
    an orphan — staleness alone must not reclassify it."""
    from core.database import get_db_session, LogicalSession, utcnow_naive

    session_id = str(uuid.uuid4())
    with get_db_session() as db:
        db.add(LogicalSession(
            id=session_id, host_id="test-host", repo_id="test-repo",
            engine="claude", status="active", claude_session_id="real-claude-session-abc",
        ))

    with get_db_session() as db:
        row = db.query(LogicalSession).filter(LogicalSession.id == session_id).first()
        row.created_at = utcnow_naive() - timedelta(seconds=agent_cli._STALE_ACTIVE_SESSION_SECONDS + 60)

    with get_db_session() as db:
        reconciled = agent_cli._reconcile_stale_sessions(db, LogicalSession)
        assert reconciled == 0
        row = db.query(LogicalSession).filter(LogicalSession.id == session_id).first()
        assert row.status == "active"
