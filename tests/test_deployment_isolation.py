"""Multi-deployment isolation acceptance (synthetic fixtures only).

Every negative case runs in both directions (misumi->phd, phd->misumi). See
docs/runtime-work-packages/multi-deployment-isolation.md.
"""

import os
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

from src import deployment_isolation as iso
from src.deployment_isolation import IsolationError, DeploymentProfile

REPO = Path(__file__).resolve().parent.parent
CANARY = {
    "misumi": "SYNTHETIC_MISUMI_ISOLATION_CANARY_01",
    "phd": "SYNTHETIC_PHD_ISOLATION_CANARY_01",
}
ROOT_VAR = {"misumi": "MISUMI_HOUSEHOLD_ROOT", "phd": "BBC_OBSIDIAN_PHD_ROOT"}
OTHER = {"misumi": "phd", "phd": "misumi"}
BOTH = [("misumi", "phd"), ("phd", "misumi")]
SECRET = "synthetic-" + "s" * 12  # low-entropy on purpose: never key-shaped


@pytest.fixture(autouse=True)
def _no_active_isolation_leaks_between_tests():
    iso.set_active(None)
    yield
    iso.set_active(None)  # enforce_startup registers a process-wide result; never let it reach another test module


def make(tmp_path, domain, **over):
    base = tmp_path / domain
    (base / "source").mkdir(parents=True, exist_ok=True)
    (base / "source" / "canary.txt").write_text(CANARY[domain])
    (base / "data").mkdir(exist_ok=True)
    env = {
        iso.MODE_VAR: "required",
        iso.ID_VAR: f"{domain}-main",
        iso.DOMAIN_VAR: domain,
        iso.DATA_VAR: str(os.path.realpath(base / "data")),
        ROOT_VAR[domain]: str(os.path.realpath(base / "source")),
        iso.CREDENTIALS_VAR: f"{domain}-cred",
        iso.PORT_VAR: "14520" if domain == "misumi" else "14521",
    }
    env.update(over)
    return env


def snapshot(tmp_path):
    return {str(p): p.read_bytes() for p in sorted(tmp_path.rglob("*")) if p.is_file()}


def test_separate_baseline_both_start_and_read_only_own_canary(tmp_path):
    results = {d: iso.enforce_startup(make(tmp_path, d)) for d in CANARY}
    assert all(r.enforced for r in results.values())
    iso.validate_profiles([r.profile for r in results.values()])
    for d, r in results.items():
        own = [p for _, p in r.profile.source_roots]
        assert Path(own[0], "canary.txt").read_text() == CANARY[d]
        with pytest.raises(IsolationError) as e:
            iso.ensure_within_deployment(r, str(tmp_path / OTHER[d] / "source" / "canary.txt"))
        assert e.value.code == "cross_domain_target"


def test_isolation_off_is_a_noop_and_does_not_create_anything(tmp_path):
    r = iso.enforce_startup({})
    assert not r.enforced
    assert iso.ensure_within_deployment(r, "/anything") == "/anything"
    iso.check_credential(r, "whatever")


def test_invalid_mode_fails_closed():
    with pytest.raises(IsolationError) as e:
        iso.enforce_startup({iso.MODE_VAR: "maybe"})
    assert e.value.code == "invalid_mode"


@pytest.mark.parametrize("domain", CANARY)
def test_missing_data_root_refused_before_anything_is_created(tmp_path, domain):
    env = make(tmp_path, domain)
    del env[iso.DATA_VAR]
    before = snapshot(tmp_path)
    with pytest.raises(IsolationError) as e:
        iso.enforce_startup(env)
    assert e.value.code == "missing_data_root"
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize("missing", [iso.ID_VAR, iso.DOMAIN_VAR])
def test_missing_identity_refused(tmp_path, missing):
    env = make(tmp_path, "misumi")
    del env[missing]
    with pytest.raises(IsolationError) as e:
        iso.enforce_startup(env)
    assert e.value.code == "missing_identity"


def test_relative_and_traversal_roots_refused(tmp_path):
    with pytest.raises(IsolationError) as e:
        iso.enforce_startup(make(tmp_path, "misumi", **{iso.DATA_VAR: "relative/data"}))
    assert e.value.code == "path_not_absolute"
    sneaky = str(tmp_path / "misumi" / "data" / ".." / ".." / "phd" / "data")
    with pytest.raises(IsolationError) as e:
        iso.enforce_startup(make(tmp_path, "misumi", **{iso.DATA_VAR: sneaky}))
    assert e.value.code == "path_alias"


