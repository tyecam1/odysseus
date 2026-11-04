"""Provider capacity across real CLI failures, routing, and recovery.

Only host transport and credentials are simulated. The CLI is an executable
process, quota observations live in the existing file-backed telemetry DB.
"""
import importlib.machinery
import importlib.util
import json
import os
import socket
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import core.database as cdb
from src import delegation_preflight as preflight
from src import estate_router as router
from src import estate_worker_client as client


@pytest.fixture
def quota_lane(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'telemetry.db'}")
    cdb.Base.metadata.create_all(engine)
    monkeypatch.setattr(cdb, "SessionLocal", sessionmaker(bind=engine))
    config = tmp_path / 'config'
    config.mkdir()
    (config / 'estate.yaml').write_text(yaml.safe_dump({'hosts': [{
        'id': 'lab', 'hostname': socket.gethostname(), 'role': 'lab',
        'identity_verified': True, 'worker': {'enabled': True, 'transport': 'local',
        'qualified_executors': ['local', 'deterministic', 'codex', 'codex-write']},
    }]}))
    (config / 'models.yaml').write_text(yaml.safe_dump({
        'default_paid_provider': 'codex', 'paid_providers': [{'name': 'codex'}],
        'capabilities': [{'alias': 'code-strong', 'binding': None}],
    }))
    monkeypatch.setattr(router, '_CONFIG_DIR', config)
    monkeypatch.setattr(client, 'worker_health', lambda host: {
        'codex': {'available': True, 'detail': '/fake/codex'},
    })
    monkeypatch.setattr(client, 'call_worker', lambda host, verb, payload, **kw: {
        'result': router.execute_codex(payload['objective']),
        'attestation': {'host_id': host},
    })
    state = tmp_path / 'message'
    count = tmp_path / 'calls'
    state.write_text("ERROR: You've hit your usage limit ... try again at 5:39 PM.")
    executable = tmp_path / 'codex'
    executable.write_text(f'''#!{sys.executable}
import json, pathlib, sys
state = pathlib.Path({str(state)!r})
count = pathlib.Path({str(count)!r})
count.write_text(count.read_text() + 'call\\n' if count.exists() else 'call\\n')
if sys.argv[1:3] == ['debug', 'models']:
    if state.read_text() == 'catalogue-quota':
        print("ERROR: You've hit your usage limit ... try again at 5:39 PM.", file=sys.stderr)
        sys.exit(1)
    print(json.dumps({{'models': [{{'slug': 'gpt-6.1-sol'}}]}}))
    sys.exit(0)
message = state.read_text()
if message != 'ok':
    print(message, file=sys.stderr)
    sys.exit(1)
pathlib.Path(sys.argv[sys.argv.index('-o')+1]).write_text('done')
''')
    executable.chmod(0o755)
    monkeypatch.setattr(router, '_codex_available', lambda: (True, str(executable)))
    now = [datetime(2026, 11, 4, 17, 0, tzinfo=timezone.utc)]
    monkeypatch.setattr(router, '_provider_now', lambda: now[0])
    yield state, count, now
    engine.dispose()


def _run_paid():
    return router.run_task({'task_class': 'code_review', 'objective': 'bounded read-only task',
        'requirements': {'capabilities': ['code-strong']},
        'routing': {'allow_paid_escalation': True}})


def _exhaust():
    result = _run_paid()
    assert result['ok'] is False
    assert result['execution']['provider_health']['state'] == 'quota_exhausted'
    return result['execution']['provider_health']


def test_real_usage_limit_preflight_keeps_lab_eligible_and_api_truthful(quota_lane):
    health = _exhaust()
    assert health['retry_after'] == '2026-11-04T17:39:00+00:00'
    assert health['retry_after_source'] == 'provider_time'
    result = preflight.delegation_preflight([{'task_class': 'code_review'}])
    codex = result['snapshot']['codex']
    assert codex['available'] is False and codex['reason'] != 'live'
    assert codex['provider_health']['state'] == 'quota_exhausted'
    assert codex['provider_health']['retry_after'] == health['retry_after']
    host = result['snapshot']['eligible_hosts'][0]
    assert host['eligible'] and host['healthy'] and host['worker_enabled']
    assert result['units'][0]['recommended_route'] is None
    assert 'no_qualified_fallback' in result['units'][0]['reason']
    assert router.resolve_route({'task_class': 'batch_test'})['ok'] is True
    import routes.estate_routing_routes as routes
    app = FastAPI()
    @app.middleware('http')
    async def auth(request, call_next):
        request.state.current_user = 'operator'
        request.state.api_token = False
        return await call_next(request)
    app.include_router(routes.setup_estate_routing_routes())
    response = TestClient(app).post('/api/estate/preflight', json={'units': [{'task_class': 'code_review'}]})
    assert response.status_code == 200
    assert response.json()['snapshot']['codex']['provider_health']['state'] == 'quota_exhausted'


