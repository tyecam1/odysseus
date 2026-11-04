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
    monkeypatch.setattr(router, "_PROVIDER_HEALTH_WRITE_FAILURES", {})
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
    if state.read_text().startswith('catalogue-error:'):
        print(state.read_text(), file=sys.stderr)
        sys.exit(1)
    print(json.dumps({{'models': [{{'slug': 'gpt-6.1-sol'}}]}}))
    sys.exit(0)
message = state.read_text()
if message == 'sleep':
    import time
    time.sleep(10)
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


@pytest.fixture
def quota_write_lease(quota_lane):
    with cdb.get_db_session() as db:
        db.add(cdb.ParkLease(id='lease', repo_id='odysseus', host_id='lab', status='active',
                            allowed_write_scope='repo', branch='feat/test', worktree_path='/w/test',
                            heartbeat_at=cdb.utcnow_naive()))


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


def test_repeated_dispatch_refused_without_starting_cli_or_write_admission(quota_lane, quota_write_lease, monkeypatch):
    from src import estate_write_lane as lane
    state, count, now = quota_lane
    _exhaust()
    before = count.read_text()
    assert _run_paid()['escalation_reason'] == 'provider_quota_exhausted'
    monkeypatch.setattr(lane, '_worker', lambda *a, **k: pytest.fail('write worker called'))
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


@pytest.mark.parametrize('mode', ['advisory', 'implementation'])
@pytest.mark.parametrize('cached_state', ['ok', 'unknown'])
def test_current_health_wins_race_after_route(quota_lane, quota_write_lease, monkeypatch, mode, cached_state):
    from src import estate_write_lane as lane
    state, count, now = quota_lane
    monkeypatch.setattr(client, 'worker_repo_probe', lambda *a, **k: {'resolved': True})
    resolve = router.resolve_route
    def raced_route(*args, **kwargs):
        route = resolve(*args, **kwargs)
        for host in route['hosts_checked']:
            host['providers'] = {'codex': {'provider': 'codex', 'state': cached_state,
                                         'retry_allowed': True, 'retry_after': None}}
        router._record_provider_health('lab', router._quota_observation(state.read_text()))
        return route
    monkeypatch.setattr(router, 'resolve_route', raced_route)
    monkeypatch.setattr(router, '_dispatch_read_only', lambda *a, **k: pytest.fail('paid worker dispatched'))
    monkeypatch.setattr(lane, '_worker', lambda *a, **k: pytest.fail('write worker called'))
    result = router.run_task({'task_class': 'code_review', 'objective': 'review', 'repo': 'odysseus',
        'requirements': {'capabilities': ['code-strong']},
        'routing': {'allow_paid_escalation': True, 'mode': mode}})
    assert result['executed'] is False
    assert result['escalation_reason'] == 'provider_quota_exhausted'
    assert not count.exists()


def test_dispatch_boundaries_check_health_without_wrapper(quota_lane, quota_write_lease, monkeypatch):
    from src import estate_write_lane as lane
    state, count, now = quota_lane
    router._record_provider_health('lab', router._quota_observation(state.read_text()))
    monkeypatch.setattr(client, 'call_worker', lambda *a, **k: pytest.fail('worker dispatched'))
    assert router._dispatch_read_only('lab', 'codex', {'objective': 'review'})['executed'] is False
    assert lane.execute_write_via_worker('implement', repo_id='odysseus', host_id='lab')['executed'] is False


def test_write_health_rechecked_after_worktree_verification(quota_lane, monkeypatch):
    from src import estate_write_lane as lane
    state, count, now = quota_lane
    with cdb.get_db_session() as db:
        db.add(cdb.ParkLease(id='lease', repo_id='odysseus', host_id='lab', status='active',
                            allowed_write_scope='repo', branch='feat/test', worktree_path='/w/test',
                            heartbeat_at=cdb.utcnow_naive()))
    def verify(*a, **k):
        router._record_provider_health('lab', router._quota_observation(state.read_text()))
        return {'ok': True, 'clean': True, 'head_sha': 'abc'}, None
    monkeypatch.setattr(lane, '_worker', verify)
    result = lane.execute_write_via_worker('implement', repo_id='odysseus', host_id='lab')
    assert result['executed'] is False
    assert result['escalation_reason'] == 'provider_quota_exhausted'
    with cdb.get_db_session() as db:
        assert db.query(cdb.EstateExecution).count() == 0


@pytest.mark.parametrize('payload', ['{bad', 'null', '[]', '{}', '',
    '{"provider":"codex","state":"ok","retry_after":"bad"}',
    '{"provider":"codex","state":"quota_exhausted","retry_after":null}'])