@pytest.mark.parametrize("a,b", BOTH)
def test_equal_and_nested_data_roots_refused(tmp_path, a, b):
    ea, eb = make(tmp_path, a), make(tmp_path, b)
    ra = iso.enforce_startup(ea)
    eb[iso.DATA_VAR] = ea[iso.DATA_VAR]
    with pytest.raises(IsolationError) as e:
        iso.validate_pair(ra.profile, iso.profile_from_env(eb))
    assert e.value.code == "data_root_overlap"
    nested = Path(ea[iso.DATA_VAR]) / "inner"
    nested.mkdir()
    eb[iso.DATA_VAR] = str(nested)
    with pytest.raises(IsolationError) as e:
        iso.validate_pair(ra.profile, iso.profile_from_env(eb))
    assert e.value.code == "nested_data_root"
    with pytest.raises(IsolationError) as e:  # and in the opposite argument order
        iso.validate_pair(iso.profile_from_env(eb), ra.profile)
    assert e.value.code == "nested_data_root"


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="symlinks unavailable")
@pytest.mark.parametrize("a,b", BOTH)
def test_symlink_alias_to_opposite_root_refused(tmp_path, a, b):
    ea, eb = make(tmp_path, a), make(tmp_path, b)
    link = tmp_path / "alias"
    try:
        os.symlink(eb[iso.DATA_VAR], link, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation not permitted")
    ea[iso.DATA_VAR] = str(link)
    before = snapshot(tmp_path)
    with pytest.raises(IsolationError) as e:
        iso.enforce_startup(ea)
    assert e.value.code == "path_alias"
    assert snapshot(tmp_path) == before


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="symlinks unavailable")
def test_link_swapped_after_validation_is_detected(tmp_path):
    env = make(tmp_path, "misumi")
    result = iso.enforce_startup(env)
    result.recheck()
    data = Path(env[iso.DATA_VAR])
    moved = tmp_path / "moved"
    data.rename(moved)
    try:
        os.symlink(tmp_path / "phd" / "data", data, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation not permitted")
    with pytest.raises(IsolationError) as e:
        result.recheck()
    assert e.value.code == "path_alias"


@pytest.mark.skipif(os.name != "nt", reason="case aliasing is a Windows-path property")
def test_case_alias_matches_on_windows(tmp_path):
    env = make(tmp_path, "misumi")
    a = iso.enforce_startup(env).profile
    swapped = iso.profile_from_env({**env, iso.ID_VAR: "other", iso.DATA_VAR: env[iso.DATA_VAR].swapcase()})
    with pytest.raises(IsolationError):
        iso.validate_pair(a, swapped)


@pytest.mark.parametrize("domain", CANARY)
def test_inherited_opposite_domain_root_refused_even_when_own_parameter_empty(tmp_path, domain):
    env = make(tmp_path, domain)
    env[ROOT_VAR[OTHER[domain]]] = str(tmp_path / OTHER[domain] / "source")  # inherited from the parent
    env[ROOT_VAR[domain]] = ""
    before = snapshot(tmp_path)
    with pytest.raises(IsolationError) as e:
        iso.enforce_startup(env)
    assert e.value.code == "opposite_domain_root_inherited"
    assert ROOT_VAR[OTHER[domain]] in e.value.detail
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize("domain", CANARY)
def test_source_root_inside_data_root_refused(tmp_path, domain):
    env = make(tmp_path, domain)
    env[ROOT_VAR[domain]] = env[iso.DATA_VAR]
    with pytest.raises(IsolationError) as e:
        iso.enforce_startup(env)
    assert e.value.code == "source_root_in_data_root"


@pytest.mark.parametrize("a,b", BOTH)
def test_writable_paths_must_stay_in_own_data_root(tmp_path, a, b):
    for var in iso.WRITABLE_VARS:
        env = make(tmp_path, a, **{var: str(tmp_path / b / "data" / "x")})
        with pytest.raises(IsolationError) as e:
            iso.enforce_startup(env)
        assert e.value.code == "writable_outside_data_root", var
        shared_src = make(tmp_path, a, **{var: str(Path(make(tmp_path, a)[ROOT_VAR[a]]) / "out")})
        with pytest.raises(IsolationError):
            iso.enforce_startup(shared_src)
    inside = make(tmp_path, a, ODYSSEUS_MAIL_ATTACHMENTS_DIR=str(Path(make(tmp_path, a)[iso.DATA_VAR]) / "mail"))
    assert iso.enforce_startup(inside).enforced


@pytest.mark.parametrize("a,b", BOTH)
def test_shared_identifier_credential_and_port_refused(tmp_path, a, b):
    pa = iso.enforce_startup(make(tmp_path, a)).profile
    base = make(tmp_path, b)
    for patch, code in (
        ({iso.ID_VAR: f"{a}-main"}, "shared_identifier"),
        ({iso.CREDENTIALS_VAR: f"{a}-cred"}, "credential_collision"),
        ({iso.PORT_VAR: str(pa.port)}, "shared_identifier"),
    ):
        with pytest.raises(IsolationError) as e:
            iso.validate_pair(pa, iso.profile_from_env({**base, **patch}))
        assert e.value.code == code


@pytest.mark.parametrize("domain", CANARY)
def test_foreign_credential_rejected_without_echo(tmp_path, domain):
    r = iso.enforce_startup(make(tmp_path, domain))
    iso.check_credential(r, f"{domain}-cred")
    with pytest.raises(IsolationError) as e:
        iso.check_credential(r, SECRET)
    assert e.value.code == "credential_collision"
    assert SECRET not in str(e.value)


@pytest.mark.parametrize("a,b", BOTH)
def test_marker_blocks_reuse_by_a_different_deployment_and_survives_restart(tmp_path, a, b):
    env = make(tmp_path, a)
    iso.enforce_startup(env)
    iso.enforce_startup(env)  # restart: marker re-verified, same deployment accepted
    other = {**make(tmp_path, b), iso.DATA_VAR: env[iso.DATA_VAR]}  # a different deployment pointed at the same data root
    before = snapshot(tmp_path)
    with pytest.raises(IsolationError) as e:
        iso.enforce_startup(other)
    assert e.value.code == "marker_mismatch"
    assert snapshot(tmp_path) == before


def test_corrupt_or_oversized_marker_refused(tmp_path):
    env = make(tmp_path, "misumi")
    marker = Path(env[iso.DATA_VAR]) / iso.MARKER_NAME
    for body in (b"not json", b"[]", b"{" + b" " * 8000 + b"}"):
        marker.write_bytes(body)
        with pytest.raises(IsolationError) as e:
            iso.enforce_startup(env)
        assert e.value.code == "marker_mismatch"


@pytest.mark.parametrize("domain", CANARY)
def test_diagnostics_never_leak_paths_canaries_or_secrets(tmp_path, domain):
    cases = []
    env = make(tmp_path, domain)
    cases.append({**env, ROOT_VAR[OTHER[domain]]: str(tmp_path / OTHER[domain] / "source")})
    cases.append({**env, ROOT_VAR[domain]: env[iso.DATA_VAR]})
    cases.append({**env, "ODYSSEUS_MAIL_ATTACHMENTS_DIR": str(tmp_path / OTHER[domain] / "data")})
    cases.append({**env, iso.DATA_VAR: str(tmp_path / ".." / "x")})
    for case in cases:
        with pytest.raises(IsolationError) as e:
            iso.enforce_startup(case)
        text = str(e.value)
        assert str(tmp_path) not in text and CANARY[domain] not in text and CANARY[OTHER[domain]] not in text
        assert "canary.txt" not in text and SECRET not in text


def _run(code, env_extra):
    env = {k: v for k, v in os.environ.items() if not k.startswith(("ODYSSEUS_", "MISUMI_", "BBC_", "OBSIDIAN_"))}
    env.update(env_extra)
    env["PYTHONPATH"] = str(REPO)
    return subprocess.run([sys.executable, "-c", code], cwd=str(REPO), env=env, capture_output=True, text=True, timeout=60)


STARTUP = "from src.deployment_isolation import enforce_startup_or_exit as e; print(e().enforced)"


def test_subprocess_startup_missing_overlapping_and_valid(tmp_path):
    good = make(tmp_path, "misumi")
    ok = _run(STARTUP, good)
    assert ok.returncode == 0 and ok.stdout.strip() == "True"
    missing = {k: v for k, v in good.items() if k != iso.DATA_VAR}
    bad = _run(STARTUP, missing)
    assert bad.returncode == 78 and "missing_data_root" in bad.stderr
    overlap = _run(STARTUP, {**good, ROOT_VAR["misumi"]: good[iso.DATA_VAR]})
    assert overlap.returncode == 78 and "source_root_in_data_root" in overlap.stderr
    assert str(tmp_path) not in overlap.stderr


def test_constants_import_refuses_when_required_and_is_unchanged_when_off(tmp_path):
    good = make(tmp_path, "misumi")
    bad = _run("import src.constants", {k: v for k, v in good.items() if k != iso.DATA_VAR})
    assert bad.returncode == 78 and "missing_data_root" in bad.stderr
    off = _run("import src.constants as c; print(c.DATA_DIR)", {iso.DATA_VAR: str(tmp_path / "plain")})
    assert off.returncode == 0 and off.stdout.strip() == str(tmp_path / "plain")


STATE_NAMES = ("SESSIONS_FILE", "MEMORY_FILE", "AUTH_FILE", "INTEGRATIONS_FILE", "VAULT_FILE", "BG_JOBS_FILE", "BG_JOBS_DIR", "APP_DB",
               "CHROMA_DIR", "RAG_DIR", "MEMORY_VECTORS_DIR", "UPLOAD_DIR", "PERSONAL_UPLOADS_DIR", "SKILLS_DIR", "MCP_OAUTH_DIR",
               "SCHEDULED_EMAILS_DB")


@pytest.mark.parametrize("a,b", BOTH)
def test_sessions_jobs_memory_indexes_and_credentials_resolve_under_each_own_data_root(tmp_path, a, b):
    code = "import json, src.constants as c; print(json.dumps({n: getattr(c, n) for n in %r}))" % (STATE_NAMES,)
    import json
    paths = {}
    for d in (a, b):
        out = _run(code, make(tmp_path, d))
        assert out.returncode == 0, out.stderr
        paths[d] = json.loads(out.stdout)
        root = os.path.realpath(make(tmp_path, d)[iso.DATA_VAR])
        for name, value in paths[d].items():
            assert os.path.realpath(value).startswith(root + os.sep), name
    assert not set(paths[a].values()) & set(paths[b].values())


# ---------------------------------------------------------------------------
# Real runtime boundaries (in-process, with the startup result registered as active)
# ---------------------------------------------------------------------------
import asyncio
import json


@pytest.fixture
def active(tmp_path):
    results = {}

    def start(domain):
        results[domain] = iso.enforce_startup(make(tmp_path, domain))
        return results[domain]

    yield start
    iso.set_active(None)


def _read_tool(path):
    import src.tool_execution as te
    from src.agent_tools import ToolBlock
    te._owner_is_admin, saved = (lambda owner: True), te._owner_is_admin  # exercise the path boundary, not the admin gate
    try:
        return asyncio.run(te.execute_tool_block(ToolBlock("read_file", json.dumps({"path": str(path)}))))
    finally:
        te._owner_is_admin = saved


@pytest.mark.parametrize("a,b", BOTH)
def test_file_tools_confined_to_own_roots_and_never_reach_opposite_domain(tmp_path, active, a, b, monkeypatch):
    make(tmp_path, b)  # the opposite domain's synthetic tree exists on disk
    r = active(a)
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    import src.tool_execution as te
    roots = te._tool_path_roots()
    assert roots[0] == r.data_root and str(tmp_path / b) not in roots and "/tmp" not in roots
    own = tmp_path / a / "source" / "canary.txt"
    _, ok = _read_tool(own)
    assert CANARY[a] in json.dumps(ok)
    foreign = tmp_path / b / "source" / "canary.txt"
    _, denied = _read_tool(foreign)
    assert denied.get("exit_code") == 1 and CANARY[b] not in json.dumps(denied)
    stray = tmp_path / "stray.txt"
    stray.write_text("shared-temp")
    _, denied = _read_tool(stray)
    assert denied.get("exit_code") == 1 and "shared-temp" not in json.dumps(denied)


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="symlinks unavailable")
@pytest.mark.parametrize("a,b", BOTH)
def test_symlink_inside_own_root_cannot_reach_opposite_domain(tmp_path, active, a, b):
    make(tmp_path, b)
    r = active(a)
    link = Path(r.data_root) / "innocent"
    try:
        os.symlink(tmp_path / b / "source", link, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation not permitted")
    _, denied = _read_tool(link / "canary.txt")
    assert denied.get("exit_code") == 1 and CANARY[b] not in json.dumps(denied)


@pytest.mark.parametrize("a,b", BOTH)
def test_workspace_binding_refuses_opposite_domain_and_shared_dirs(tmp_path, active, a, b):
    make(tmp_path, b)
    active(a)
    import src.tool_execution as te
    assert te.vet_workspace(str(tmp_path / b / "source")) is None
    assert te.vet_workspace(str(tmp_path)) is None
    assert te.vet_workspace(str(tmp_path / a / "source")) == os.path.realpath(tmp_path / a / "source")


def test_shell_tools_background_jobs_and_admin_shell_refused_unless_opted_in(tmp_path, active, monkeypatch):
    from fastapi import HTTPException
    import src.tool_execution as te
    from src.agent_tools import ToolBlock
    from src import bg_jobs
    from routes import shell_routes
    monkeypatch.delenv(iso.SHELL_OPT_IN_VAR, raising=False)
    active("misumi")
    for tool in ("bash", "python"):
        _, res = asyncio.run(te.execute_tool_block(ToolBlock(tool, "echo hi")))
        assert res.get("exit_code") == 1 and "isolation" in res["error"], tool
    with pytest.raises(IsolationError) as e:
        bg_jobs.launch("echo hi", session_id="s")
    assert e.value.code == "shell_disabled"
    with pytest.raises(HTTPException) as h:
        shell_routes._require_admin(object())
    assert h.value.status_code == 403
    with pytest.raises(IsolationError):
        asyncio.run(shell_routes._create_shell("echo hi"))
    monkeypatch.setenv(iso.SHELL_OPT_IN_VAR, "1")
    assert not iso.shell_blocked()


def test_shell_not_blocked_when_isolation_off():
    iso.set_active(None)
    assert not iso.shell_blocked() and iso.confined_roots() is None


@pytest.mark.parametrize("a,b", BOTH)
def test_estate_repo_resolution_cannot_point_dispatch_at_the_other_domain(tmp_path, active, a, b, monkeypatch):
    make(tmp_path, b)
    active(a)
    from src import estate_router
    own, foreign = str(tmp_path / a / "source"), str(tmp_path / b / "source")
    for repo, path, expected in (("own", own, own), ("foreign", foreign, None)):
        monkeypatch.setattr(estate_router, "_resolve_repo_path_unconfined", lambda rid, p=path: p)
        assert estate_router.resolve_repo_path(repo) == expected


def test_boundaries_unchanged_when_isolation_off(tmp_path, monkeypatch):
    iso.set_active(None)
    from src import estate_router
    monkeypatch.setattr(estate_router, "_resolve_repo_path_unconfined", lambda rid: "/anywhere")
    assert estate_router.resolve_repo_path("x") == "/anywhere"


@pytest.mark.parametrize("a,b", BOTH)
def test_memory_and_state_stores_are_per_deployment(tmp_path, a, b):
    from src.memory import MemoryManager
    ra, rb = make(tmp_path, a)[iso.DATA_VAR], make(tmp_path, b)[iso.DATA_VAR]
    ma, mb = MemoryManager(ra), MemoryManager(rb)
    ma.save([ma.add_entry(f"private {a} fact {CANARY[a]}", owner="tye")])
    assert all(CANARY[a] not in json.dumps(e) for e in mb.load_all())
    assert any(CANARY[a] in json.dumps(e) for e in ma.load_all())


@pytest.mark.parametrize("winner,loser", BOTH)
def test_concurrent_startup_has_one_marker_owner(tmp_path, winner, loser):
    env_w, env_l = make(tmp_path, winner), make(tmp_path, loser)
    env_l[iso.DATA_VAR] = env_w[iso.DATA_VAR]  # both race for the same data root
    fresh = Path(env_w[iso.DATA_VAR]) / "fresh"
    env_w[iso.DATA_VAR] = env_l[iso.DATA_VAR] = str(fresh)
    code = "from src.deployment_isolation import enforce_startup_or_exit as e; e(); print('ok')"
    procs = []
    for env in [env_w] * 4 + [env_l] * 4:
        penv = {k: v for k, v in os.environ.items() if not k.startswith(("ODYSSEUS_", "MISUMI_", "BBC_", "OBSIDIAN_"))}
        penv.update(env, PYTHONPATH=str(REPO))
        procs.append((env[iso.ID_VAR], subprocess.Popen([sys.executable, "-c", code], cwd=str(REPO), env=penv,
                                                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)))
    outcomes = {}
    for ident, p in procs:
        out, err = p.communicate(timeout=60)
        outcomes.setdefault(ident, set()).add(p.returncode)
        assert "marker_mismatch" in err or p.returncode == 0
        assert str(tmp_path) not in err
    # exactly one deployment owns the root; the other is wholly refused, never half-started
    assert sorted(len(v) for v in outcomes.values()) == [1, 1]
    assert {frozenset(v) for v in outcomes.values()} == {frozenset({0}), frozenset({78})}
    marker = json.loads((fresh / iso.MARKER_NAME).read_text())
    assert marker["deployment_id"] in outcomes and outcomes[marker["deployment_id"]] == {0}
    assert [p.name for p in fresh.iterdir()] == [iso.MARKER_NAME]  # no leaked temp files


@pytest.mark.parametrize("a,b", BOTH)
def test_claim_never_overwrites_an_existing_marker(tmp_path, a, b):
    env = make(tmp_path, a)
    iso.enforce_startup(env)
    marker = Path(env[iso.DATA_VAR]) / iso.MARKER_NAME
    before = marker.read_bytes()
    intruder = iso.profile_from_env({**env, iso.ID_VAR: f"{b}-main", iso.DOMAIN_VAR: b})
    with pytest.raises(IsolationError) as e:  # bypass validate_profile: the claim itself must be exclusive
        iso.claim_data_root(intruder)
    assert e.value.code == "marker_mismatch"
    assert marker.read_bytes() == before


@pytest.mark.parametrize("a,b", BOTH)
def test_data_root_nested_in_or_containing_another_deployments_is_refused_before_any_write(tmp_path, a, b):
    ea = make(tmp_path, a)
    iso.enforce_startup(ea)
    inner = {**make(tmp_path, b), iso.DATA_VAR: str(Path(ea[iso.DATA_VAR]) / "nested" / "deeper")}
    before = snapshot(tmp_path)
    with pytest.raises(IsolationError) as e:
        iso.enforce_startup(inner)
    assert e.value.code == "nested_data_root" and not (Path(ea[iso.DATA_VAR]) / "nested").exists()
    assert snapshot(tmp_path) == before
    outer = {**make(tmp_path, b), iso.DATA_VAR: str(tmp_path)}  # contains a's marked data root two levels down
    with pytest.raises(IsolationError) as e:
        iso.enforce_startup(outer)
    assert e.value.code in ("nested_data_root", "source_root_in_data_root")
    assert str(tmp_path) not in str(e.value)


def test_pair_cli_refuses_shared_internal_token_without_echoing_it(tmp_path):
    token = "synthetic-" + "t" * 12
    files = []
    for d in CANARY:
        f = tmp_path / f"{d}.json"
        f.write_text(json.dumps({**make(tmp_path, d), iso.INTERNAL_TOKEN_VAR: token}))
        files.append(str(f))
    env = {**os.environ, "PYTHONPATH": str(REPO)}
    bad = subprocess.run([sys.executable, "-m", "src.deployment_isolation", "check", *files], cwd=str(REPO), env=env, capture_output=True, text=True)
    assert bad.returncode == 78 and "credential_collision" in bad.stderr and token not in bad.stderr + bad.stdout
    for d, f in zip(CANARY, files):
        doc = json.loads(Path(f).read_text())
        doc[iso.INTERNAL_TOKEN_VAR] = "tok-" + d
        Path(f).write_text(json.dumps(doc))
    ok = subprocess.run([sys.executable, "-m", "src.deployment_isolation", "check", *files], cwd=str(REPO), env=env, capture_output=True, text=True)
    assert ok.returncode == 0


# ---------------------------------------------------------------------------
# Independent-review round 1 (Sol): inventory, shell-equivalents, credentials, launcher, swaps, config
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("a,b", BOTH)
def test_every_domain_root_variable_is_checked_not_only_the_obvious_ones(tmp_path, a, b):
    for var in iso.DOMAIN_ROOT_VARS[b]:
        env = make(tmp_path, a, **{var: str(tmp_path / b / "source")})
        with pytest.raises(IsolationError) as e:
            iso.enforce_startup(env)
        assert e.value.code == "opposite_domain_root_inherited" and var in e.value.detail, var


def test_event_log_stt_and_profile_paths_are_writable_roots_that_must_stay_inside(tmp_path):
    for var in ("MISUMI_EVENT_LOG", "ODYSSEUS_STT_TMP_DIR", "ODYSSEUS_META_EXPORT_BROWSER_PROFILE"):
        with pytest.raises(IsolationError) as e:
            iso.enforce_startup(make(tmp_path, "phd", **{var: str(tmp_path / "misumi" / "data" / "x")}))
        assert e.value.code == "writable_outside_data_root", var


def test_shared_read_roots_must_be_inside_the_deployment_or_the_application(tmp_path):
    from src.runtime_paths import get_app_root
    make(tmp_path, "misumi")
    for var in iso.SHARED_READ_VARS:
        with pytest.raises(IsolationError) as e:
            iso.enforce_startup(make(tmp_path, "phd", **{var: str(tmp_path / "misumi" / "source" / "x")}))
        assert e.value.code == "foreign_root_configured", var
        assert iso.enforce_startup(make(tmp_path, "phd", **{var: os.path.join(get_app_root(), "docs")})).enforced


def test_unknown_domain_and_missing_or_absent_source_root_refused(tmp_path):
    with pytest.raises(IsolationError) as e:
        iso.enforce_startup(make(tmp_path, "misumi", **{iso.DOMAIN_VAR: "other"}))
    assert e.value.code == "unknown_domain"
    env = make(tmp_path, "misumi")
    env.pop(ROOT_VAR["misumi"])
    with pytest.raises(IsolationError) as e:
        iso.enforce_startup(env)
    assert e.value.code == "missing_source_root"
    with pytest.raises(IsolationError) as e:
        iso.enforce_startup(make(tmp_path, "misumi", **{ROOT_VAR["misumi"]: str(tmp_path / "does-not-exist")}))
    assert e.value.code == "missing_source_root"


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="symlinks unavailable")
def test_marker_replaced_by_a_link_or_directory_is_refused(tmp_path):
    env = make(tmp_path, "misumi")
    iso.enforce_startup(env)
    marker = Path(env[iso.DATA_VAR]) / iso.MARKER_NAME
    good = marker.read_bytes()
    elsewhere = tmp_path / "elsewhere.json"
    elsewhere.write_bytes(good)  # content identical: only the link-ness differs
    marker.unlink()
    try:
        os.symlink(elsewhere, marker)
    except OSError:
        pytest.skip("symlink creation not permitted")
    with pytest.raises(IsolationError) as e:
        iso.enforce_startup(env)
    assert e.value.code == "marker_mismatch"
    marker.unlink()
    marker.mkdir()
    with pytest.raises(IsolationError):
        iso.enforce_startup(env)


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="symlinks unavailable")
@pytest.mark.parametrize("a,b", BOTH)
def test_source_root_swapped_for_a_link_after_startup_stops_being_an_allowed_root(tmp_path, active, a, b):
    make(tmp_path, b)
    r = active(a)
    import src.tool_execution as te
    own = Path(r.sources[0][1])
    assert te.vet_workspace(str(own)) == str(own)
    moved = tmp_path / "moved-source"
    own.rename(moved)
    try:
        os.symlink(tmp_path / b / "source", own, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation not permitted")
    with pytest.raises(IsolationError):
        r.recheck()
    with pytest.raises(ValueError):
        te._tool_path_roots()
    _, denied = _read_tool(own / "canary.txt")
    assert denied.get("exit_code") == 1 and CANARY[b] not in json.dumps(denied)


@pytest.mark.parametrize("a,b", BOTH)
def test_env_token_is_bound_to_the_deployment_so_a_shared_value_cannot_cross(tmp_path, a, b):
    shared = "synthetic-" + "i" * 12
    code = "import core.middleware as m; print(m.INTERNAL_TOOL_TOKEN)"
    tokens = {}
    for d in (a, b):
        env = make(tmp_path, d, **{iso.INTERNAL_TOKEN_VAR: shared})
        out = _run(code, env)
        assert out.returncode == 0, out.stderr
        tokens[d] = out.stdout.strip()
        expected = iso.bind_credential(shared, env[iso.ID_VAR], env[iso.DATA_VAR])
        assert tokens[d] == expected and shared not in out.stdout + out.stderr
    assert tokens[a] != tokens[b]
    plain = _run(code, {iso.INTERNAL_TOKEN_VAR: shared})  # isolation off: unchanged behaviour
    assert plain.returncode == 0 and plain.stdout.strip() == shared


def test_validate_cli_creates_nothing_and_refuses_bad_configuration(tmp_path):
    env = make(tmp_path, "misumi")
    fresh = tmp_path / "never-created" / "data"
    code = "import sys; from src.deployment_isolation import main; sys.exit(main(['validate']))"
    ok = _run(code, {**env, iso.DATA_VAR: str(fresh)})
    assert ok.returncode == 0 and not fresh.exists() and not fresh.parent.exists()  # validation alone writes nothing
    bad = _run(code, {k: v for k, v in env.items() if k != iso.DATA_VAR})
    assert bad.returncode == 78 and "missing_data_root" in bad.stderr


def test_shell_equivalent_surfaces_are_gated(tmp_path, active, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from routes import cookbook_routes, mcp_routes, shell_routes
    monkeypatch.delenv(iso.SHELL_OPT_IN_VAR, raising=False)
    monkeypatch.setenv("AUTH_ENABLED", "false")
    active("phd")
    app = FastAPI()
    app.include_router(mcp_routes.setup_mcp_routes(mock.MagicMock()))
    app.include_router(cookbook_routes.setup_cookbook_routes())
    client = TestClient(app)
    r = client.post("/api/mcp/servers", data={"name": "x", "transport": "stdio", "command": "/bin/echo"})
    assert r.status_code == 403 and "isolated" in r.text
    r = client.get("/api/cookbook/gpus")
    assert r.status_code == 403 and "isolated" in r.text
    with pytest.raises(Exception) as gate:
        shell_routes._isolation_shell_gate()
    assert getattr(gate.value, "status_code", None) == 403
    iso.set_active(None)
    assert client.get("/api/cookbook/gpus").status_code != 403


@pytest.mark.parametrize("a,b", BOTH)
def test_estate_park_route_cannot_lease_a_repo_that_resolves_into_the_other_domain(tmp_path, active, a, b, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from routes import estate_routing_routes as er
    from src import estate_router, park_lease_ops
    make(tmp_path, b)
    active(a)
    monkeypatch.setattr(er, "_scope_owner", lambda request, allowed: "tye")
    monkeypatch.setattr(er, "current_host_id", lambda: "lab")
    monkeypatch.setattr(park_lease_ops, "git_is_clean", lambda path: (False, "dirty"))
    app = FastAPI()
    app.include_router(er.setup_estate_routing_routes())
    client = TestClient(app)
    monkeypatch.setattr(estate_router, "_resolve_repo_path_unconfined", lambda rid: str(tmp_path / b / "source"))
    foreign = client.post("/api/estate/park/some-repo")
    assert foreign.status_code == 404 and "not a registered repo" in foreign.text and str(tmp_path) not in foreign.text
    monkeypatch.setattr(estate_router, "_resolve_repo_path_unconfined", lambda rid: str(tmp_path / a / "source"))
    own = client.post("/api/estate/park/some-repo")
    assert own.status_code == 409 and "not a registered repo" not in own.text  # resolution passed; stopped later by the dirty-tree gate


# ---------------------------------------------------------------------------
# Independent-review round 2 (Sol): saved MCP servers, bound workspaces, snapshot window, hard links, Install
# ---------------------------------------------------------------------------
def test_saved_custom_stdio_mcp_server_cannot_connect_but_builtin_servers_still_do(tmp_path, active, monkeypatch):
    from unittest.mock import AsyncMock
    from src.mcp_manager import McpManager
    monkeypatch.delenv(iso.SHELL_OPT_IN_VAR, raising=False)
    active("phd")
    manager = McpManager()
    spawn = AsyncMock(return_value=True)
    monkeypatch.setattr(manager, "_connect_stdio", spawn)
    assert asyncio.run(manager.connect_server("custom1", "custom", "stdio", command="/bin/echo")) is False
    spawn.assert_not_called()
    assert manager._connections["custom1"]["status"] == "error" and "isolated" in manager._connections["custom1"]["error"]
    from src import builtin_mcp
    from src.runtime_paths import get_app_root
    script = os.path.join(get_app_root(), builtin_mcp._BUILTIN_SERVERS["image_gen"][0])
    assert asyncio.run(manager.connect_server("image_gen", "image_gen", "stdio", command=sys.executable, args=[script])) is True
    spawn.assert_called_once()
    monkeypatch.setenv(iso.SHELL_OPT_IN_VAR, "1")  # explicit operator opt-in restores the custom path
    assert asyncio.run(manager.connect_server("custom2", "custom", "stdio", command="/bin/echo")) is True


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="symlinks unavailable")
@pytest.mark.parametrize("a,b", BOTH)
def test_already_bound_workspace_is_rechecked_when_its_source_root_is_swapped(tmp_path, active, a, b):
    import src.tool_execution as te
    make(tmp_path, b)
    r = active(a)
    own = Path(r.sources[0][1])
    token = te._active_workspace.set(str(own))
    try:
        assert te._resolve_search_root("") == str(own)
        own.rename(tmp_path / "moved-source")
        try:
            os.symlink(tmp_path / b / "source", own, target_is_directory=True)
        except OSError:
            pytest.skip("symlink creation not permitted")
        for call in (lambda: te._resolve_tool_path(str(own / "canary.txt")), lambda: te._resolve_search_root(""),
                     lambda: te._resolve_search_root("canary.txt")):
            with pytest.raises(ValueError):
                call()
    finally:
        te._active_workspace.reset(token)


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="symlinks unavailable")
@pytest.mark.parametrize("a,b", BOTH)
def test_source_root_swapped_between_validation_and_snapshot_is_refused(tmp_path, a, b, monkeypatch):
    env = make(tmp_path, a)
    make(tmp_path, b)
    own = Path(env[ROOT_VAR[a]])
    real_claim = iso.claim_data_root

    def swap_then_claim(profile):
        own.rename(tmp_path / "moved-source")
        try:
            os.symlink(tmp_path / b / "source", own, target_is_directory=True)
        except OSError:
            pytest.skip("symlink creation not permitted")
        return real_claim(profile)

    monkeypatch.setattr(iso, "claim_data_root", swap_then_claim)
    with pytest.raises(IsolationError) as e:
        iso.enforce_startup(env)
    assert e.value.code == "path_alias" and iso.get_active() is None
    assert CANARY[b] not in str(e.value) and str(tmp_path) not in str(e.value)


@pytest.mark.skipif(os.name == "nt", reason="POSIX has no exclusive rename fallback; Windows falls back to rename")
def test_filesystem_without_hard_links_gives_a_path_safe_refusal_and_leaves_no_temp_file(tmp_path, monkeypatch):
    env = make(tmp_path, "misumi")
    monkeypatch.setattr(os, "link", lambda *a, **k: (_ for _ in ()).throw(OSError(95, "Operation not supported")))
    with pytest.raises(IsolationError) as e:
        iso.enforce_startup(env)
    assert e.value.code == "marker_unsupported" and str(tmp_path) not in str(e.value)
    assert [p.name for p in Path(env[iso.DATA_VAR]).iterdir()] == []


@pytest.mark.skipif(not hasattr(os, "geteuid") or os.geteuid() == 0, reason="needs an unprivileged POSIX user")
def test_unwritable_data_root_is_a_path_safe_refusal_not_a_traceback(tmp_path):
    env = make(tmp_path, "misumi")
    data = Path(env[iso.DATA_VAR])
    data.chmod(0o500)
    try:
        with pytest.raises(IsolationError) as e:
            iso.enforce_startup(env)
    finally:
        data.chmod(0o700)
    assert e.value.code == "data_root_unwritable" and str(tmp_path) not in str(e.value)


def test_windows_launcher_validates_before_creating_anything_in_both_install_and_run():
    script = (REPO / "scripts" / "windows" / "odysseus-host.ps1").read_text(encoding="utf-8")
    assert "& $Python -m src.deployment_isolation validate" in script
    for action in ("'Install' {", "'Run' {"):
        body = script[script.index(action):]
        assert body.index("Invoke-IsolationPreflight") < body.index("New-Item -ItemType Directory -Force -Path $DataRoot,$LogDir"), action
    for name in ("FLAT_KNOWLEDGEBASE_ROOT", "MISUMI_SEED_ORDER_ROOT", "MISUMI_CANONICAL_ROOT", "OBSIDIAN_PHD_ROOT"):
        assert name in script


# ---------------------------------------------------------------------------
# Independent-review round 3 (Sol): spoofed built-in ids, pinned identities, script-scope flag, errno classes
# ---------------------------------------------------------------------------
def test_only_the_exact_application_launch_of_a_builtin_server_is_trusted(tmp_path, active, monkeypatch):
    from unittest.mock import AsyncMock
    from src import builtin_mcp
    from src.mcp_manager import McpManager
    from src.runtime_paths import get_app_root
    monkeypatch.delenv(iso.SHELL_OPT_IN_VAR, raising=False)
    script = os.path.join(get_app_root(), builtin_mcp._BUILTIN_SERVERS["image_gen"][0])
    assert builtin_mcp.is_trusted_builtin_launch("image_gen", sys.executable, [script])
    npx = builtin_mcp._BUILTIN_NPX_SERVERS["builtin_browser"]
    assert builtin_mcp.is_trusted_builtin_launch("builtin_browser", builtin_mcp._find_npx(), npx["args"])
    assert not builtin_mcp.is_trusted_builtin_launch("builtin_browser", "/tmp/npx.sh", npx["args"])  # name alone is not trust
    for sid, cmd, args in (
        ("builtin_custom", "/bin/echo", ["hi"]),                        # prefix alone is not trust
        ("builtin_browser", "/bin/sh", ["-c", "echo hi"]),             # known id, different executable
        ("builtin_browser", builtin_mcp._find_npx(), ["-y", "evil-package"]),  # known id and executable, different package
        ("image_gen", sys.executable, ["/tmp/other.py"]),              # known id, different script
        ("image_gen", "/bin/sh", [script]),
        ("memory", sys.executable, []),
    ):
        assert not builtin_mcp.is_trusted_builtin_launch(sid, cmd, args), (sid, cmd, args)
    active("phd")
    manager = McpManager()
    spawn = AsyncMock(return_value=True)
    monkeypatch.setattr(manager, "_connect_stdio", spawn)
    assert asyncio.run(manager.connect_server("builtin_custom", "x", "stdio", command="/bin/echo")) is False
    spawn.assert_not_called()
    assert asyncio.run(manager.connect_server("image_gen", "img", "stdio", command=sys.executable, args=[script])) is True
    spawn.assert_called_once()


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="symlinks unavailable")
@pytest.mark.parametrize("a,b", BOTH)
def test_source_root_replaced_after_first_resolution_but_before_the_snapshot_is_refused(tmp_path, a, b, monkeypatch):
    env = make(tmp_path, a)
    make(tmp_path, b)
    own = Path(env[ROOT_VAR[a]])
    real_neighbours = iso._refuse_foreign_neighbours  # runs at the end of validate_profile, after identities are pinned

    def swap_after_pinning(data):
        own.rename(tmp_path / "moved-source")
        (tmp_path / "decoy").mkdir()
        try:
            os.symlink(tmp_path / b / "source", own, target_is_directory=True)
        except OSError:
            pytest.skip("symlink creation not permitted")
        return real_neighbours(data)

    monkeypatch.setattr(iso, "_refuse_foreign_neighbours", swap_after_pinning)
    with pytest.raises(IsolationError) as e:
        iso.enforce_startup(env)
    assert e.value.code == "path_alias" and iso.get_active() is None


