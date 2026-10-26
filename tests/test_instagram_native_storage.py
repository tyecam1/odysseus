"""Synthetic local-only storage acceptance, including real native Windows APIs.

On Windows run: python -m pytest tests/test_instagram_native_storage.py -q
Only disposable tmp_path ACLs are changed. No browser, account or network use.
The same process-contention tests exercise flock on POSIX and msvcrt on Windows.
"""

import csv
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import time

import pytest

from src.instagram_export_job import (
    _acquisition_lock,
    _append_operator_gate,
    load_acquisition_state,
    run_instagram_export_job,
    save_acquisition_state,
)
from src.instagram_import_job import append_import_run, last_import_run
from src.private_state_io import check_private_path, private_dir


REPO = Path(__file__).resolve().parents[1]
WINDOWS = pytest.mark.skipif(os.name != "nt", reason="requires real Windows security and locking APIs")
POSIX = pytest.mark.skipif(os.name == "nt", reason="POSIX permissions and symlinks")


def _icacls(path, *args):
    return subprocess.run(["icacls", str(path), *args], check=True, capture_output=True).stdout


@pytest.fixture
def private_root(tmp_path):
    root = tmp_path / "synthetic-private"
    root.mkdir(mode=0o700)
    if os.name == "nt":
        # SID output avoids localised account/group names. This is not a credential.
        row = subprocess.run(["whoami", "/user", "/fo", "csv", "/nh"],
                             check=True, capture_output=True, text=True).stdout
        user_sid = next(csv.reader(io.StringIO(row.strip())))[1]
        _icacls(root, "/inheritance:r", "/grant:r", f"*{user_sid}:(OI)(CI)F",
                "*S-1-5-18:(OI)(CI)F", "*S-1-5-32-544:(OI)(CI)F")
    check_private_path(root)
    return root


def _state_and_logs(root):
    path = root / "instagram" / "acquisition-state.json"
    with _acquisition_lock(path):
        save_acquisition_state({"state": "awaiting_email", "cycle_id": "synthetic"}, path)
    assert load_acquisition_state(path)["cycle_id"] == "synthetic"
    with _acquisition_lock(path):
        state = load_acquisition_state(path)
        state["state"] = "validating"
        save_acquisition_state(state, path)
    assert load_acquisition_state(path)["state"] == "validating"
    assert (path.parent / ".acquisition-state.json.lock").is_file()
    assert not (path.parent / ".state.lock").exists()
    runs, gates = path.parent / "runs.jsonl", path.parent / "operator-gates.jsonl"
    for index in range(2):
        append_import_run({"created": index}, runs)
        _append_operator_gate({"reason": "synthetic", "index": index}, gates)
    assert [json.loads(line) for line in runs.read_text().splitlines()] == [{"created": 0}, {"created": 1}]
    assert [json.loads(line)["index"] for line in gates.read_text().splitlines()] == [0, 1]
    assert last_import_run(runs) == {"created": 1}
    for item in path.parent.iterdir():
        check_private_path(item)
        if os.name != "nt":
            assert stat.S_IMODE(item.stat().st_mode) == 0o600
    return path


@WINDOWS
def test_native_windows_acquisition_state_and_append_logs(private_root):
    # No mocked os.name, fchmod, fcntl or permission guard: real msvcrt/DACL calls.
    _state_and_logs(private_root)
    calls = []
    def requester(_profile):
        calls.append("synthetic request")
        return {"submitted_at": "2026-10-25T00:00:00Z"}
    args = dict(state_path=private_root / "job" / "state.json",
                exports_dir=private_root / "exports", profile_dir=private_root / "unused-profile",
                requester=requester, inbox_checker=lambda _profile: [])
    assert run_instagram_export_job(**args)["state"] == "awaiting_email"
    assert run_instagram_export_job(**args)["state"] == "awaiting_email"
    assert calls == ["synthetic request"]


@POSIX
def test_posix_acquisition_state_and_append_logs(private_root):
    path = _state_and_logs(private_root)
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700


_PROCESS = r"""
import sys
from pathlib import Path
from src.instagram_export_job import _acquisition_lock, load_acquisition_state, save_acquisition_state
from src.misumi_state_io import StateLockTimeout
mode, path, ready = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
if mode == 'waiter':
    ready.write_text('waiting')
try:
    with _acquisition_lock(path, timeout=0.15 if mode == 'refuse' else 5):
        state = load_acquisition_state(path)
        state['count'] += 1
        save_acquisition_state(state, path)
        if mode in ('release', 'exception', 'death'):
            ready.write_text('locked')
            sys.stdin.readline()
            if mode == 'death':
                import os
                os._exit(23)
            if mode == 'exception':
                raise RuntimeError('synthetic unwind')
except StateLockTimeout:
    print('refused', flush=True)
except RuntimeError:
    if mode != 'exception':
        raise
else:
    print('completed', flush=True)
"""