def test_unreadable_observation_blocks_paid_but_keeps_host_eligible(quota_lane, payload):
    with cdb.get_db_session() as db:
        db.add(cdb.RoutingDecision(id='bad-health', task_class='provider_health_observation',
            host_id='lab', executor='codex', status='complete', provider_health_json=payload))
    health = router.provider_health('lab')
    assert health['state'] == 'unknown_unreadable' and not health['retry_allowed']
    assert health['reason']
    result = _run_paid()
    assert result['executed'] is False
    assert result['escalation_reason'] == 'provider_unknown_unreadable'
    snapshot = preflight.delegation_preflight([{'task_class': 'code_review'}])
    assert not snapshot['snapshot']['codex']['available']
    assert snapshot['snapshot']['codex']['reason'] != 'live'
    assert snapshot['units'][0]['recommended_route'] is None
    assert snapshot['snapshot']['eligible_hosts'][0]['eligible']
    assert snapshot['snapshot']['eligible_hosts'][0]['healthy']


def test_health_query_failure_blocks_paid_dispatch(quota_lane, monkeypatch):
    from contextlib import contextmanager
    @contextmanager
    def broken():
        raise OSError('health database unavailable')
        yield
    monkeypatch.setattr(cdb, 'get_db_session', broken)
    health = router.provider_health('lab')
    assert health['state'] == 'unknown_unreadable'
    assert not health['retry_allowed']
    assert not router._codex_health('lab', {'available': True})['available']
    monkeypatch.setattr(client, 'call_worker', lambda *a, **k: pytest.fail('paid call'))
    assert router._dispatch_read_only('lab', 'codex', {'objective': 'review'})['executed'] is False


def test_failed_health_persistence_retries_pending_observation_and_recovers(quota_lane, monkeypatch):
    from contextlib import contextmanager
    state, count, now = quota_lane
    state.write_text('ok')
    assert _run_paid()['ok']
    now[0] += timedelta(seconds=1)
    real_session = cdb.get_db_session
    attempts = []
    @contextmanager
    def reject_observation():
        with real_session() as db:
            yield db
            if any(isinstance(row, cdb.RoutingDecision) and row.task_class == 'provider_health_observation'
                   for row in db.new):
                attempts.append('write')
                raise OSError('observation write failed')
    monkeypatch.setattr(cdb, 'get_db_session', reject_observation)
    state.write_text("You've hit your usage limit ... try again at 5:39 PM.")
    result = _run_paid()
    assert result['provider_health']['state'] == 'unknown_unreadable'
    assert 'unwritable' in result['provider_health']['reason']
    before = len(attempts)
    assert router.provider_health('lab')['retry_allowed'] is False
    assert len(attempts) == before + 1  # Bounded: one write attempt per read.
    before_calls = count.read_text()
    assert router._dispatch_read_only('lab', 'codex', {'objective': 'review'})['executed'] is False
    assert count.read_text() == before_calls
    monkeypatch.setattr(cdb, 'get_db_session', real_session)
    health = router.provider_health('lab')
    assert health['state'] == 'quota_exhausted'
    assert health['retry_after'] == '2026-11-04T17:39:00+00:00'
    assert health['observed_at'] == now[0].isoformat()
    assert ('lab', 'codex') not in router._PROVIDER_HEALTH_WRITE_FAILURES
    assert router.provider_health('lab') == health
    with real_session() as db:
        rows = db.query(cdb.RoutingDecision).filter_by(task_class='provider_health_observation').all()
        assert len(rows) == 2  # Original success plus exactly one retried failure.
        assert sum(json.loads(row.provider_health_json)['state'] == 'quota_exhausted' for row in rows) == 1
    before = count.read_text()
    assert _run_paid()['executed'] is False
    assert count.read_text() == before
    assert not preflight.delegation_preflight([{'task_class': 'code_review'}])['snapshot']['codex']['available']
    now[0] = datetime.fromisoformat(health['retry_after']) + timedelta(seconds=1)
    state.write_text('ok')
    assert _run_paid()['ok']
    assert router.provider_health('lab')['state'] == 'ok'


