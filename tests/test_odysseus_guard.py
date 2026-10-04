"""Behaviour tests for scripts/windows/odysseus-guard.ps1 (Windows PowerShell; skipped elsewhere).

Each "service" is a tiny local HTTP server whose health is a marker file, and the recovery/stop actions are injected commands, so the
real decision logic runs end to end without touching scheduled tasks or the real runtime.
"""

import json
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GUARD = ROOT / "scripts" / "windows" / "odysseus-guard.ps1"
HOST = ROOT / "scripts" / "windows" / "odysseus-host.ps1"
POWERSHELL = shutil.which("powershell")

pytestmark = pytest.mark.skipif(sys.platform != "win32" or not POWERSHELL, reason="Windows PowerShell required")


def _server(marker: Path):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            self.send_response(200 if marker.exists() else 503)
            self.end_headers()
            self.wfile.write(b"{}")

        def log_message(self, *args):
            pass

    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


class Harness:
    def __init__(self, tmp: Path):
        self.tmp = tmp
        self.up_od, self.up_ol = tmp / "up_od", tmp / "up_ol"
        self.rec_od, self.rec_ol = tmp / "rec_od.log", tmp / "rec_ol.log"
        self.od, self.ol = _server(self.up_od), _server(self.up_ol)
        self.state = tmp / "state"

    def set_up(self, od: bool, ol: bool):
        for marker, on in ((self.up_od, od), (self.up_ol, ol)):
            if on:
                marker.write_text("up")
            elif marker.exists():
                marker.unlink()

    def calls(self, log: Path) -> int:
        return len(log.read_text().splitlines()) if log.exists() else 0

    def run(self, action: str, *extra: str, fix: bool = True, wait: int = 6):
        rec_od = f"Add-Content -Path '{self.rec_od}' -Value x" + (f"; Set-Content -Path '{self.up_od}' -Value up" if fix else "")
        rec_ol = f"Add-Content -Path '{self.rec_ol}' -Value x" + (f"; Set-Content -Path '{self.up_ol}' -Value up" if fix else "")
        stop_od = f"if (Test-Path '{self.up_od}') {{ Remove-Item '{self.up_od}' }}"
        stop_ol = f"if (Test-Path '{self.up_ol}') {{ Remove-Item '{self.up_ol}' }}"
        cmd = [POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(GUARD), "-Action", action,
               "-StateDir", str(self.state), "-DataRoot", str(self.tmp),
               "-OdysseusHealthUrl", f"http://127.0.0.1:{self.od.server_port}/h", "-OllamaHealthUrl", f"http://127.0.0.1:{self.ol.server_port}/h",
               "-RecoverOdysseusCommand", rec_od, "-RecoverOllamaCommand", rec_ol,
               "-StopOdysseusCommand", stop_od, "-StopOllamaCommand", stop_ol, "-RecoveryWaitSeconds", str(wait), *extra]
        return subprocess.run(cmd, capture_output=True, text=True, timeout=120)

    def evidence(self):
        p = self.state / "guard.jsonl"
        return [json.loads(line) for line in p.read_text(encoding="utf-8-sig").splitlines()] if p.exists() else []

    def close(self):
        self.od.shutdown(); self.ol.shutdown()


@pytest.fixture
def h():
    tmp = Path(tempfile.mkdtemp(prefix="guard-"))
    harness = Harness(tmp)
    yield harness
    harness.close()
    shutil.rmtree(tmp, ignore_errors=True)


def test_both_scripts_parse_cleanly():
    for script in (GUARD, HOST):
        out = subprocess.run([POWERSHELL, "-NoProfile", "-Command",
                              f"$e=$null; [void][System.Management.Automation.Language.Parser]::ParseFile('{script}', [ref]$null, [ref]$e); $e.Count"],
                             capture_output=True, text=True)
        assert out.stdout.strip() == "0", script


def test_the_wrapper_offers_a_boot_start_mode_with_the_required_properties():
    text = HOST.read_text(encoding="utf-8")
    assert "[switch]$BootStart" in text
    for needle in ("New-ScheduledTaskTrigger -AtStartup", "-LogonType S4U", "-StartWhenAvailable", "-MultipleInstances IgnoreNew", "-RestartCount 10"):
        assert needle in text, needle
    assert "session={2}" in text                      # the supervisor records which session it lives in
    guard = GUARD.read_text(encoding="utf-8")
    assert "SYSTEM" not in guard.split("#>")[1] or "-LogonType S4U" in guard   # least privilege: S4U as the same user, never SYSTEM
    assert "RunLevel Limited" in guard
    # Registering with DOMAIN\user failed on the household host (HRESULT 0x80070534, no account mapping); the tasks that work there use the plain user name.
    for text in (guard, HOST.read_text(encoding="utf-8")):
        assert "USERDOMAIN" not in text
        assert "-UserId $env:USERNAME" in text