def test_repeated_dispatch_refused_without_starting_cli_or_write_admission(quota_lane, monkeypatch):
    state, count, now = quota_lane
    _exhaust()
    before = count.read_text()
    assert _run_paid()['escalation_reason'] == 'provider_quota_exhausted'
    monkeypatch.setattr(router, 'execute_write_via_worker', lambda *a, **k: pytest.fail('write admitted'))
    refusal = router.execute_codex_write_durable('implement', repo_id='odysseus', host_id='lab')
    assert refusal['executed'] is False
    assert 'codex quota_exhausted' in refusal['error']
    monkeypatch.setattr(router, '_dispatch_read_only', lambda *a, **k: pytest.fail('worker dispatched'))
    result = router.run_task({'task_class': 'code_review', 'objective': 'review',
        'requirements': {'capabilities': ['code-strong']},
        'routing': {'allow_paid_escalation': True}})
    assert result['executed'] is False
    assert result['escalation_reason'] == 'provider_quota_exhausted'
    assert count.read_text() == before
    with cdb.get_db_session() as db:
        row = db.query(cdb.RoutingDecision).filter_by(id=result['decision_id']).one()
        assert row.status == 'blocked'
        assert row.escalation_reason == 'provider_quota_exhausted'


def test_unparseable_reset_is_explicit_bounded_backoff(quota_lane):
    state, count, now = quota_lane
    state.write_text("ERROR: You've hit your usage limit ... try again later.")
    health = _exhaust()
    assert datetime.fromisoformat(health['retry_after']) == now[0] + timedelta(seconds=900)
    assert health['retry_after_source'] == 'bounded_backoff'
    assert '900-second bounded backoff' in health['reason']


def test_expiry_requires_success_before_provider_returns_to_ok(quota_lane):
    state, count, now = quota_lane
    health = _exhaust()
    now[0] = datetime.fromisoformat(health['retry_after']) + timedelta(seconds=1)
    snapshot = preflight.delegation_preflight([{'task_class': 'code_review'}])['snapshot']['codex']
    assert snapshot['available'] is False
    assert snapshot['provider_health']['state'] == 'quota_exhausted'
    assert snapshot['provider_health']['retry_allowed'] is True
    state.write_text('ok')
    assert _run_paid()['ok'] is True
    assert router.provider_health('lab')['state'] == 'ok'
    snapshot = preflight.delegation_preflight([{'task_class': 'code_review'}])['snapshot']['codex']
    assert snapshot['available'] is True and snapshot['provider_health']['state'] == 'ok'


@pytest.mark.parametrize('message, expected', [
    ('ERROR: You’ve hit your usage limit ... try again at 5:39 pm.', '2026-11-04T17:39:00+00:00'),
    ("You've hit your usage limit ... try again at 5:39 PM UTC.", '2026-11-04T17:39:00+00:00'),
    ("You've hit your usage limit ... try again at 2026-11-05T17:39:00Z.", '2026-11-05T17:39:00+00:00'),
    ("You've hit your usage limit ... try again at 4:39 PM.", '2026-11-04T17:15:00+00:00'),
    ("You've hit your usage limit ... try again at 25:39 PM.", '2026-11-04T17:15:00+00:00'),
])
def test_reset_parser_never_rolls_past_or_invalid_time_into_tomorrow(quota_lane, message, expected):
    assert router._quota_observation(message)['retry_after'] == expected


def test_generic_executor_failure_does_not_mark_quota(quota_lane):
    state, count, now = quota_lane
    state.write_text('sandbox failed')
    assert _run_paid()['ok'] is False
    assert router.provider_health('lab')['state'] == 'unknown'


def test_observation_survives_worker_process_exit(quota_lane):
    _exhaust()
    environment = {**os.environ, 'DATABASE_URL': str(cdb.SessionLocal.kw['bind'].url)}
    process = subprocess.run([sys.executable, '-c',
        "import json; from src.estate_router import provider_health; print(json.dumps(provider_health('lab')))"],
        capture_output=True, text=True, env=environment, timeout=15)
    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout)['state'] == 'quota_exhausted'


