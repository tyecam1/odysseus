"""The backup task principal comes from the Windows token, never from $env:USERDOMAIN.

Found by the 2026-10-06 restore drill: in an SSH session USERDOMAIN read WORKGROUP, and registering the task as
WORKGROUP\\user fails (HRESULT 0x80070534). The static checks run everywhere; the behavioural check needs Windows PowerShell.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "windows" / "odysseus-backup-task.ps1"
POWERSHELL = shutil.which("powershell")
windows_only = pytest.mark.skipif(sys.platform != "win32" or not POWERSHELL, reason="Windows PowerShell required")


def _code_lines():
    text = SCRIPT.read_text(encoding="utf-8-sig")
    body = text.split("#>", 1)[1]
    return [line for line in body.splitlines() if not line.strip().startswith("#")]


def test_the_task_principal_never_reads_the_ambient_domain_variable():
    assert not [line for line in _code_lines() if "USERDOMAIN" in line]


def test_the_task_principal_is_the_windows_token_identity():
    code = "\n".join(_code_lines())
    assert "[Security.Principal.WindowsIdentity]::GetCurrent().Name" in code
    assert "New-ScheduledTaskPrincipal -UserId $taskIdentity -LogonType S4U -RunLevel Limited" in code


@windows_only
def test_the_script_parses_cleanly():
    out = subprocess.run(
        [POWERSHELL, "-NoProfile", "-Command",
         f"$e=$null; [void][System.Management.Automation.Language.Parser]::ParseFile('{SCRIPT}', [ref]$null, [ref]$e); $e.Count"],
        capture_output=True, text=True,
    )
    assert out.stdout.strip() == "0"


@windows_only
def test_install_whatif_reports_the_token_identity_even_when_userdomain_is_wrong(tmp_path):
    expected = subprocess.run(
        [POWERSHELL, "-NoProfile", "-Command", "[Security.Principal.WindowsIdentity]::GetCurrent().Name"],
        capture_output=True, text=True,
    ).stdout.strip()
    env = dict(os.environ, USERDOMAIN="BOGUSDOMAIN")
    out = subprocess.run(
        [POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(SCRIPT), "-Action", "Install",
         "-SourceRoot", str(tmp_path), "-StagingDir", str(tmp_path / "staging"), "-TaskName", "Odysseus-Backup-pytest-whatif", "-WhatIf"],
        capture_output=True, text=True, env=env,
    )
    assert out.returncode == 0, out.stderr
    assert "BOGUSDOMAIN" not in out.stdout
    assert f"as {expected}, S4U" in out.stdout
