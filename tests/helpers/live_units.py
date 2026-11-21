"""Safe handling of real `aoteru-*` systemd user units from live tests.

A live test must never signal a unit it did not start: on the execution host those units are real
workers (a paid writer mid-run). Units are named after the execution / lease ids that created them, so
cleanup kills only units carrying an id the TEST ITSELF created; a real worker that happens to start
while the test runs can never match. See tests/test_live_unit_hygiene.py."""
import os
import subprocess

BUSY_STATES = frozenset({"active", "activating", "deactivating", "reloading"})


def _env():
    return {**os.environ, "XDG_RUNTIME_DIR": os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")}


def _rows(run=subprocess.run):
    done = run(["systemctl", "--user", "list-units", "--all", "--no-legend", "aoteru-*"],
               capture_output=True, text=True, env=_env())
    if getattr(done, "returncode", 0) != 0:
        # An unreadable listing must never look like "no units": that would disable the busy-skip.
        raise RuntimeError("systemctl --user list-units failed: " + str(getattr(done, "stderr", ""))[:200])
    for line in (done.stdout or "").splitlines():
        fields = line.split()
        # systemctl prefixes a failed/problem unit with a bullet that is its own field.
        while fields and not any(ch.isalnum() for ch in fields[0]):
            fields = fields[1:]
        if fields:
            yield fields[0], (fields[2] if len(fields) > 2 else "")


def active_units(run=subprocess.run):
    """Every loaded aoteru-* unit (including stopped/failed ones). Raises if systemctl cannot be read."""
    return {unit for unit, _state in _rows(run)}


def busy_units(run=subprocess.run):
    """aoteru-* units that are running or starting: a real worker is busy on this host."""
    return {unit for unit, state in _rows(run) if state in BUSY_STATES}


def wait_until_idle(timeout=20.0, interval=1.0, run=subprocess.run, sleep=None, clock=None):
    """Busy units still present after `timeout` seconds. Short-lived `aoteru-verify-*` units (which carry
    no execution id) left by a previous test drain quickly; a real paid writer does not."""
    import time
    sleep, clock = sleep or time.sleep, clock or time.monotonic
    deadline = clock() + timeout
    busy = busy_units(run)
    while busy and clock() < deadline:
        sleep(interval)
        busy = busy_units(run)
    return busy


def stop_units_started_since(before, owned_ids, run=subprocess.run):
    """SIGKILL only units that are new since `before` AND carry an id the test created."""
    owned = {i for i in owned_ids if isinstance(i, str) and i}
    if not owned:
        return
    try:
        units = active_units(run)
    except RuntimeError:
        return                      # cannot read the host's units: kill nothing
    for unit in sorted(units - set(before)):
        if any(i in unit for i in owned):
            run(["systemctl", "--user", "kill", "--signal=KILL", unit], capture_output=True, env=_env())