@pytest.mark.skipif(os.name == "nt", reason="same-path directory replacement is exercised on POSIX")
def test_source_root_directory_replaced_by_another_directory_at_the_same_path_is_refused(tmp_path, monkeypatch):
    env = make(tmp_path, "misumi")
    own = Path(env[ROOT_VAR["misumi"]])
    real_neighbours = iso._refuse_foreign_neighbours

    def replace_with_new_dir(data):
        own.rename(tmp_path / "moved-source")
        own.mkdir()  # same path, different directory (different inode): a plain realpath comparison would pass
        return real_neighbours(data)

    monkeypatch.setattr(iso, "_refuse_foreign_neighbours", replace_with_new_dir)
    with pytest.raises(IsolationError) as e:
        iso.enforce_startup(env)
    assert e.value.code == "path_alias"


def test_launcher_captures_the_explicit_data_root_flag_at_script_scope():
    script = (REPO / "scripts" / "windows" / "odysseus-host.ps1").read_text(encoding="utf-8")
    assert script.count("$PSBoundParameters") == 1  # a function's own $PSBoundParameters can never see the script's -DataRoot
    assert script.index("$DataRootExplicit = $PSBoundParameters.ContainsKey('DataRoot')") < script.index("function Assert-Configuration")
    assert "if (-not $DataRootExplicit)" in script


