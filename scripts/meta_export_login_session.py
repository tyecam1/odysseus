#!/usr/bin/env python3
"""One-time interactive Meta/Instagram login session for the P2 real-export
gate (docs: external-ingest programme).

Launches a real Chromium browser, headless=new (Chrome 112+'s fully-
rendering headless mode - no Xvfb/X server/VNC needed at all: this is not
a screenshot-only mode, it renders exactly as a headed browser would),
with Chrome DevTools Protocol remote debugging bound to 127.0.0.1 ONLY.
The user reaches it over their EXISTING authenticated SSH/Tailscale path
from their laptop - never a new network exposure - and interacts with the
live page through Chrome's own remote-debugging inspector, typing their
password directly into the rendered page exactly as they would locally.
No credential, password, or 2FA code is ever read, logged, or handled by
this script - it never sees keystrokes; the browser renders the real Meta
page and the user's own local Chrome sends input directly to it over the
tunnelled DevTools Protocol connection.

Same existing Meta/Instagram account the user already uses on their
phone. This script does not create, does not assume, and has no concept
of a second account or identity - see the module docstring of
src/meta_export_automation.py for the steady-state automation that reuses
whatever session this launcher lets the user establish.

Usage (on the lab host, over SSH):

    python3 scripts/meta_export_login_session.py start [--port 9333] [--minutes 30]
    python3 scripts/meta_export_login_session.py stop
    python3 scripts/meta_export_login_session.py status

On the USER'S OWN laptop, in a separate terminal, while `start` is
running:

    ssh -L 9333:127.0.0.1:9333 agent@<lab-host>

Then in the user's own local Chrome/Chromium browser:

    1. open chrome://inspect/#devices
    2. click "Configure..." next to "Discover network targets" and add
       localhost:9333
    3. the remote page appears under "Remote Target" - click "inspect"

That opens a live, fully interactive mirrored view of the real browser
running on the lab - the user can see the page, click, and type their
password directly into it, and approve any Meta security/passkey prompt
on their phone exactly as they normally would. No VNC, no noVNC, no new
publicly-reachable service: the debugging port is bound to 127.0.0.1 on
the lab and only ever reachable through the SSH tunnel the user already
authenticates with.

`start` blocks in the foreground (intended to be run under an outer
`timeout`, or in a background job the operator manages) until either the
bounded lifetime elapses or `stop` is run from another shell - at which
point the browser process is terminated. It never lingers past its own
bounded window: this is a temporary presentation service for one login,
not a persistent server.

The browser's persistent profile (cookies/session state for the
authenticated account) is written to PROFILE_DIR with restrictive
(0700) permissions and is what src/meta_export_automation.py reuses
afterward, headless and with no debugging port exposed at all, for the
actual bounded, policy-gated export workflow.
"""
from __future__ import annotations

import argparse
import glob
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

PROFILE_DIR = Path.home() / ".aoteru" / "meta-export-browser-profile"
STATE_DIR = Path.home() / ".aoteru" / "meta-export-login-session"
PID_FILE = STATE_DIR / "chrome.pid"
STOP_FLAG = STATE_DIR / "stop"

DEFAULT_PORT = 9333
DEFAULT_MINUTES = 30

# Meta/Instagram's own login entry point - the safest, most stable place
# to start: no export-specific navigation happens automatically here, the
# user drives everything themselves once the tunnel is open.
START_URL = "https://www.instagram.com/accounts/login/"


def _find_chromium_binary() -> str:
    """Locate the Playwright-managed Chromium binary already installed
    for this host (shared with src/meta_export_automation.py - both use
    the same ~/.cache/ms-playwright cache and the same persistent
    profile, so a session established here is exactly what the steady-
    state automation reuses)."""
    candidates = sorted(
        glob.glob(str(Path.home() / ".cache" / "ms-playwright" / "chromium-*" / "chrome-linux64" / "chrome")),
        reverse=True,
    )
    if candidates:
        return candidates[0]
    raise SystemExit(
        "no Playwright-managed Chromium found under ~/.cache/ms-playwright - "
        "run `python3 -m playwright install chromium` once first (or "
        "`npx playwright install chromium`, same shared cache either way)"
    )


