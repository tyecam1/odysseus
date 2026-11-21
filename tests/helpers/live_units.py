"""Safe handling of real `aoteru-*` systemd user units from live tests.

A live test must never signal a unit it did not start: on the execution host those units are real
workers (a paid writer mid-run). See tests/test_live_unit_hygiene.py."""
import os
import subprocess

BUSY_STATES = frozenset({"active", "activating", "deactivating", "reloading"})


def _env():
    return {**os.environ, "XDG_RUNTIME_DIR": os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")}


def _rows(run=subprocess.run):
    out = run(["systemctl", "--user", "list-units", "--all", "--no-legend", "aoteru-*"],
              capture_output=True, text=True, env=_env()).stdout
    for line in out.splitlines():
        fields = line.split()
        # systemctl prefixes a failed/problem unit with a bullet that is its own field.
        while fields and not any(ch.isalnum() for ch in fields[0]):
            fields = fields[1:]
        if fields:
            yield fields[0], (fields[2] if len(fields) > 2 else "")


def active_units(run=subprocess.run):
    """Every loaded aoteru-* unit (including stopped/failed ones)."""
    return {unit for unit, _state in _rows(run)}


def busy_units(run=subprocess.run):
    """aoteru-* units that are running or starting: a real worker is busy on this host."""
    return {unit for unit, state in _rows(run) if state in BUSY_STATES}


def stop_units_started_since(before, run=subprocess.run):
    """SIGKILL only units that appeared after the `before` snapshot (the test's own)."""
    for unit in sorted(active_units(run) - set(before)):
        run(["systemctl", "--user", "kill", "--signal=KILL", unit], capture_output=True, env=_env())