@pytest.mark.skipif(os.name == "nt", reason="errno classes are asserted for POSIX")
@pytest.mark.parametrize("err,code", [
    (13, "data_root_unwritable"),   # EACCES
    (28, "data_root_unwritable"),   # ENOSPC
    (30, "data_root_unwritable"),   # EROFS
    (95, "marker_unsupported"),     # EOPNOTSUPP
    (1, "marker_unsupported"),      # EPERM (filesystem without hard links)
    (18, "marker_unsupported"),     # EXDEV
])
def test_hard_link_failures_are_classified_by_errno_without_leaking_paths(tmp_path, monkeypatch, err, code):
    env = make(tmp_path, "phd")

    def fail(*a, **k):
        raise OSError(err, "synthetic failure")

    monkeypatch.setattr(os, "link", fail)
    with pytest.raises(IsolationError) as e:
        iso.enforce_startup(env)
    assert e.value.code == code and str(tmp_path) not in str(e.value)
    assert [p.name for p in Path(env[iso.DATA_VAR]).iterdir()] == []  # temp file cleaned, no marker published


@pytest.mark.skipif(not hasattr(os, "rename"), reason="needs rename")
@pytest.mark.parametrize("a,b", BOTH)
def test_directory_swapped_while_it_is_being_resolved_and_pinned_is_refused(tmp_path, a, b, monkeypatch):
    env = make(tmp_path, a)
    own = Path(env[ROOT_VAR[a]])
    real_resolve = iso._resolve_root
    state = {"calls": 0}

    def swap_during_pin(role, raw):
        result = real_resolve(role, raw)
        if role == ROOT_VAR[a]:
            state["calls"] += 1
            if state["calls"] == 2:  # the resolution inside _pin: swap right after realpath, before the identity is read
                own.rename(tmp_path / "moved-source")
                own.mkdir()
        return result

    monkeypatch.setattr(iso, "_resolve_root", swap_during_pin)
    with pytest.raises(IsolationError) as e:
        iso.enforce_startup(env)
    assert e.value.code == "path_alias" and iso.get_active() is None and str(tmp_path) not in str(e.value)