def cmd_start(args: argparse.Namespace) -> int:
    if PID_FILE.exists():
        try:
            existing_pid = int(PID_FILE.read_text().strip())
            os.kill(existing_pid, 0)
            print(f"a login session is already running (pid {existing_pid}) - run `stop` first")
            return 1
        except (ValueError, ProcessLookupError, PermissionError):
            PID_FILE.unlink(missing_ok=True)

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(STATE_DIR, 0o700)
    STOP_FLAG.unlink(missing_ok=True)

    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(PROFILE_DIR, 0o700)

    chrome = _find_chromium_binary()
    port = args.port
    minutes = args.minutes

    proc = subprocess.Popen(
        [
            chrome,
            "--headless=new",
            f"--remote-debugging-port={port}",
            "--remote-debugging-address=127.0.0.1",
            f"--user-data-dir={PROFILE_DIR}",
            "--no-first-run",
            "--no-default-browser-check",
            START_URL,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    PID_FILE.write_text(str(proc.pid))

    print(f"Meta/Instagram login session started (pid {proc.pid}), bounded to {minutes} minutes.")
    print(f"Remote debugging bound to 127.0.0.1:{port} on this host ONLY - not reachable over the network directly.")
    print()
    print("On your OWN laptop, in a separate terminal:")
    print(f"    ssh -L {port}:127.0.0.1:{port} agent@<this-lab-host>")
    print()
    print("Then in your own local Chrome/Chromium:")
    print("    1. open chrome://inspect/#devices")
    print(f"    2. click \"Configure...\" next to \"Discover network targets\", add localhost:{port}")
    print("    3. the remote page appears under \"Remote Target\" - click \"inspect\"")
    print()
    print("Log in with your existing Instagram/Meta account exactly as normal; approve")
    print("any security/passkey prompt on your phone as usual. Your password is typed")
    print("directly into the real remote page - this script never sees it.")
    print()
    print(f"This session will shut itself down automatically after {minutes} minutes, or run:")
    print("    python3 scripts/meta_export_login_session.py stop")
    print("from another shell to end it as soon as you are done.")

    deadline = time.monotonic() + minutes * 60
    try:
        while time.monotonic() < deadline:
            if STOP_FLAG.exists():
                print("stop requested - shutting down the login session.")
                break
            if proc.poll() is not None:
                print("browser process exited on its own.")
                break
            time.sleep(2)
        else:
            print(f"{minutes} minute bound reached - shutting down the login session.")
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
        PID_FILE.unlink(missing_ok=True)
        STOP_FLAG.unlink(missing_ok=True)

    print("Login session ended. The authenticated profile (if login succeeded) "
          f"persists at {PROFILE_DIR} for the steady-state automation to reuse.")
    return 0


def cmd_stop(args: argparse.Namespace) -> int:
    if not PID_FILE.exists():
        print("no login session is currently recorded as running")
        return 0
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STOP_FLAG.write_text("stop")
    print("stop requested - the running `start` process will shut down within a few seconds")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    if not PID_FILE.exists():
        print("no login session is currently running")
        return 0
    pid = int(PID_FILE.read_text().strip())
    try:
        os.kill(pid, 0)
        print(f"login session running (pid {pid})")
        return 0
    except ProcessLookupError:
        print("stale pid file found (process no longer exists) - cleaning up")
        PID_FILE.unlink(missing_ok=True)
        return 0


def main(argv: list[str] | None = None) -> int:
    # Line-buffer stdout even when redirected to a file/pipe (e.g. a
    # backgrounded `nohup ... &`) so the printed connection instructions
    # are visible immediately rather than sitting in a block buffer until
    # the process exits.
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)

    p_start = sub.add_parser("start", help="launch the temporary interactive login session")
    p_start.add_argument("--port", type=int, default=DEFAULT_PORT)
    p_start.add_argument("--minutes", type=int, default=DEFAULT_MINUTES)

    sub.add_parser("stop", help="signal a running session to shut down")
    sub.add_parser("status", help="check whether a session is currently running")

    args = parser.parse_args(argv)
    handlers = {"start": cmd_start, "stop": cmd_stop, "status": cmd_status}
    return handlers[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
