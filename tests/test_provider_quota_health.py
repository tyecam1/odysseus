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


def test_retry_cannot_delete_newer_pending_failure(quota_lane, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from contextlib import contextmanager
    import threading

    state, count, now = quota_lane
    older = router._quota_observation(state.read_text())
    now[0] += timedelta(hours=1)  # A's cooldown has expired; losing B would admit paid work.
    newer = router._quota_observation(state.read_text())
    key = ('lab', 'codex')
    real_session = cdb.get_db_session
    persisted = threading.Event()
    replace = threading.Event()
    replacement_ready = threading.Event()
    real_lock = threading.Lock()

    class ObservedLock:
        def __enter__(self):
            if threading.current_thread().name == 'newer-failure':
                replacement_ready.set()  # B has failed its write and reached the latch.
            real_lock.acquire()
        def __exit__(self, *args):
            real_lock.release()

    class InterleavedPending(dict):
        def get(self, k, default=None):
            previous = super().get(k, default)
            if threading.current_thread().name == 'retry' and persisted.is_set() and not replace.is_set():
                replace.set()  # A captured previous; let B try replacing it before A pops.
                assert replacement_ready.wait(5)
            return previous
        def __setitem__(self, k, value):
            super().__setitem__(k, value)
            if threading.current_thread().name == 'newer-failure':
                replacement_ready.set()  # Unlocked implementation: B replaces before A pops.

    pending = InterleavedPending({key: {
        'observation': older, 'observation_id': 'retry-a',
        'failure': router._unreadable_provider_health('codex', 'pending A'),
    }})
    monkeypatch.setattr(router, '_PROVIDER_HEALTH_WRITE_FAILURES', pending)
    monkeypatch.setattr(router, '_PROVIDER_HEALTH_LOCK', ObservedLock(), raising=False)

    @contextmanager
    def interleaved_session():
        if threading.current_thread().name == 'newer-failure':
            raise OSError('B cannot persist')
        with real_session() as db:
            yield db
        if threading.current_thread().name == 'retry':
            persisted.set()
    monkeypatch.setattr(cdb, 'get_db_session', interleaved_session)

    def retry():
        threading.current_thread().name = 'retry'
        return router.provider_health('lab')
    def fail_newer():
        threading.current_thread().name = 'newer-failure'
        assert replace.wait(5)
        return router._record_provider_health('lab', newer, observation_id='failed-b')
    with ThreadPoolExecutor(max_workers=2) as pool:
        retry_result = pool.submit(retry)
        newer_result = pool.submit(fail_newer)
        retry_result.result(timeout=10)
        assert newer_result.result(timeout=10)['state'] == 'unknown_unreadable'
    assert pending[key]['observation_id'] == 'failed-b'

    @contextmanager
    def still_unwritable():
        raise OSError('B still cannot persist')
        yield
    monkeypatch.setattr(cdb, 'get_db_session', still_unwritable)
    health = router.provider_health('lab')
    assert health['state'] == 'unknown_unreadable' and not health['retry_allowed']
    assert router._dispatch_read_only('lab', 'codex', {'objective': 'review'})['executed'] is False
    assert not count.exists()


@pytest.mark.parametrize('state, field', [
    (state, field) for state, fields in [
        ('ok', ('provider', 'state', 'observed_at', 'reason', 'retry_after')),
        ('quota_exhausted', ('provider', 'state', 'observed_at', 'reason', 'retry_after', 'retry_after_source')),
    ] for field in fields
])
def test_incomplete_observation_fails_closed(quota_lane, state, field):
    message, count, now = quota_lane
    health = router._quota_observation(message.read_text())
    if state == 'ok':
        health.update(state='ok', retry_after=None)
        health.pop('retry_after_source')
    del health[field]
    with cdb.get_db_session() as db:
        db.add(cdb.RoutingDecision(id='incomplete', task_class='provider_health_observation',
            host_id='lab', executor='codex', status='complete', provider_health_json=json.dumps(health)))
    health = router.provider_health('lab')
    assert health['state'] == 'unknown_unreadable' and not health['retry_allowed']
    assert _run_paid()['escalation_reason'] == 'provider_unknown_unreadable'
    assert not preflight.delegation_preflight([{'task_class': 'code_review'}])['snapshot']['codex']['available']
    assert not count.exists()


@pytest.mark.parametrize('entry', ['read_only', 'routed', 'write', 'durable', 'routed_write', 'record'])
@pytest.mark.parametrize('mutation', [
    *[f'missing:{field}' for field in (
        'provider', 'state', 'observed_at', 'reason', 'retry_after', 'retry_after_source')],
    *[f'type:{field}' for field in (
        'provider', 'state', 'observed_at', 'reason', 'retry_after', 'retry_after_source')],
    'scope', 'payload:null', 'payload:false', 'payload:zero', 'payload:string',
    'payload:list', 'payload:nonempty_list', 'payload:empty_dict',
])
def test_malformed_worker_health_closes_next_paid_dispatch(
        quota_lane, quota_write_lease, monkeypatch, entry, mutation):
    from src import estate_write_lane as lane
    message, count, now = quota_lane
    router._record_provider_health('lab', {
        'provider': 'codex', 'state': 'ok', 'retry_after': None,
        'observed_at': now[0].isoformat(), 'reason': 'successful execution',
    })
    assert router.provider_health('lab')['state'] == 'ok'
    now[0] += timedelta(seconds=1)
    health = router._quota_observation(message.read_text())
    kind, _, field = mutation.partition(':')
    if kind == 'missing':
        del health[field]
    elif kind == 'type':
        health[field] = []  # Includes unhashable provider/state/source values.
    elif kind == 'scope':
        health['provider'] = 'other-provider'
    else:
        health = {'null': None, 'false': False, 'zero': 0, 'string': 'bad',
                  'list': [], 'nonempty_list': ['bad'], 'empty_dict': {}}[field]
    result = {'ok': False, 'provider_health': health, 'error': 'quota evidence'}
    calls = []
    def read_worker(host, verb, payload, **kwargs):
        calls.append(verb)
        return {'result': result, 'attestation': {'host_id': host}}
    def write_worker(host, verb, payload, **kwargs):
        if verb == 'worktree.verify':
            return {'ok': True, 'clean': True, 'head_sha': 'abc'}, None
        assert verb == 'start'
        calls.append(verb)
        return {'state': 'failed', 'handle': {'pid': 123}, 'result': result}, None
    monkeypatch.setattr(client, 'call_worker', read_worker)
    monkeypatch.setattr(client, 'worker_repo_probe', lambda *a, **k: {'resolved': True})
    monkeypatch.setattr(lane, '_worker', write_worker)
    if entry == 'read_only':
        outcome = router._dispatch_read_only('lab', 'codex', {'objective': 'review'})
    elif entry == 'routed':
        outcome = _run_paid()
    elif entry == 'record':
        outcome = {'provider_health': router._record_provider_health('lab', health)}
    elif entry == 'routed_write':
        outcome = router.run_task({'task_class': 'code_implementation', 'repo': 'odysseus',
            'objective': 'implement', 'requirements': {'capabilities': ['code-strong']},
            'routing': {'allow_paid_escalation': True, 'mode': 'implementation'}})
    else:
        execute = lane.execute_write_via_worker if entry == 'write' else router.execute_codex_write_durable
        outcome = execute('implement', repo_id='odysseus', host_id='lab')
    returned_health = outcome.get('provider_health') or outcome['result']['provider_health']
    assert returned_health['state'] == 'unknown_unreadable'
    assert returned_health['reason'] and returned_health['retry_allowed'] is False
    assert len(calls) == (0 if entry == 'record' else 1)
    # Clear only the test execution's worktree blocker so the next write reaches
    # the provider gate, rather than the existing-execution recovery response.
    with cdb.get_db_session() as db:
        db.query(cdb.EstateExecution).update({'worktree_resolution': 'finalized'})
    monkeypatch.setattr(client, 'call_worker', lambda *a, **k: pytest.fail('next paid read dispatched'))
    monkeypatch.setattr(lane, '_worker', lambda *a, **k: pytest.fail('next paid write dispatched'))
    for refused in (_run_paid(), router._dispatch_read_only('lab', 'codex', {'objective': 'review'}),
                    lane.execute_write_via_worker('implement', repo_id='odysseus', host_id='lab')):
        assert refused['executed'] is False
        assert refused['escalation_reason'] == 'provider_unknown_unreadable'
        assert refused['provider_health']['reason']
    assert router.provider_health('other-host')['state'] == 'unknown'
    assert router.provider_health('lab', 'other-provider')['state'] == 'unknown'
    assert not count.exists()


@pytest.mark.parametrize('field, value', [
    ('provider', None), ('provider', 1), ('state', ['ok']), ('state', 'unknown'),
    ('state', 'unknown_unreadable'), ('state', 'invalid'), ('reason', None), ('reason', 1), ('reason', ''),
    ('observed_at', None), ('observed_at', 1), ('observed_at', 'bad'),
    ('observed_at', '2026-11-04T17:00:00'),
    ('retry_after', 1), ('retry_after', []), ('retry_after', 'bad'),
    ('retry_after', '2026-11-04T17:39:00'), ('retry_after', '2026-11-04T16:00:00Z'),
    ('retry_after_source', None), ('retry_after_source', []), ('retry_after_source', 'guess'),
])
def test_invalid_observation_fields_fail_closed(quota_lane, field, value):
    message, count, now = quota_lane
    health = router._quota_observation(message.read_text())
    health[field] = value
    with cdb.get_db_session() as db:
        db.add(cdb.RoutingDecision(id='invalid', task_class='provider_health_observation',
            host_id='lab', executor='codex', status='complete', provider_health_json=json.dumps(health)))
    health = router.provider_health('lab')
    assert health['state'] == 'unknown_unreadable' and not health['retry_allowed']


@pytest.mark.parametrize('unrecorded', [0, 23])
def test_terminal_replay_all_rows_bounded_newest_finished_first(quota_lane, monkeypatch, unrecorded):
    from src import estate_write_lane as lane
    message, count, now = quota_lane
    health = router._quota_observation(message.read_text())
    with cdb.get_db_session() as db:
        # Include old results without provider telemetry: they must not starve recovery.
        for i in reversed(range(100 + unrecorded + 15)):
            result = {'ok': False, 'provider_health': health} if i < 100 + unrecorded else {'ok': False}
            row = cdb.EstateExecution(id=f'terminal-{i:03}', objective='implement', executor='codex-write',
                provider='codex', host_id='lab', repo_id='odysseus', lease_id='lease', branch='feat/test',
                worktree_path='/w/test', lifecycle_state='failed', worktree_resolution='finalized',
                submitted_at=(now[0] + timedelta(seconds=i)).replace(tzinfo=None),
                finished_at=(now[0] + timedelta(seconds=i)).replace(tzinfo=None), result_json=json.dumps(result))
            db.add(row)
            if i < 100:
                lane._record_outcome(row, 'failed', 'lab', result)

    replayed = []
    record = router._record_provider_health
    def replay(host, health, *, observation_id, **kwargs):
        replayed.append(observation_id.removeprefix('provider-health:'))
        return record(host, health, observation_id=observation_id, **kwargs)
    monkeypatch.setattr(router, '_record_provider_health', replay)
    monkeypatch.setattr(lane, '_worker', lambda *a, **k: pytest.fail('terminal replay called worker'))
    # The production limit is ten; assert the externally visible bound as well.
    for sweep in range((100 + unrecorded + 15 + 9) // 10):
        before = len(replayed)
        with cdb.get_db_session() as db:
            lane.reconcile_stale_estate_executions(db, cdb.EstateExecution)
        visited = range(max(0, 100 + unrecorded + 15 - (sweep + 1) * 10),
                        max(0, 100 + unrecorded + 15 - sweep * 10))
        assert len(replayed) - before == sum(100 <= i < 100 + unrecorded for i in visited)
        with cdb.get_db_session() as db:
            assert db.query(cdb.RoutingDecision).filter_by(task_class='provider_health_replay').count() == min(
                (sweep + 1) * 10, 100 + unrecorded + 15)
    assert replayed == [f'terminal-{i:03}' for i in reversed(range(100, 100 + unrecorded))]
    with cdb.get_db_session() as db:
        rows = db.query(cdb.RoutingDecision).filter_by(task_class='provider_health_observation').all()
        assert len(rows) == 100 + unrecorded
        assert all(json.loads(row.provider_health_json)['observed_at'] == health['observed_at'] for row in rows)


def test_replay_backlog_blocks_health_and_paid_admission(quota_lane, quota_write_lease, monkeypatch):
    from src import estate_write_lane as lane
    message, count, now = quota_lane
    quota = router._quota_observation(message.read_text())
    with cdb.get_db_session() as db:
        # The newest quota failure is recorded in the first batch; remaining evidence still closes admission.
        for i in range(11):
            health = quota if i == 10 else {
                'provider': 'codex', 'state': 'ok', 'retry_after': None,
                'observed_at': (now[0] - timedelta(seconds=11 - i)).isoformat(),
                'reason': 'successful execution',
            }
            db.add(cdb.EstateExecution(id=f'backlog-{i:02}', objective='implement', executor='codex-write',
                provider='codex', host_id='lab', repo_id='odysseus', lease_id='lease', branch='feat/test',
                worktree_path='/w/test', lifecycle_state='failed' if i == 10 else 'succeeded',
                worktree_resolution='finalized', finished_at=(now[0] + timedelta(seconds=i)).replace(tzinfo=None),
                result_json=json.dumps({'ok': i < 10, 'provider_health': health})))
    monkeypatch.setattr(lane, '_worker', lambda *a, **k: pytest.fail('write worker called'))
    monkeypatch.setattr(client, 'call_worker', lambda *a, **k: pytest.fail('paid worker called'))
    with cdb.get_db_session() as db:
        lane.reconcile_stale_estate_executions(db, cdb.EstateExecution)
    health = router.provider_health('lab')
    assert health['state'] == 'unknown_unreadable' and not health['retry_allowed']
    assert health['reason'] == 'observation backlog'
    assert router.provider_health('other-worker')['state'] == 'unknown'
    assert router.provider_health('lab', 'other-provider')['state'] == 'unknown'
    assert _run_paid()['executed'] is False
    assert router._dispatch_read_only('lab', 'codex', {'objective': 'review'})['executed'] is False
    assert lane.execute_write_via_worker('implement', repo_id='odysseus', host_id='lab')['executed'] is False
    assert not preflight.delegation_preflight([{'task_class': 'code_review'}])['snapshot']['codex']['available']
    with cdb.get_db_session() as db:
        assert db.query(cdb.RoutingDecision).filter_by(task_class='provider_health_observation').count() == 10
        assert db.query(cdb.EstateExecution).count() == 11  # No new write admission.
        lane.reconcile_stale_estate_executions(db, cdb.EstateExecution)
    health = router.provider_health('lab')
    assert health['state'] == 'quota_exhausted' and not health['retry_allowed']
    assert health['retry_after'] == quota['retry_after']
    assert not count.exists()


def test_empty_terminal_payloads_cannot_starve_quota_replay(quota_lane, monkeypatch):
    from src import estate_write_lane as lane
    message, count, now = quota_lane
    quota = router._quota_observation(message.read_text())
    with cdb.get_db_session() as db:
        for i in range(24):
            # More than two batches of genuinely absent observations, including whitespace.
            payload = ' { \n } ' if i < 23 else json.dumps({'provider_health': quota})
            db.add(cdb.EstateExecution(id=f'empty-{i:02}', objective='implement', executor='codex-write',
                provider='codex', host_id='lab', repo_id='odysseus', lease_id='lease', branch='feat/test',
                worktree_path='/w/test', lifecycle_state='failed', worktree_resolution='finalized',
                finished_at=(now[0] + timedelta(seconds=i)).replace(tzinfo=None), result_json=payload))
    monkeypatch.setattr(lane, '_worker', lambda *a, **k: pytest.fail('terminal replay called worker'))
    for _ in range(3):
        with cdb.get_db_session() as db:
            lane.reconcile_stale_estate_executions(db, cdb.EstateExecution)
    with cdb.get_db_session() as db:
        row = db.query(cdb.RoutingDecision).filter_by(task_class='provider_health_observation').one()
        assert row.id == 'provider-health:empty-23'
        assert json.loads(row.provider_health_json) == quota
    health = router.provider_health('lab')
    assert health['state'] == 'quota_exhausted' and not health['retry_allowed']
    assert not count.exists()


@pytest.mark.parametrize('payload', [
    {'provider_health': value} for value in (
        [], False, 0, '', {}, None, 'bad', 1, ['bad'], {'state': 'ok'},
    )
] + [{}, [], False, None, '{bad'])
def test_unusable_terminal_replay_cannot_starve_another_host(quota_lane, monkeypatch, payload):
    from src import estate_write_lane as lane
    message, count, now = quota_lane
    quota = router._quota_observation(message.read_text())
    with cdb.get_db_session() as db:
        for i in range(24):
            result = {'provider_health': quota} if i == 23 else payload
            db.add(cdb.EstateExecution(id=f'malformed-{i:02}', objective='implement', executor='codex-write',
                provider='codex', host_id='lab' if i == 23 else 'bad-host', repo_id='odysseus',
                lease_id='lease', branch='feat/test', worktree_path='/w/test', lifecycle_state='failed',
                worktree_resolution='finalized', finished_at=(now[0] + timedelta(seconds=i)).replace(tzinfo=None),
                result_json=result if result == '{bad' else json.dumps(result)))
    monkeypatch.setattr(lane, '_worker', lambda *a, **k: pytest.fail('terminal replay called worker'))
    for sweep in range(3):
        with cdb.get_db_session() as db:
            lane.reconcile_stale_estate_executions(db, cdb.EstateExecution)
        with cdb.get_db_session() as db:
            assert db.query(cdb.RoutingDecision).filter_by(task_class='provider_health_replay').count() == min((sweep + 1) * 10, 24)
            observation = db.query(cdb.RoutingDecision).filter_by(task_class='provider_health_observation').one()
            assert observation.id == 'provider-health:malformed-23'
            assert json.loads(observation.provider_health_json) == quota
            if sweep == 2:
                disposition = 'no_observation' if payload == {} else 'unpersistable'
                assert db.query(cdb.RoutingDecision).filter_by(
                    task_class='provider_health_replay', escalation_reason=disposition,
                    host_id='bad-host', executor='codex',
                ).count() == 23
                assert lane._unrecorded_provider_health(db, cdb.EstateExecution).count() == 0
        assert router.provider_health('bad-host')['state'] == ('unknown' if payload == {} else 'unknown_unreadable')
        assert router.provider_health('lab')['state'] == 'quota_exhausted'
        assert router.provider_health('lab', 'other-provider')['state'] == 'unknown'
    assert not count.exists()


@pytest.mark.parametrize('conflict', ['state', 'retry_after'])
def test_terminal_reconciliation_detects_recorded_payload_conflict(quota_lane, monkeypatch, conflict):
    from src import estate_write_lane as lane
    message, count, now = quota_lane
    quota = router._quota_observation(message.read_text())
    recorded = {**quota}
    if conflict == 'state':
        recorded.update(state='ok', retry_after=None)
        recorded.pop('retry_after_source')
    else:
        recorded['retry_after'] = (now[0] + timedelta(minutes=20)).isoformat()
    with cdb.get_db_session() as db:
        db.add(cdb.RoutingDecision(id='provider-health:conflict-terminal',
            task_class='provider_health_observation', host_id='lab', executor='codex',
            status='complete', provider_health_json=json.dumps(recorded)))
        db.add(cdb.EstateExecution(id='conflict-terminal', objective='implement', executor='codex-write',
            provider='codex', host_id='lab', repo_id='odysseus', lease_id='lease', branch='feat/test',
            worktree_path='/w/test', lifecycle_state='failed', worktree_resolution='finalized',
            finished_at=now[0].replace(tzinfo=None), result_json=json.dumps({'provider_health': quota})))
    monkeypatch.setattr(lane, '_worker', lambda *a, **k: pytest.fail('terminal replay called worker'))
    with cdb.get_db_session() as db:
        lane.reconcile_stale_estate_executions(db, cdb.EstateExecution)
    # A restart must not restore the conflicting persisted success.
    router._PROVIDER_HEALTH_WRITE_FAILURES.clear()
    health = router.provider_health('lab')
    assert health['state'] == 'unknown_unreadable' and not health['retry_allowed']
    assert 'conflict' in health['reason']
    assert _run_paid()['executed'] is False
    assert router.provider_health('other-host')['state'] == 'unknown'
    assert router.provider_health('lab', 'other-provider')['state'] == 'unknown'
    assert not count.exists()


def _replay_execution(execution_id, payload, submitted_at, **kwargs):
    return cdb.EstateExecution(id=execution_id, objective='implement', executor='codex-write',
        provider='codex', host_id=kwargs.pop('host_id', 'lab'), repo_id='odysseus', lease_id='lease',
        branch='feat/test', worktree_path='/w/test', lifecycle_state='failed',
        worktree_resolution='finalized', submitted_at=submitted_at,
        finished_at=kwargs.pop('finished_at', submitted_at), result_json=payload, **kwargs)


@pytest.mark.parametrize('elapsed', [timedelta(hours=25), timedelta(days=6)])
def test_week_long_quota_survives_crash_and_delayed_replay(quota_lane, quota_write_lease, monkeypatch, elapsed):
    from src import estate_write_lane as lane
    message, count, now = quota_lane
    start = now[0]
    monkeypatch.setattr(lane, '_now', lambda: now[0].replace(tzinfo=None))
    health = router._quota_observation("You've hit your usage limit ... try again at 2026-11-11T17:00:00Z.")
    assert datetime.fromisoformat(health['retry_after']) == start + timedelta(days=7)
    with cdb.get_db_session() as db:
        row = _replay_execution('week-crash', None, start.replace(tzinfo=None))
        row.lifecycle_state, row.worktree_resolution, row.finished_at = 'running', 'unresolved', None
        db.add(row)
    record = lane._record_outcome
    def crash(*a, **k):
        raise RuntimeError('crash before observation persistence')
    monkeypatch.setattr(lane, '_record_outcome', crash)
    with pytest.raises(RuntimeError, match='crash before observation persistence'):
        lane._apply_view('week-crash', {'state': 'failed', 'handle': {'pid': 123},
                                     'result': {'provider_health': health}})
    monkeypatch.setattr(lane, '_record_outcome', record)
    # Finalized work allows a fresh write admission to reach the capacity gate.
    with cdb.get_db_session() as db:
        db.query(cdb.EstateExecution).filter_by(id='week-crash').update({
            'worktree_resolution': 'finalized', 'spool_released_at': start.replace(tzinfo=None)})
        assert db.query(cdb.RoutingDecision).filter_by(task_class='provider_health_observation').count() == 0
    now[0] = start + elapsed
    monkeypatch.setattr(client, 'call_worker', lambda *a, **k: pytest.fail('paid worker called'))
    monkeypatch.setattr(lane, '_worker', lambda *a, **k: pytest.fail('write worker called'))
    for reconciled in (False, True):
        if reconciled:
            with cdb.get_db_session() as db:
                lane.reconcile_stale_estate_executions(db, cdb.EstateExecution)
            router._PROVIDER_HEALTH_WRITE_FAILURES.clear()  # Simulate restart.
        assert not router.provider_health('lab')['retry_allowed']
        assert _run_paid()['executed'] is False
        assert lane.execute_write_via_worker('implement', repo_id='odysseus', host_id='lab')['executed'] is False
    assert router.provider_health('lab')['retry_after'] == health['retry_after']
    now[0] = start + timedelta(days=7)
    assert router.provider_health('lab')['retry_allowed']
    assert not count.exists()


def test_unreadable_week_long_evidence_stays_closed_through_replay_horizon(quota_lane, monkeypatch):
    from src import estate_write_lane as lane
    message, count, now = quota_lane
    start = now[0]
    health = router._quota_observation("You've hit your usage limit ... try again at 2026-11-11T17:00:00Z.")
    # A truncated result retains a reset but cannot be safely recovered.
    payload = json.dumps({'provider_health': health})[:-1]
    with cdb.get_db_session() as db:
        db.add(_replay_execution('unreadable-week', payload, start.replace(tzinfo=None)))
    with cdb.get_db_session() as db:
        lane.reconcile_stale_estate_executions(db, cdb.EstateExecution)
    with cdb.get_db_session() as db:
        assert db.query(cdb.RoutingDecision).filter_by(id='provider-health-replay:unreadable-week').one().escalation_reason == 'unpersistable'
    monkeypatch.setattr(client, 'call_worker', lambda *a, **k: pytest.fail('paid worker called'))
    for elapsed in (timedelta(hours=25), timedelta(days=6), timedelta(days=7)):
        now[0] = start + elapsed
        router._PROVIDER_HEALTH_WRITE_FAILURES.clear()
        health = router.provider_health('lab')
        assert health['state'] == 'unknown_unreadable' and not health['retry_allowed']
        assert _run_paid()['executed'] is False
    now[0] = start + lane.REPLAY_HORIZON + timedelta(seconds=1)
    assert router.provider_health('lab')['retry_allowed']
    assert not count.exists()


@pytest.mark.parametrize('reset', ['2026-11-12T17:00:00Z', '9999-12-31T23:59:59-23:59'])
def test_reset_beyond_max_cooldown_is_capped_without_overflow(quota_lane, reset):
    message, count, now = quota_lane
    health = router._quota_observation(f"You've hit your usage limit ... try again at {reset}.")
    assert datetime.fromisoformat(health['retry_after']) == now[0] + timedelta(days=7)
    assert health['retry_after_source'] == 'bounded_cap'
    assert 'cap' in health['reason']
    router._validate_provider_payload(health)
    router._record_provider_health('lab', health)
    now[0] += timedelta(days=7)
    assert router.provider_health('lab')['retry_allowed']


def test_accepted_payload_cannot_exceed_max_cooldown(quota_lane):
    message, count, now = quota_lane
    health = router._quota_observation(message.read_text())
    health['retry_after'] = (now[0] + timedelta(days=8)).isoformat()
    with pytest.raises(ValueError, match='maximum cooldown'):
        router._validate_provider_payload(health)
    assert router._record_provider_health('lab', health)['state'] == 'unknown_unreadable'


@pytest.mark.parametrize('payload', [
    '{"provider_health":' + '[' * 100000,
    '{"provider_health":' + '[' * 100 + '0' + ']' * 100 + '}',
    '{"output":"' + 'x' * (1024 * 1024) + '"}',
    b'{"provider_health":"\xff"}', '{bad',
], ids=['deep', 'depth-bound', 'oversize', 'invalid-utf8', 'invalid-json'])
def test_bounded_malformed_replay_isolated_and_disposed(quota_lane, monkeypatch, payload):
    from src import estate_write_lane as lane
    message, count, now = quota_lane
    quota = router._quota_observation(message.read_text())
    with cdb.get_db_session() as db:
        db.add(_replay_execution('bad', payload, now[0].replace(tzinfo=None), host_id='bad-host'))
        db.add(_replay_execution('good', json.dumps({'provider_health': quota}),
                                (now[0] + timedelta(seconds=1)).replace(tzinfo=None)))
    # Bounds must be enforced before calling the decoder, even for otherwise valid JSON.
    loads = lane.json.loads
    parsed_bad = []
    def bounded_loads(raw, *args, **kwargs):
        if raw == payload:
            parsed_bad.append(raw)
        return loads(raw, *args, **kwargs)
    if isinstance(payload, str) and (len(payload) > 1024 * 1024 or payload.count('[') > 64):
        monkeypatch.setattr(lane.json, 'loads', bounded_loads)
    monkeypatch.setattr(lane, '_worker', lambda *a, **k: pytest.fail('terminal replay called worker'))
    for _ in range(3):
        with cdb.get_db_session() as db:
            lane.reconcile_stale_estate_executions(db, cdb.EstateExecution)
        with cdb.get_db_session() as db:
            assert db.query(cdb.RoutingDecision).filter_by(id='provider-health-replay:bad').one().escalation_reason == 'unpersistable'
            assert db.query(cdb.RoutingDecision).filter_by(id='provider-health:good').count() == 1
        assert router.provider_health('lab')['state'] == 'quota_exhausted'
    assert not parsed_bad, 'unusable raw payload reached JSON parser'


@pytest.mark.parametrize('error', [RecursionError, MemoryError, ValueError, TypeError])
def test_replay_validation_exception_is_row_local(quota_lane, monkeypatch, error):
    from src import estate_write_lane as lane
    message, count, now = quota_lane
    quota = router._quota_observation(message.read_text())
    bad = {**quota, 'reason': 'raise on this row'}
    with cdb.get_db_session() as db:
        db.add(_replay_execution('bad', json.dumps({'provider_health': bad}), now[0].replace(tzinfo=None), host_id='bad-host'))
        db.add(_replay_execution('good', json.dumps({'provider_health': quota}), now[0].replace(tzinfo=None)))
    validate = router._validate_provider_payload
    def validate_row(health):
        if health.get('reason') == bad['reason']:
            raise error('invalid row')
        return validate(health)
    monkeypatch.setattr(router, '_validate_provider_payload', validate_row)
    with cdb.get_db_session() as db:
        lane.reconcile_stale_estate_executions(db, cdb.EstateExecution)
        assert db.query(cdb.RoutingDecision).filter_by(id='provider-health-replay:bad').one().escalation_reason == 'unpersistable'
    assert router.provider_health('lab')['state'] == 'quota_exhausted'


def test_expired_legacy_history_not_backfilled_and_live_progress_continues(quota_lane, monkeypatch):
    from sqlalchemy import event
    from src import estate_write_lane as lane
    message, count, now = quota_lane
    start = now[0].replace(tzinfo=None)
    with cdb.get_db_session() as db:
        db.add_all([_replay_execution(f'legacy-{i:05}', '{}', start - lane.REPLAY_HORIZON - timedelta(days=1, seconds=i))
                    for i in range(5000)])
        db.add(cdb.EstateExecution(id='live', objective='implement', executor='codex-write',
            provider='codex', host_id='lab', repo_id='odysseus', lease_id='lease', branch='feat/test',
            worktree_path='/w/test', lifecycle_state='running', worktree_resolution='unresolved',
            worker_handle_json='{"pid":123}'))
    observed = []
    def worker(host, verb, payload, **kwargs):
        observed.append((verb, payload['execution_id']))
        return {'state': 'unknown'}, None
    monkeypatch.setattr(lane, '_worker', worker)
    statements = []
    engine = cdb.SessionLocal.kw['bind']
    def executed(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)
    event.listen(engine, 'before_cursor_execute', executed)
    try:
        # Legacy-only history must be cheap even before any dispositions exist.
        assert router.provider_health('lab')['state'] == 'unknown'
        assert len(statements) <= 5
        for sweep in range(2):
            statements.clear()
            with cdb.get_db_session() as db:
                lane.reconcile_stale_estate_executions(db, cdb.EstateExecution)
            assert len(statements) <= 20
            if sweep == 0:
                assert observed == [('status', 'live')]
                with cdb.get_db_session() as db:
                    assert db.query(cdb.RoutingDecision).filter_by(task_class='provider_health_replay').count() == 0
        with cdb.get_db_session() as db:
            assert lane._unrecorded_provider_health(db, cdb.EstateExecution).count() == 0
            assert db.query(cdb.RoutingDecision).filter_by(task_class='provider_health_replay').count() == 0
            assert db.query(cdb.EstateExecution).filter_by(provider_health_replay_handled=True).count() == 0
        statements.clear()
        assert router.provider_health('lab')['state'] == 'unknown'
        assert len(statements) <= 5
    finally:
        event.remove(engine, 'before_cursor_execute', executed)


def test_replay_cursor_uses_index_and_crosses_tied_pages(quota_lane):
    from sqlalchemy import event, text
    from src import estate_write_lane as lane
    message, count, now = quota_lane
    engine = cdb.SessionLocal.kw['bind']
    # Exercise the existing-table migration as well as metadata on a fresh DB.
    with engine.begin() as conn:
        conn.execute(text('DROP INDEX ix_estate_executions_replay_cursor'))
        conn.execute(text('CREATE INDEX ix_estate_executions_replay_cursor ON estate_executions (lifecycle_state, submitted_at, id)'))
    original_engine = cdb.engine
    try:
        cdb.engine = engine
        cdb._migrate_add_estate_execution_worker_columns()
        cdb._migrate_add_estate_execution_worker_columns()
    finally:
        cdb.engine = original_engine
    with cdb.get_db_session() as db:
        for i in reversed(range(25)):
            row = _replay_execution(f'tied-{i:02}', '{}', now[0].replace(tzinfo=None))
            row.lifecycle_state = lane._TERMINAL[i % 3]
            db.add(row)
    plans = []
    def executed(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith('SELECT estate_executions.') and 'ORDER BY' in statement:
            plans.extend(conn.exec_driver_sql('EXPLAIN QUERY PLAN ' + statement, parameters).all())
    event.listen(engine, 'before_cursor_execute', executed)
    try:
        with cdb.get_db_session() as db:
            rows = list(lane._provider_health_replay_pages(
                lane._unrecorded_provider_health(db, cdb.EstateExecution), cdb.EstateExecution, max_rows=23))
            assert [row.id for row in rows] == [f'tied-{i:02}' for i in range(24, 1, -1)]
        assert any('ix_estate_executions_replay_cursor' in row[-1] for row in plans)
        assert not any('TEMP B-TREE' in row[-1] for row in plans)
    finally:
        event.remove(engine, 'before_cursor_execute', executed)


@pytest.mark.parametrize('escaped_key', [False, True])
@pytest.mark.parametrize('as_bytes', [False, True])
def test_health_backlog_finds_valid_observation_after_legacy_rows(quota_lane, escaped_key, as_bytes):
    message, count, now = quota_lane
    quota = router._quota_observation(message.read_text())
    # Brackets and escaped quotes in strings must not count toward JSON depth.
    quota['reason'] += ' [' * 100 + ' \\"quoted"'
    payload = json.dumps({'provider_health': quota})
    if escaped_key:
        payload = payload.replace('provider_health', r'\u0070rovider_health')
    if as_bytes:
        payload = payload.encode('utf-8')
    with cdb.get_db_session() as db:
        db.add_all([_replay_execution(f'legacy-{i:03}', '{}', now[0].replace(tzinfo=None)) for i in range(100)])
        db.add(_replay_execution('valid', payload, now[0].replace(tzinfo=None)))
    assert router.provider_health('lab')['reason'] == 'observation backlog'


@pytest.mark.parametrize('shape', ['oversize', 'deep'])
@pytest.mark.parametrize('health_first', [False, True])
def test_recent_bounded_payload_never_opens_paid_dispatch(quota_lane, monkeypatch, shape, health_first):
    from src import estate_write_lane as lane
    message, count, now = quota_lane
    quota = router._quota_observation(message.read_text())
    noise = json.dumps('x' * (1024 * 1024 + 1)) if shape == 'oversize' else '[' * 100 + '0' + ']' * 100
    member = '"provider_health":' + json.dumps(quota)
    payload = '{' + (member + ',"noise":' + noise if health_first else '"noise":' + noise + ',' + member) + '}'
    with cdb.get_db_session() as db:
        db.add(_replay_execution('bounded-quota', payload, now[0].replace(tzinfo=None),
                                finished_at=now[0].replace(tzinfo=None)))
    monkeypatch.setattr(client, 'call_worker', lambda *a, **k: pytest.fail('paid dispatch escaped gate'))
    # Both before reconciliation and after a process restart, uncertainty closes admission.
    for sweep in range(3):
        health = router.provider_health('lab')
        assert health['state'] in {'quota_exhausted', 'unknown_unreadable'}
        assert not health['retry_allowed']
        assert router._dispatch_read_only('lab', 'codex', {'objective': 'review'})['executed'] is False
        with cdb.get_db_session() as db:
            lane.reconcile_stale_estate_executions(db, cdb.EstateExecution)
        router._PROVIDER_HEALTH_WRITE_FAILURES.clear()
    with cdb.get_db_session() as db:
        assert db.query(cdb.RoutingDecision).filter_by(task_class='provider_health_replay').count() == 1
    if health_first or shape == 'deep':
        assert router.provider_health('lab')['state'] == 'quota_exhausted'
    now[0] += lane.REPLAY_HORIZON + timedelta(seconds=1)
    assert router.provider_health('lab')['retry_allowed']
    assert not count.exists()


def test_unpersistable_recent_rows_do_not_monopolise_replay(quota_lane):
    from src import estate_write_lane as lane
    message, count, now = quota_lane
    quota = router._quota_observation(message.read_text())
    bad = {**quota, 'observed_at': '0001-01-01T00:00:00+01:00'}
    with cdb.get_db_session() as db:
        for i in range(10):
            when = (now[0] - timedelta(seconds=20 - i)).replace(tzinfo=None)
            db.add(_replay_execution(f'overflow-{i:02}', json.dumps({'provider_health': bad}), when,
                                    finished_at=when, host_id='bad-host'))
        db.add(_replay_execution('following-quota', json.dumps({'provider_health': quota}),
                                now[0].replace(tzinfo=None), finished_at=now[0].replace(tzinfo=None)))
    for _ in range(2):
        with cdb.get_db_session() as db:
            lane.reconcile_stale_estate_executions(db, cdb.EstateExecution)
    with cdb.get_db_session() as db:
        assert db.query(cdb.RoutingDecision).filter_by(id='provider-health:following-quota').count() == 1
        assert db.query(cdb.RoutingDecision).filter_by(task_class='provider_health_replay',
            escalation_reason='unpersistable', host_id='bad-host').count() == 10
    router._PROVIDER_HEALTH_WRITE_FAILURES.clear()
    assert router.provider_health('bad-host')['state'] == 'unknown_unreadable'
    assert not router.provider_health('bad-host')['retry_allowed']
    assert router.provider_health('lab')['state'] == 'quota_exhausted'
    # A durable disposition prevents repeated persistence attempts, including after restart.
    with cdb.get_db_session() as db:
        lane.reconcile_stale_estate_executions(db, cdb.EstateExecution)
    assert not router._PROVIDER_HEALTH_WRITE_FAILURES
    now[0] += lane.REPLAY_HORIZON + timedelta(seconds=1)
    assert router.provider_health('bad-host')['retry_allowed']
    assert not count.exists()


def test_replay_vm_cost_independent_of_expired_history(quota_lane, record_property):
    from sqlalchemy import event
    from src import estate_write_lane as lane
    message, count, now = quota_lane
    engine = cdb.SessionLocal.kw['bind']
    start = now[0].replace(tzinfo=None)
    costs = []
    for history_size in (0, 10000):
        with cdb.get_db_session() as db:
            db.query(cdb.RoutingDecision).delete()
            db.query(cdb.EstateExecution).delete()
            for i in range(history_size):
                when = start - lane.REPLAY_HORIZON - timedelta(days=1, seconds=history_size - i)
                db.add(_replay_execution(f'history-{i:05}', '{}', when, finished_at=when))
                if i < history_size // 2:
                    db.add(cdb.RoutingDecision(id=f'provider-health-replay:history-{i:05}',
                        task_class='provider_health_replay', host_id='lab', executor='codex',
                        escalation_reason='no_usable_observation', status='complete'))
                # Handled rows inside the longer window must also stay cheap.
                db.add(_replay_execution(f'handled-{i:05}', '{}', start,
                                        provider_health_replay_handled=True))
            for i in range(4):
                db.add(_replay_execution(f'recent-{i}', '{}', start, finished_at=start))
        statements, steps, connections = [], [0], set()
        def executed(conn, cursor, statement, parameters, context, executemany):
            statements.append(statement)
            connections.add(cursor.connection)
            cursor.connection.set_progress_handler(progress, 1)
        def progress():
            steps[0] += 1
            return 0
        event.listen(engine, 'before_cursor_execute', executed)
        try:
            with cdb.get_db_session() as db:
                lane.reconcile_stale_estate_executions(db, cdb.EstateExecution)
        finally:
            event.remove(engine, 'before_cursor_execute', executed)
            for raw in connections:
                raw.set_progress_handler(None, 0)
        costs.append((len(statements), steps[0]))
    record_property("replay_costs_empty_then_expired_history", str(costs))
    assert costs[1][0] <= costs[0][0] + 2, costs
    assert costs[1][1] <= costs[0][1] + 1000, costs
    assert costs[1][1] < 4000, costs


def test_terminal_write_failure_ages_out_without_process_retry_latch(quota_lane, monkeypatch):
    from src import estate_write_lane as lane
    message, count, now = quota_lane
    health = {**router._quota_observation(message.read_text()),
              'observed_at': '0001-01-01T00:00:00+01:00'}
    result = {'provider_health': health}
    with cdb.get_db_session() as db:
        db.add(_replay_execution('live-overflow', json.dumps(result), now[0].replace(tzinfo=None)))
    lane._record_outcome(lane._load_row('live-overflow'), 'failed', 'lab', result)
    assert not router._PROVIDER_HEALTH_WRITE_FAILURES
    monkeypatch.setattr(client, 'call_worker', lambda *a, **k: pytest.fail('paid dispatch escaped gate'))
    assert router._dispatch_read_only('lab', 'codex', {'objective': 'review'})['executed'] is False
    # Even if reconciliation was stopped beyond the horizon, stale poison evidence no
    # longer gates this provider or gets retried by a health read.
    now[0] += lane.REPLAY_HORIZON + timedelta(seconds=1)
    assert router.provider_health('lab')['retry_allowed']
    with cdb.get_db_session() as db:
        lane.reconcile_stale_estate_executions(db, cdb.EstateExecution)
        assert db.query(cdb.RoutingDecision).filter_by(task_class='provider_health_replay').count() == 0
    assert not count.exists()


def test_member_extraction_replays_health_without_rewriting_execution_outcome(quota_lane):
    from src import estate_write_lane as lane
    message, count, now = quota_lane
    health = {'provider': 'codex', 'state': 'ok', 'retry_after': None,
              'observed_at': now[0].isoformat(), 'reason': 'successful execution'}
    result = json.dumps({'provider_health': health, 'ok': True, 'output': 'x' * (1024 * 1024)})
    with cdb.get_db_session() as db:
        db.add(cdb.RoutingDecision(id='completed-decision', task_class='code_implementation',
            host_id='lab', executor='codex-write', status='complete', deterministic_gate='pass'))
        row = _replay_execution('large-success', result, now[0].replace(tzinfo=None))
        row.lifecycle_state = 'succeeded'
        row.decision_id = 'completed-decision'
        db.add(row)
    with cdb.get_db_session() as db:
        lane.reconcile_stale_estate_executions(db, cdb.EstateExecution)
    with cdb.get_db_session() as db:
        decision = db.query(cdb.RoutingDecision).filter_by(id='completed-decision').one()
        assert (decision.status, decision.deterministic_gate) == ('complete', 'pass')
        observation = db.query(cdb.RoutingDecision).filter_by(id='provider-health:large-success').one()
        assert json.loads(observation.provider_health_json) == health
    assert router.provider_health('lab')['state'] == 'ok'