@pytest.mark.parametrize("a,b", BOTH)
def test_source_directory_replaced_between_pinning_and_validation_is_refused(tmp_path, a, b, monkeypatch):
    env = make(tmp_path, a)
    own = Path(env[ROOT_VAR[a]])
    real_resolved = iso._resolved

    def swap_then_resolve(profile):
        own.rename(tmp_path / "moved-source")
        own.mkdir()  # same path, new directory: the pin recorded the original's identity
        return real_resolved(profile)

    monkeypatch.setattr(iso, "_resolved", swap_then_resolve)
    with pytest.raises(IsolationError) as e:
        iso.enforce_startup(env)
    assert e.value.code == "path_alias" and iso.get_active() is None and str(tmp_path) not in str(e.value)


@pytest.mark.parametrize("a,b", BOTH)
def test_existing_data_root_replaced_between_pinning_and_validation_is_refused(tmp_path, a, b, monkeypatch):
    env = make(tmp_path, a)
    data = Path(env[iso.DATA_VAR])
    real_resolved = iso._resolved

    def swap_then_resolve(profile):
        data.rename(tmp_path / "moved-data")
        data.mkdir()
        return real_resolved(profile)

    monkeypatch.setattr(iso, "_resolved", swap_then_resolve)
    with pytest.raises(IsolationError) as e:
        iso.enforce_startup(env)
    assert e.value.code == "path_alias"