def _spawn(mode, path, ready):
    env = dict(os.environ, PYTHONPATH=str(REPO))
    return subprocess.Popen([sys.executable, "-c", _PROCESS, mode, str(path), str(ready)],
                            cwd=REPO, env=env, stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def _ready(path, proc):
    deadline = time.monotonic() + 15
    while not path.exists():
        assert proc.poll() is None, proc.communicate(timeout=2)
        assert time.monotonic() < deadline, "child did not reach synthetic rendezvous"
        time.sleep(0.01)


@pytest.mark.parametrize("ending", ["release", "exception", "death"])
def test_independent_processes_timeout_then_recover(private_root, ending):
    path = private_root / "state.json"
    save_acquisition_state({"state": "scheduled", "count": 0}, path)
    holder = _spawn(ending, path, private_root / "holder-ready")
    children = [holder]
    try:
        _ready(private_root / "holder-ready", holder)
        contender = _spawn("refuse", path, private_root / "unused")
        children.append(contender)
        started = time.monotonic()
        out, err = contender.communicate(timeout=15)
        assert contender.returncode == 0, err
        assert out.strip() == "refused"
        assert time.monotonic() - started < 15
        assert load_acquisition_state(path)["count"] == 1  # refused body did not run
        waiter = _spawn("waiter", path, private_root / "waiter-ready")
        children.append(waiter)
        _ready(private_root / "waiter-ready", waiter)
        holder.communicate(input="release\n", timeout=15)
        assert holder.returncode == (23 if ending == "death" else 0)
        out, err = waiter.communicate(timeout=15)
        assert waiter.returncode == 0, err
        assert out.strip() == "completed"
        assert load_acquisition_state(path)["count"] == 2
    finally:
        for child in children:
            if child.poll() is None:
                child.kill()
            child.communicate(timeout=5)


@WINDOWS
@pytest.mark.parametrize("grant", ["*S-1-1-0:(OI)(CI)R", "*S-1-5-11:(OI)(CI)R"])
def test_windows_rejects_shared_configured_root_without_changing_acl(private_root, grant):
    _icacls(private_root, "/grant", grant)  # Everyone / Authenticated Users
    before = _icacls(private_root)
    with pytest.raises(PermissionError, match="private storage"):
        private_dir(private_root)
    with pytest.raises(PermissionError, match="private storage"):
        save_acquisition_state({"state": "scheduled"}, private_root / "new" / "state.json")
    with pytest.raises(PermissionError, match="private storage"):
        append_import_run({"created": 0}, private_root / "runs.jsonl")
    with pytest.raises(PermissionError, match="private storage"):
        _append_operator_gate({"reason": "synthetic"}, private_root / "gates.jsonl")
    with pytest.raises(PermissionError, match="private storage"):
        with _acquisition_lock(private_root / "state.json"):
            pytest.fail("privacy refusal must precede transition")
    assert not (private_root / "new").exists()
    assert not list(private_root.iterdir())
    assert _icacls(private_root) == before


@WINDOWS
@pytest.mark.parametrize("kind", ["state", "runs", "gates", "lock"])
def test_windows_rejects_existing_shared_files_before_io(private_root, kind):
    path = _state_and_logs(private_root)
    files = {"state": path, "runs": path.parent / "runs.jsonl",
             "gates": path.parent / "operator-gates.jsonl",
             "lock": path.parent / ".acquisition-state.json.lock"}
    shared = files[kind]
    _icacls(shared, "/grant", "*S-1-1-0:R")
    before, acl = shared.read_bytes(), _icacls(shared)
    with pytest.raises(PermissionError, match="private storage"):
        if kind == "state":
            save_acquisition_state({"state": "scheduled"}, path)
        elif kind == "runs":
            append_import_run({"created": 5}, shared)
        elif kind == "gates":
            _append_operator_gate({"reason": "synthetic"}, shared)
        else:
            with _acquisition_lock(path):
                pytest.fail("shared lock must be refused")
    if kind == "state":
        with pytest.raises(PermissionError, match="private storage"):
            load_acquisition_state(path)
    elif kind == "runs":
        with pytest.raises(PermissionError, match="private storage"):
            last_import_run(shared)
    assert shared.read_bytes() == before
    assert _icacls(shared) == acl


@POSIX
@pytest.mark.parametrize("kind", ["state", "runs", "gates", "lock", "directory"])
def test_posix_refuses_symlinks(private_root, kind):
    victim = private_root / "victim"
    victim.write_text("preserve")
    if kind == "directory":
        link = private_root / "link"
        link.symlink_to(private_root, target_is_directory=True)
        action = lambda: private_dir(link)
    else:
        path = private_root / "state.json"
        link = {"state": path, "runs": private_root / "runs.jsonl",
                "gates": private_root / "gates.jsonl", "lock": private_root / ".state.json.lock"}[kind]
        link.symlink_to(victim)
        def action():
            if kind == "state":
                save_acquisition_state({"state": "scheduled"}, path)
            elif kind == "runs":
                append_import_run({}, link)
            elif kind == "gates":
                _append_operator_gate({}, link)
            else:
                with _acquisition_lock(path):
                    pytest.fail("symlink lock must be refused")
    with pytest.raises(OSError):
        action()
    assert victim.read_text() == "preserve"


@POSIX
def test_posix_privacy_failure_is_explicit(private_root, monkeypatch):
    def denied(*args, **kwargs):
        raise PermissionError("synthetic chmod refusal")
    monkeypatch.setattr(Path, "chmod", denied)
    with pytest.raises(PermissionError, match="refusal"):
        save_acquisition_state({"state": "scheduled"}, private_root / "state.json")
    assert not list(private_root.iterdir())


@pytest.mark.parametrize("timeout", [float("inf"), float("nan"), -1])
def test_lock_rejects_unbounded_timeout(private_root, timeout):
    with pytest.raises(ValueError, match="finite"):
        with _acquisition_lock(private_root / "state.json", timeout=timeout):
            pytest.fail("invalid timeout must not enter lock")


# --- Sol review of #178 ------------------------------------------------------------------------------------------------------------------


def test_read_private_bytes_returns_content_and_reports_absence(tmp_path):
    from src.private_state_io import private_dir, private_file, read_private_bytes

    root = tmp_path / "state"
    private_dir(root)
    with pytest.raises(FileNotFoundError):
        read_private_bytes(root / "missing.json")
    with private_file(root / "state.json", os.O_WRONLY | os.O_CREAT | os.O_TRUNC) as fd:
        os.write(fd, b'{"state": "scheduled"}')
    assert read_private_bytes(root / "state.json") == b'{"state": "scheduled"}'


@pytest.mark.skipif(os.name == "nt", reason="O_NOFOLLOW symlink behaviour is POSIX")
def test_read_private_bytes_never_follows_a_symlink_at_the_final_component(tmp_path):
    from src.private_state_io import private_dir, read_private_bytes

    root = tmp_path / "state"
    private_dir(root)
    outside = tmp_path / "elsewhere.json"
    outside.write_text('{"state": "scheduled"}')
    (root / "state.json").symlink_to(outside)
    with pytest.raises(OSError):
        read_private_bytes(root / "state.json")


@pytest.mark.skipif(os.name != "nt", reason="Windows ACL behaviour")
def test_windows_accepts_directories_python_creates_and_still_refuses_broader_grants(tmp_path):
    """Sol: CPython's mkdir(mode=0o700) writes an OWNER RIGHTS allow ACE; the validator used to reject the directories it had just created."""
    import subprocess

    from src.private_state_io import check_private_path, private_dir

    root = tmp_path / "state"
    private_dir(root / "instagram" / "deep")
    check_private_path(root / "instagram" / "deep")
    shared = tmp_path / "shared"
    shared.mkdir()
    subprocess.run(["icacls", str(shared), "/grant", "Everyone:(R)"], check=True, capture_output=True)
    with pytest.raises(PermissionError):
        check_private_path(shared)


@pytest.mark.skipif(os.name == "nt", reason="O_NOFOLLOW symlink behaviour is POSIX")
def test_a_symlinked_state_file_is_refused_not_recovered_as_corruption(tmp_path):
    """Sol: the corruption recovery renames and chmods the path, which for a link acts on its target."""
    from src.instagram_export_job import load_acquisition_state
    from src.private_state_io import PrivateStorageRefused, private_dir

    root = tmp_path / "state"
    private_dir(root)
    target_dir = tmp_path / "runtime-owned"
    target_dir.mkdir(mode=0o755)
    (root / "acquisition-state.json").symlink_to(target_dir)
    with pytest.raises(PrivateStorageRefused):
        load_acquisition_state(root / "acquisition-state.json")
    assert (root / "acquisition-state.json").is_symlink()                    # not renamed
    assert (target_dir.stat().st_mode & 0o777) == 0o755                      # not chmod-ed through the link
    assert not [p for p in root.iterdir() if ".corrupt-" in p.name]


def test_read_private_bytes_refuses_a_file_that_changes_identity_between_check_and_open(tmp_path, monkeypatch):
    from src import private_state_io as psio

    root = tmp_path / "state"
    psio.private_dir(root)
    path = root / "state.json"
    path.write_text('{"state": "scheduled"}')
    real_stat = os.fstat
    other = tmp_path / "other"
    other.write_text("x")
    other_fd = os.open(other, os.O_RDONLY)
    try:
        monkeypatch.setattr(psio.os, "fstat", lambda fd: real_stat(other_fd))
        with pytest.raises(psio.PrivateStorageRefused):
            psio.read_private_bytes(path)
    finally:
        os.close(other_fd)