@pytest.mark.parametrize('message, expected', [
    ('authentication failed: invalid credentials', 'auth_failed'),
    ('HTTP 401 Unauthorized', 'auth_failed'),
    ('connection failed: connection refused', 'unreachable'),
    ('request timed out contacting provider', 'unreachable'),
])
def test_observed_failure_after_success_replaces_health(quota_lane, message, expected):
    state, count, now = quota_lane
    state.write_text('ok')
    assert _run_paid()['ok']
    assert router.provider_health('lab')['state'] == 'ok'
    now[0] += timedelta(seconds=1)
    state.write_text(message)
    result = _run_paid()
    assert result['provider_health']['state'] == expected
    assert result['escalation_reason'] == f'provider_{expected}'
    health = router.provider_health('lab')
    assert health['state'] == expected
    assert health['retry_after_source'] == 'bounded_backoff'
    assert datetime.fromisoformat(health['retry_after']) == now[0] + timedelta(seconds=900)
    snapshot = preflight.delegation_preflight([{'task_class': 'code_review'}])
    assert not snapshot['snapshot']['codex']['available']
    assert snapshot['snapshot']['codex']['reason'] != 'live'
    assert snapshot['units'][0]['recommended_route'] is None
    assert _run_paid()['executed'] is False
    now[0] += timedelta(seconds=901)
    assert router.provider_health('lab')['retry_allowed']
    assert not preflight.delegation_preflight([{'task_class': 'code_review'}])['snapshot']['codex']['available']
    state.write_text('ok')
    assert _run_paid()['ok']
    assert router.provider_health('lab')['state'] == 'ok'


def test_terminal_health_recovered_after_crash_once(quota_lane, monkeypatch):
    from src import estate_write_lane as lane
    state, count, now = quota_lane
    health = router._quota_observation(state.read_text())
    result = {'ok': False, 'provider_health': health, 'error': 'quota failure',
              'escalation_reason': 'provider_quota_exhausted'}
    with cdb.get_db_session() as db:
        db.add(cdb.EstateExecution(id='crashed', objective='implement', executor='codex-write', provider='codex',
            host_id='lab', repo_id='odysseus', lease_id='lease', branch='feat/test', worktree_path='/w/test',
            lifecycle_state='running', worktree_resolution='unresolved', worker_handle_json='{"pid": 123}'))
    original = lane._record_outcome
    def crash(*a, **k):
        raise RuntimeError('crash after terminal commit')
    monkeypatch.setattr(lane, '_record_outcome', crash)
    with pytest.raises(RuntimeError, match='crash after terminal commit'):
        lane._apply_view('crashed', {'state': 'failed', 'handle': {'pid': 123}, 'result': result})
    assert lane._load_row('crashed').lifecycle_state == 'failed'
    with cdb.get_db_session() as db:
        assert db.query(cdb.RoutingDecision).filter_by(task_class='provider_health_observation').count() == 0
    monkeypatch.setattr(lane, '_record_outcome', original)
    monkeypatch.setattr(lane, '_worker', lambda *a, **k: pytest.fail('terminal execution redispatched'))
    for _ in range(2):
        with cdb.get_db_session() as db:
            lane.reconcile_stale_estate_executions(db, cdb.EstateExecution)
    assert router.provider_health('lab')['state'] == 'quota_exhausted'
    with cdb.get_db_session() as db:
        rows = db.query(cdb.RoutingDecision).filter_by(task_class='provider_health_observation').all()
        assert len(rows) == 1
        assert json.loads(rows[0].provider_health_json)['observed_at'] == health['observed_at']


@pytest.mark.parametrize('message, expected', [
    ('catalogue-error: authentication failed', 'auth_failed'),
    ('catalogue-error: connection failed', 'unreachable'),
])
def test_catalogue_failure_after_success_changes_provider_state(quota_lane, message, expected):
    state, count, now = quota_lane
    state.write_text('ok')
    assert _run_paid()['ok']
    now[0] += timedelta(seconds=1)
    state.write_text(message)
    result = _run_paid()
    assert result['provider_health']['state'] == expected
    assert result['execution']['model_policy'] == 'fail_closed'
    assert router.provider_health('lab')['state'] == expected


def test_cli_timeout_after_success_records_unreachable(quota_lane, monkeypatch):
    state, count, now = quota_lane
    state.write_text('ok')
    assert _run_paid()['ok']
    now[0] += timedelta(seconds=1)
    state.write_text('sleep')
    monkeypatch.setattr(client, 'call_worker', lambda host, verb, payload, **kw: {
        'result': router.execute_codex(payload['objective'], timeout=0.05),
        'attestation': {'host_id': host},
    })
    result = _run_paid()
    assert result['provider_health']['state'] == 'unreachable'
    assert result['escalation_reason'] == 'provider_unreachable'
    assert router.provider_health('lab')['state'] == 'unreachable'
    assert _run_paid()['executed'] is False