@pytest.mark.parametrize("a,b", BOTH)
@pytest.mark.parametrize("plant", ["nested_marker", "top_level_marker"])
def test_absent_data_root_created_with_a_foreign_marker_after_validation_is_not_adopted(tmp_path, a, b, plant, monkeypatch):
    env = make(tmp_path, a)
    fresh = tmp_path / "fresh-data"
    env[iso.DATA_VAR] = str(fresh)
    real_validate = iso.validate_profile

    def validate_then_plant(profile, env=None):
        result = real_validate(profile, env=env)  # passes: the data root does not exist yet, so it cannot be pinned
        foreign = json.dumps({"schema": 1, "deployment_id": f"{b}-main", "domain": b})
        if plant == "nested_marker":
            (fresh / "inner").mkdir(parents=True)
            (fresh / "inner" / iso.MARKER_NAME).write_text(foreign)
        else:
            fresh.mkdir()
            (fresh / iso.MARKER_NAME).write_text(foreign)
        return result

    monkeypatch.setattr(iso, "validate_profile", validate_then_plant)
    with pytest.raises(IsolationError) as e:
        iso.enforce_startup(env)
    assert e.value.code in ("nested_data_root", "marker_mismatch") and iso.get_active() is None
    assert not (fresh / "inner" / "x").exists()
    marker = fresh / iso.MARKER_NAME
    assert not marker.exists() or json.loads(marker.read_text())["deployment_id"] == f"{b}-main"  # ours was never published
