#!/usr/bin/env python3
"""home_reentry_inventory.py — read-only host inventory for the future
home-PC re-entry qualification (Workstream I,
docs/aoteru-long-horizon-autonomous-convergence.agent-task.md).

Home is unavailable this session, and this script does NOT hard-code any
imagined home hardware — it is a generic host inventory that can be run
on ANY host (lab, laptop, or home once reachable) to produce the exact
facts a re-entry/promotion decision needs, so home's return costs one
bounded qualification run, not a redesign. Read-only: it never registers,
promotes, or writes anything into config/estate.yaml — that stays a
deliberate, reviewed operator/foreman step per Workstream I's "mere
reachability never implies trust or promotion."

Usage:
    venv/bin/python scripts/home_reentry_inventory.py [--json]
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

_AOTERU_HOME = Path.home() / ".aoteru"
_HOST_LOCAL_PATH = _AOTERU_HOME / "config.local.json"


def _host_identity() -> dict:
    return {
        "hostname": socket.gethostname(),
        "platform": platform.platform(),
        "python_version": platform.python_version(),
    }


def _hardware() -> dict:
    result: dict = {}
    try:
        result["cpu_count"] = os.cpu_count()
    except Exception:
        result["cpu_count"] = None
    result["mem_total_gb"] = None
    try:
        # Matches scripts/agent's own approach — no psutil dependency
        # needed for one field, and this stays consistent with the
        # existing `agent status` host block.
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    result["mem_total_gb"] = round(int(line.split()[1]) / 2**20, 1)
                    break
    except OSError:
        pass
    try:
        usage = shutil.disk_usage(str(PROJECT_ROOT))
        result["disk_total_gb"] = round(usage.total / (1024 ** 3), 1)
        result["disk_free_gb"] = round(usage.free / (1024 ** 3), 1)
    except Exception:
        result["disk_total_gb"] = None
        result["disk_free_gb"] = None
    try:
        gpu = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=5,
        )
        result["gpu"] = gpu.stdout.strip() if gpu.returncode == 0 else None
    except FileNotFoundError:
        result["gpu"] = None
    return result


def _tailscale() -> dict:
    try:
        proc = subprocess.run(["tailscale", "status", "--self", "--json"],
                               capture_output=True, text=True, timeout=8)
    except FileNotFoundError:
        return {"present": False}
    if proc.returncode != 0:
        return {"present": True, "up": False}
    try:
        payload = json.loads(proc.stdout)
        self_info = payload.get("Self") or {}
        return {
            "present": True, "up": True,
            "tailnet_name": self_info.get("DNSName"),
            "tailscale_ips": self_info.get("TailscaleIPs"),
        }
    except Exception:
        return {"present": True, "up": True, "parse_error": True}


def _ollama_models() -> dict:
    url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434") + "/api/tags"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "home-reentry-inventory/1"})
        with urllib.request.urlopen(req, timeout=4) as resp:  # noqa: S310
            payload = json.loads(resp.read().decode("utf-8"))
        models = [m.get("name") for m in payload.get("models", [])]
        return {"reachable": True, "count": len(models), "models": models}
    except (urllib.error.URLError, TimeoutError, OSError):
        return {"reachable": False}


def _config_local_roots() -> dict:
    if not _HOST_LOCAL_PATH.exists():
        return {"configured": False, "path": str(_HOST_LOCAL_PATH)}
    try:
        data = json.loads(_HOST_LOCAL_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        return {"configured": True, "path": str(_HOST_LOCAL_PATH), "error": f"unreadable: {e}"}
    roots = {k: v for k, v in data.items() if k.endswith("_ROOT")}
    resolved = {}
    for name, value in roots.items():
        if value:
            resolved[name] = {"value": value, "exists": Path(value).expanduser().exists()}
        else:
            resolved[name] = {"value": None, "exists": False}
    return {"configured": True, "path": str(_HOST_LOCAL_PATH), "roots": resolved}


def _systemd_units() -> dict:
    patterns = ("odysseus", "misumi", "chromadb")
    try:
        proc = subprocess.run(
            ["systemctl", "list-units", "--type=service", "--all", "--no-legend", "--no-pager"],
            capture_output=True, text=True, timeout=8,
        )
    except FileNotFoundError:
        return {"present": False}
    if proc.returncode not in (0, 1):
        return {"present": True, "error": f"systemctl exited {proc.returncode}"}
    matches = []
    for line in proc.stdout.splitlines():
        # `systemctl list-units` prefixes a failed/degraded unit's line
        # with a bullet (e.g. "● foo.service loaded failed failed ..."),
        # which isn't the unit name — strip any leading non-word marker
        # before taking the first field.
        stripped = line.strip().lstrip("●").strip()
        if not stripped:
            continue
        unit_name = stripped.split()[0]
        if any(p in unit_name.lower() for p in patterns):
            matches.append(unit_name)
    return {"present": True, "matching_units": matches}


def build_inventory() -> dict:
    return {
        "collected_at_host": socket.gethostname(),
        "identity": _host_identity(),
        "hardware": _hardware(),
        "tailscale": _tailscale(),
        "ollama": _ollama_models(),
        "config_local_roots": _config_local_roots(),
        "systemd_units": _systemd_units(),
        "note": (
            "Read-only inventory. Reachability alone never implies trust "
            "or promotion — see docs/aoteru-autonomous-programme-state.md "
            "workstream I. A human/foreman decision to register/promote "
            "this host must happen as a separate, reviewed step."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit raw JSON only")
    args = parser.parse_args()

    inventory = build_inventory()
    if args.json:
        print(json.dumps(inventory, indent=2))
        return 0

    print(f"Host inventory — {inventory['collected_at_host']}")
    print(f"  identity:  {inventory['identity']}")
    print(f"  hardware:  {inventory['hardware']}")
    print(f"  tailscale: {inventory['tailscale']}")
    print(f"  ollama:    reachable={inventory['ollama'].get('reachable')} "
          f"models={inventory['ollama'].get('count')}")
    print(f"  config.local.json roots: {inventory['config_local_roots'].get('roots')}")
    print(f"  systemd units matching odysseus/misumi/chromadb: "
          f"{inventory['systemd_units'].get('matching_units')}")
    print()
    print(inventory["note"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
