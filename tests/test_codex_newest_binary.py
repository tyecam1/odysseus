"""The write lane's 'latest model' is the newest entry of the *chosen binary's* authenticated
catalogue, so a stale install silently pins an old model.

Live finding (2026-11-20, activation f4b6f653): the service ran the user-local npm install
(`~/.local/codex-cli`, package.json `^0.163.0`, which on a 0.x release pins the minor), whose
catalogue tops out at gpt-6.1-sol, while the standalone install and the newest release already
offered gpt-6.2-sol. The first live write therefore ran on gpt-6.1-sol, against the standing rule
to use only the latest model versions. `_resolve_codex_binary` must prefer the newest install.
"""
import stat

import pytest

from src import estate_router


def fake_codex(path, version):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"#!/bin/sh\necho 'codex-cli {version}'\n")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setattr(estate_router.Path, "home", lambda: tmp_path)
    import shutil
    monkeypatch.setattr(shutil, "which", lambda name: None)
    estate_router._CODEX_VERSION_CACHE.clear()
    return tmp_path


def local_npm(home, version):
    return fake_codex(home / ".local" / "codex-cli" / "node_modules" / ".bin" / "codex", version)


def standalone(home, version):
    return fake_codex(home / ".local" / "bin" / "codex", version)


def test_a_newer_standalone_install_beats_a_stale_user_local_npm_install(home):
    local_npm(home, "0.163.0")
    newer = standalone(home, "0.171.0")
    binary, source = estate_router._resolve_codex_binary()
    assert binary == str(newer)
    assert "newest" in source and "0.171.0" in source and "0.163.0" in source


def test_the_user_local_install_still_wins_when_it_is_current(home):
    local = local_npm(home, "0.171.0")
    standalone(home, "0.171.0")
    binary, source = estate_router._resolve_codex_binary()
    assert binary == str(local) and "user-local" in source


def test_a_newer_user_local_install_wins(home):
    local = local_npm(home, "0.172.0")
    standalone(home, "0.171.0")
    assert estate_router._resolve_codex_binary()[0] == str(local)


def test_versions_compare_numerically_not_as_text(home):
    local_npm(home, "0.99.0")
    newer = standalone(home, "0.171.0")
    assert estate_router._resolve_codex_binary()[0] == str(newer)


def test_an_unprobeable_preferred_install_is_kept_never_replaced_by_a_guess(home):
    local = home / ".local" / "codex-cli" / "node_modules" / ".bin" / "codex"
    local.parent.mkdir(parents=True)
    local.write_text("#!/bin/sh\nexit 3\n")                    # --version fails: version unknown
    local.chmod(local.stat().st_mode | stat.S_IXUSR)
    standalone(home, "0.171.0")
    assert estate_router._resolve_codex_binary()[0] == str(local)


def test_the_system_copy_is_a_candidate_too(home, monkeypatch):
    import shutil
    local_npm(home, "0.163.0")
    system = fake_codex(home / "usr" / "bin" / "codex", "0.180.0")
    monkeypatch.setattr(shutil, "which", lambda name: str(system))
    assert estate_router._resolve_codex_binary()[0] == str(system)