@pytest.mark.parametrize('entry', ['lane', 'durable', 'run_task'])
@pytest.mark.parametrize('lifecycle', ['accepted', 'running', 'succeeded', 'failed', 'timed_out', 'interrupted', 'lost'])
def test_cooldown_preserves_existing_execution_response(quota_lane, quota_write_lease, monkeypatch, entry, lifecycle):
    from src import estate_write_lane as lane
    state, count, now = quota_lane
    with cdb.get_db_session() as db:
        db.add(cdb.EstateExecution(id='existing', objective='implement', executor='codex-write', provider='codex',
            host_id='lab', repo_id='odysseus', lease_id='lease', branch='feat/test', worktree_path='/w/test',
            lifecycle_state=lifecycle, worktree_resolution='unresolved', worker_handle_json='{"pid":123}'))
    monkeypatch.setattr(client, 'worker_repo_probe', lambda *a, **k: {'resolved': True})
    monkeypatch.setattr(lane, '_worker', lambda *a, **k: pytest.fail('existing execution caused worker call'))
    def submit():
        if entry == 'run_task':
            return router.run_task({'task_class': 'code_implementation', 'repo': 'odysseus', 'objective': 'implement',
                'requirements': {'capabilities': ['code-strong']},
                'routing': {'allow_paid_escalation': True, 'mode': 'implementation'}})['execution']
        execute = lane.execute_write_via_worker if entry == 'lane' else router.execute_codex_write_durable
        return execute('implement', repo_id='odysseus', host_id='lab')
    before = submit()
    assert before['execution_id'] == 'existing'
    assert before['lifecycle_state'] == lifecycle
    if lifecycle in ('accepted', 'running'):
        assert before['dispatch'] == 'reused_in_flight'
        assert 'GET /api/estate/run/existing' in before['next_action']['http']
    else:
        assert before['next_action']
        assert before['error_code'] == lane._UNRESOLVED_REFUSALS[lifecycle]
    router._record_provider_health('lab', router._quota_observation(state.read_text()))
    assert submit() == before
    assert not count.exists()
    with cdb.get_db_session() as db:
        assert db.query(cdb.EstateExecution).count() == 1
        assert db.query(cdb.EstateExecution).one().lifecycle_state == lifecycle


def test_concurrent_terminal_replay_validates_durable_winner(quota_lane, monkeypatch):
    from types import SimpleNamespace
    from src import estate_write_lane as lane
    state, count, now = quota_lane
    health = router._quota_observation(state.read_text())
    session_class = cdb.SessionLocal.class_
    real_add = session_class.add
    raced = []
    def insert_winner(db, row, *args, **kwargs):
        if isinstance(row, cdb.RoutingDecision) and row.task_class == 'provider_health_observation' and not raced:
            raced.append(row.id)
            # Commit between the loser's existence check and its INSERT.
            with cdb.get_db_session() as winner:
                winner.add(cdb.RoutingDecision(**{name: getattr(row, name) for name in (
                    'id', 'task_class', 'host_id', 'executor', 'created_at', 'provider_health_json',
                    'escalation_reason', 'status')}))
        return real_add(db, row, *args, **kwargs)
    monkeypatch.setattr(session_class, 'add', insert_winner)
    result = {'ok': False, 'provider_health': health, 'error': 'quota failure'}
    row = SimpleNamespace(id='race-execution', decision_id=None)
    lane._record_outcome(row, 'failed', 'lab', result)
    assert len(raced) == 1
    # A health-read retry must not mask a false write-failure latch.
    assert ('lab', 'codex') not in router._PROVIDER_HEALTH_WRITE_FAILURES
    assert router.provider_health('lab')['state'] == 'quota_exhausted'
    lane._record_outcome(row, 'failed', 'lab', result)
    with cdb.get_db_session() as db:
        rows = db.query(cdb.RoutingDecision).filter_by(task_class='provider_health_observation').all()
        assert len(rows) == 1
        assert json.loads(rows[0].provider_health_json) == health


@pytest.mark.parametrize('conflict', ['payload', 'host', 'provider', 'task_class'])
def test_replayed_observation_id_must_match_payload_and_scope(quota_lane, conflict):
    state, count, now = quota_lane
    health = router._quota_observation(state.read_text())
    values = dict(id='conflicting', task_class='provider_health_observation', host_id='lab',
                  executor='codex', provider_health_json=json.dumps(health), status='blocked')
    if conflict == 'payload':
        values['provider_health_json'] = json.dumps({**health, 'reason': 'different observation'})
    else:
        values[{'host': 'host_id', 'provider': 'executor', 'task_class': 'task_class'}[conflict]] = 'other'
    with cdb.get_db_session() as db:
        db.add(cdb.RoutingDecision(**values))
    result = router._record_provider_health('lab', health, observation_id='conflicting')
    assert result['state'] == 'unknown_unreadable'
    assert router.provider_health('lab')['retry_allowed'] is False