def test_healthy_services_cause_no_action(h):
    h.set_up(True, True)
    for _ in range(3):
        assert h.run("Watch").returncode == 0
    assert h.calls(h.rec_od) == 0 and h.calls(h.rec_ol) == 0
    assert h.evidence() == []                         # quiet when nothing happens


def test_a_single_failed_probe_is_tolerated_and_two_trigger_exactly_one_recovery(h):
    h.set_up(False, True)
    assert h.run("Watch").returncode == 0
    assert h.calls(h.rec_od) == 0                     # first failure: wait
    assert h.run("Watch").returncode == 0
    assert h.calls(h.rec_od) == 1                     # second consecutive failure: recover once
    assert h.calls(h.rec_ol) == 0                     # the healthy service is never touched
    assert h.run("Watch").returncode == 0
    assert h.calls(h.rec_od) == 1                     # recovered, so no repeat
    rec = [e for e in h.evidence() if e["kind"] == "recovery"]
    assert len(rec) == 1 and rec[0]["service"] == "odysseus" and rec[0]["healthy_after"] is True


def test_recovery_that_does_not_work_is_reported_not_hidden(h):
    h.set_up(True, False)
    h.run("Watch", fix=False, wait=3)
    result = h.run("Watch", fix=False, wait=3)
    assert result.returncode == 2
    rec = [e for e in h.evidence() if e["kind"] == "recovery"]
    assert rec and rec[-1]["service"] == "ollama" and rec[-1]["healthy_after"] is False


def test_maintenance_stays_stopped_and_is_not_fought_then_release_recovers(h):
    h.set_up(True, True)
    entered = h.run("MaintenanceEnter", "-Reason", "kiosk outage acceptance", "-MaintenanceHours", "1")
    assert entered.returncode == 0, entered.stderr
    assert not h.up_od.exists() and not h.up_ol.exists()   # governed stop took both down
    for _ in range(4):
        assert h.run("Watch").returncode == 0
    assert h.calls(h.rec_od) == 0 and h.calls(h.rec_ol) == 0   # the guard never restarted anything
    kinds = {e["kind"] for e in h.evidence()}
    assert "suppressed" in kinds and "recovery" not in kinds
    released = h.run("MaintenanceRelease")
    assert released.returncode == 0, released.stderr
    assert h.calls(h.rec_od) == 1 and h.calls(h.rec_ol) == 1   # released: both come back at once
    assert h.up_od.exists() and h.up_ol.exists()


def test_an_expired_maintenance_flag_cannot_leave_the_stack_down(h):
    h.set_up(False, False)
    h.state.mkdir(parents=True, exist_ok=True)
    (h.state / "maintenance.json").write_text(json.dumps({"reason": "forgotten", "entered": "2020-01-01T00:00:00", "expires": "2020-01-01T01:00:00", "by": "t"}))
    h.run("Watch"); h.run("Watch")
    assert not (h.state / "maintenance.json").exists()
    assert h.calls(h.rec_od) == 1 and h.calls(h.rec_ol) == 1
    assert any(e["kind"] == "maintenance" and e.get("event") == "expired" for e in h.evidence())


def test_maintenance_is_bounded_and_needs_a_reason(h):
    h.set_up(True, True)
    assert h.run("MaintenanceEnter").returncode != 0              # no reason
    h.run("MaintenanceEnter", "-Reason", "long job", "-MaintenanceHours", "99")
    flag = json.loads((h.state / "maintenance.json").read_text(encoding="utf-8-sig"))
    entered, expires = flag["entered"], flag["expires"]
    from datetime import datetime
    span = (datetime.fromisoformat(expires[:26]) - datetime.fromisoformat(entered[:26])).total_seconds() / 3600
    assert span <= 6.01                                           # capped at MaxMaintenanceHours


def test_status_is_clean_json_with_plain_evidence_lines(h):
    h.set_up(False, True)
    h.run("Watch"); h.run("Watch")                                      # leave some evidence behind
    out = h.run("Status")
    assert out.returncode == 0, out.stderr
    status = json.loads(out.stdout)
    assert status["odysseus_healthy"] is True and status["ollama_healthy"] is True
    assert status["maintenance"] is None
    lines = status["recent_evidence"]
    assert lines and all(isinstance(line, str) for line in lines)      # plain strings, not file-provider objects
    assert "PSPath" not in out.stdout
    assert "/Date(" not in out.stdout                                   # dates are ISO strings
