#!/usr/bin/env python3
"""Cold-reboot post-boot verification (Workstream J,
docs/aoteru-long-horizon-autonomous-convergence.agent-task.md).

The one human action (an authorised `sudo reboot` of the lab host) must be
sufficient to exercise a complete automated post-boot check afterwards —
this script is that check. It does NOT reboot anything itself and never
will; it only reads live state after a reboot has already happened (or at
any other time, as a standing health check).

Checks, in order, each independent so one failure doesn't hide the rest:

1. systemd unit `odysseus-aoteru-lab.service` is active (skipped, not
   failed, if systemd/the unit isn't present — e.g. running this from a
   non-lab checkout).
2. the app's own `/api/ready` endpoint on 127.0.0.1:7001 returns 200 with
   `ready: true` — reuses src.readiness.check_readiness's own critical-
   subsystem judgement rather than re-deriving a second opinion here.
3. Ollama is reachable on 127.0.0.1:11434.
4. ChromaDB is reachable on 127.0.0.1:8101 (best-effort: the app already
   treats it as a runtime, not startup, dependency — see
   odysseus-aoteru-lab.service's comments — so this is reported, not
   fatal).
5. Tailscale is up and `tailscale serve` shows no funnel/public exposure
   (every route must be "(tailnet only)"; a Funnel line is an immediate
   failure, not a warning).
6. No active ParkLease rows are stale (a lease whose holder crashed before
   a reboot must not silently block the repo forever after the host comes
   back — this only reports it; reclaiming is `agent park`'s job, not
   this script's).

Exit code 0 iff every check that ran passed. Skipped checks (missing
systemd, no `.env`/config a checkout might not have) do not fail the run —
they're printed as SKIP so the operator can see what wasn't exercised.

Usage: `venv/bin/python scripts/cold_reboot_verify.py`
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

APP_URL = os.getenv("COLD_REBOOT_APP_URL", "http://127.0.0.1:7001")
OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
CHROMA_URL = os.getenv("CHROMA_HEALTH_URL", "http://127.0.0.1:8101")
SYSTEMD_UNIT = os.getenv("COLD_REBOOT_UNIT", "odysseus-aoteru-lab.service")


class Result:
    def __init__(self, name: str, status: str, detail: str = ""):
        self.name = name
        self.status = status  # PASS | FAIL | SKIP
        self.detail = detail


def _get(url: str, timeout: float = 4.0, token: str | None = None) -> tuple[int, str]:
    headers = {"User-Agent": "cold-reboot-verify/1"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        return resp.status, resp.read().decode("utf-8", errors="replace")


def check_systemd_unit() -> Result:
    try:
        proc = subprocess.run(
            ["systemctl", "is-active", SYSTEMD_UNIT],
            capture_output=True, text=True, timeout=5,
        )
    except FileNotFoundError:
        return Result("systemd unit", "SKIP", "systemctl not present on this host")
    state = proc.stdout.strip()
    if state == "active":
        return Result("systemd unit", "PASS", f"{SYSTEMD_UNIT} active")
    if proc.returncode == 4:
        return Result("systemd unit", "SKIP", f"{SYSTEMD_UNIT} not installed on this host")
    return Result("systemd unit", "FAIL", f"{SYSTEMD_UNIT} state={state!r}")


def check_app_ready() -> Result:
    # /api/ready is deliberately NOT auth-exempt (app.py's AUTH_EXEMPT_EXACT)
    # — it reveals internal subsystem detail, unlike /api/health's plain
    # liveness ping. Without a token this check falls back to /api/health
    # so a reboot can still be verified end-to-end; export
    # COLD_REBOOT_AUTH_TOKEN (a real API bearer token, never printed here)
    # to exercise the full critical-subsystem judgement instead.
    token = os.getenv("COLD_REBOOT_AUTH_TOKEN")
    if not token:
        try:
            status, _ = _get(f"{APP_URL}/api/health")
        except Exception as e:
            return Result("app liveness", "FAIL", f"unreachable: {e}")
        if status == 200:
            return Result("app liveness", "PASS",
                           "status=200 (liveness only — set COLD_REBOOT_AUTH_TOKEN for full /api/ready)")
        return Result("app liveness", "FAIL", f"status={status}")

    try:
        status, body = _get(f"{APP_URL}/api/ready", token=token)
    except urllib.error.HTTPError as e:
        status, body = e.code, e.read().decode("utf-8", errors="replace")
    except Exception as e:
        return Result("app /api/ready", "FAIL", f"unreachable: {e}")
    try:
        payload = json.loads(body)
    except Exception:
        return Result("app /api/ready", "FAIL", f"non-JSON response (status {status})")
    ready = bool(payload.get("ready"))
    failing = [k for k, v in (payload.get("checks") or {}).items()
               if v.get("critical") and not v.get("ok")]
    if ready:
        return Result("app /api/ready", "PASS", f"status={status}")
    return Result("app /api/ready", "FAIL", f"status={status} failing critical checks={failing}")


def check_ollama() -> Result:
    try:
        status, _ = _get(f"{OLLAMA_URL}/api/tags")
        if status == 200:
            return Result("ollama", "PASS", OLLAMA_URL)
        return Result("ollama", "FAIL", f"status={status}")
    except Exception as e:
        return Result("ollama", "FAIL", f"unreachable: {e}")


def check_chroma() -> Result:
    for path in ("/api/v2/heartbeat", "/api/v1/heartbeat"):
        try:
            status, _ = _get(f"{CHROMA_URL}{path}")
            if status == 200:
                return Result("chromadb", "PASS", f"{CHROMA_URL}{path}")
        except Exception:
            continue
    return Result("chromadb", "SKIP", f"{CHROMA_URL} not reachable — runtime, not startup, dependency")


def check_tailscale_private_only() -> Result:
    try:
        status_proc = subprocess.run(["tailscale", "status", "--json"], capture_output=True, text=True, timeout=8)
    except FileNotFoundError:
        return Result("tailscale private-only", "SKIP", "tailscale binary not present")
    if status_proc.returncode != 0:
        return Result("tailscale private-only", "FAIL", "tailscale status failed — is tailscaled running?")
    try:
        serve_proc = subprocess.run(["tailscale", "serve", "status"], capture_output=True, text=True, timeout=8)
    except FileNotFoundError:
        return Result("tailscale private-only", "SKIP", "tailscale serve not available")
    output = serve_proc.stdout
    lines = [ln for ln in output.splitlines() if ln.strip().startswith("http")]
    non_private = [ln for ln in lines if "tailnet only" not in ln]
    if non_private:
        return Result("tailscale private-only", "FAIL", f"non-tailnet-only route(s): {non_private}")
    if not lines:
        return Result("tailscale private-only", "SKIP", "no `tailscale serve` routes configured")
    return Result("tailscale private-only", "PASS", f"{len(lines)} route(s), all tailnet-only")


def check_park_leases() -> Result:
    try:
        from core.database import ParkLease, get_db_session, park_lease_is_stale
    except Exception as e:
        return Result("park leases", "SKIP", f"could not import core.database: {e}")
    try:
        with get_db_session() as session:
            active = session.query(ParkLease).filter(ParkLease.status == "active").all()
            stale = [row for row in active if park_lease_is_stale(row)]
    except Exception as e:
        return Result("park leases", "FAIL", f"query failed: {e}")
    if stale:
        ids = [f"{row.repo_id}@{row.host_id}" for row in stale]
        return Result("park leases", "FAIL",
                       f"{len(stale)} stale active lease(s) will block their repo until reclaimed: {ids}")
    return Result("park leases", "PASS", f"{len(active)} active lease(s), none stale")


def main() -> int:
    checks = [
        check_systemd_unit(),
        check_app_ready(),
        check_ollama(),
        check_chroma(),
        check_tailscale_private_only(),
        check_park_leases(),
    ]
    width = max(len(c.name) for c in checks)
    for c in checks:
        print(f"[{c.status:4}] {c.name.ljust(width)}  {c.detail}")
    failed = [c for c in checks if c.status == "FAIL"]
    print()
    if failed:
        print(f"COLD-REBOOT VERIFICATION: FAIL ({len(failed)}/{len(checks)} checks failed)")
        return 1
    print("COLD-REBOOT VERIFICATION: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