def test_local_alternative_preserves_reserved_gate_and_write_authority(quota_lane, monkeypatch):
    _exhaust()
    route = router.resolve_route({'task_class': 'code_review',
        'requirements': {'capabilities': ['code-strong']}}, record_decision=False)
    route.update(ok=True)
    route['route']['executor'] = 'local'
    monkeypatch.setattr(router, 'resolve_route', lambda *a, **k: route)
    ordinary = preflight.delegation_preflight([{'task_class': 'code_review'}])['units'][0]
    assert ordinary['ok'] and ordinary['recommended_route'] == 'local'
    reserved = preflight.delegation_preflight([{'task_class': 'code_review',
        'verification': {'independent_model_required': True}}])['units'][0]
    assert not reserved['ok'] and reserved['recommended_route'] is None
    monkeypatch.setattr(router, '_codex_write_authority', lambda *a: {'ok': True, 'lease_id': 'existing'})
    write = preflight.delegation_preflight([{'task_class': 'code_implementation', 'repo': 'odysseus'}])['units'][0]
    assert not write['ok'] and write['recommended_route'] is None
    assert write['write_authority']['ready'] is True
    without_repo = preflight.delegation_preflight([{'task_class': 'code_implementation'}])['units'][0]
    assert not without_repo['ok'] and without_repo['recommended_route'] is None


def test_full_error_parsed_before_display_truncation(quota_lane):
    state, count, now = quota_lane
    state.write_text("\x1b[31mYou've hit your usage limit ... try again at 5:39 PM.\x1b[0m\n" + 'noise' * 200)
    assert _exhaust()['retry_after'] == '2026-11-04T17:39:00+00:00'


def test_catalogue_usage_limit_is_classified_without_model_fallback(quota_lane):
    state, count, now = quota_lane
    state.write_text('catalogue-quota')
    result = _run_paid()
    assert result['execution']['model_policy'] == 'fail_closed'
    assert result['provider_health']['state'] == 'quota_exhausted'
    assert result['provider_health']['retry_after'] == '2026-11-04T17:39:00+00:00'
    assert count.read_text().count('call') == 1
    assert _run_paid()['executed'] is False
    assert count.read_text().count('call') == 1


def test_health_is_host_scoped_and_visible_in_agent_status(quota_lane):
    _exhaust()
    assert router.provider_health('other-worker')['state'] == 'unknown'
    loader = importlib.machinery.SourceFileLoader('quota_agent_cli', str(Path('scripts/agent').resolve()))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    agent = importlib.util.module_from_spec(spec)
    loader.exec_module(agent)
    assert agent._provider_health_on_this_host({'id': 'lab'})['codex']['state'] == 'quota_exhausted'


def test_routing_health_column_migration_is_additive_and_repeatable(tmp_path, monkeypatch):
    from sqlalchemy import text
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    with engine.begin() as db:
        db.execute(text('CREATE TABLE routing_decisions (id TEXT PRIMARY KEY)'))
        db.execute(text("INSERT INTO routing_decisions (id) VALUES ('historical')"))
    monkeypatch.setattr(cdb, 'engine', engine)
    cdb._migrate_add_routing_delegation_columns()
    cdb._migrate_add_routing_delegation_columns()
    with engine.connect() as db:
        assert db.execute(text('SELECT id, provider_health_json FROM routing_decisions')).all() == [('historical', None)]
    engine.dispose()


def test_durable_write_outcome_reports_provider_quota_without_lifecycle_change(quota_lane, monkeypatch):
    from types import SimpleNamespace
    from src import estate_write_lane as lane
    monkeypatch.setattr(client, 'worker_repo_probe', lambda *a, **kw: {'resolved': True})
    monkeypatch.setattr(lane, '_lease_authority', lambda *a: {'ok': True})
    def terminal_result(objective, *, decision_id, **kw):
        result = router._execute_codex_with_sandbox(objective, sandbox='workspace-write', provider='codex')
        lane._record_outcome(SimpleNamespace(decision_id=decision_id), 'failed', 'lab', result)
        return {'ok': True, 'lifecycle_state': 'failed', 'result': result, 'execution_id': 'execution'}
    monkeypatch.setattr(router, 'execute_write_via_worker', terminal_result)
    result = router.run_task({'task_class': 'code_implementation', 'repo': 'odysseus', 'objective': 'implement',
        'requirements': {'capabilities': ['code-strong']},
        'routing': {'allow_paid_escalation': True, 'mode': 'implementation'}})
    assert result['escalation_reason'] == 'provider_quota_exhausted'
    assert result['provider_health']['state'] == 'quota_exhausted'
    assert 'quota_exhausted' in result['reason']
    assert result['execution']['lifecycle_state'] == 'failed'
    assert router.provider_health('lab')['state'] == 'quota_exhausted'
    with cdb.get_db_session() as db:
        row = db.query(cdb.RoutingDecision).filter_by(id=result['decision_id']).one()
        assert row.escalation_reason == 'provider_quota_exhausted'
        assert json.loads(row.provider_health_json)['state'] == 'quota_exhausted'
