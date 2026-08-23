#!/usr/bin/env python3
"""glovebox_qualification.py — read-only experiment-edge inventory/
qualification for the glovebox Jetson Orin Nano (Workstream G,
docs/aoteru-long-horizon-autonomous-convergence.agent-task.md).

Glovebox has been offline on tailnet for 36+ days as of this session
(config/estate.yaml, re-checked live via `tailscale status` this session —
still offline, unchanged). This script cannot be run against the real
device this session; it is the exact deployable artefact + one operator
command described in G's own closing instruction: "If [Jetson] is not
[reachable], leave exactly one operator command/procedure." That command
is:

    ssh glovebox 'python3 glovebox_qualification.py'

(or copy this one file over, same no-checkout-required spirit as the
laptop client). Reuses scripts/home_reentry_inventory.py's generic
host/hardware/Tailscale facts rather than duplicating them, and adds only
the glovebox-specific checks: JetPack/L4T version, ROS 2 presence,
RealSense (librealsense/pyrealsense2), and Jetson thermal/power via
`tegrastats` — none of which a generic x86 lab/laptop host has.

Read-only. Never registers/promotes the host, never runs a general-purpose
LLM (Workstream G: "Never run generic background LLMs on Jetson by
default") — this script makes zero model calls.

CAVEAT: the Jetson-specific checks below are written from documented
JetPack/L4T/ROS2/RealSense conventions (standard file paths, standard CLI
tool names), NOT verified live against actual glovebox hardware, since
this session cannot reach it. Treat any check here that turns out wrong
against the real device as a bug report, not settled fact — this is
explicitly flagged rather than presented as already-proven.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPTS_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(SCRIPTS_DIR))

import home_reentry_inventory as _generic  # noqa: E402  (same scripts/ dir)


def _jetpack_l4t_version() -> dict:
    # Standard JetPack/L4T location. UNVERIFIED against real hardware —
    # see module docstring.
    release_file = Path("/etc/nv_tegra_release")
    if not release_file.exists():
        return {"present": False, "path": str(release_file)}
    try:
        content = release_file.read_text(encoding="utf-8", errors="replace").strip()
        return {"present": True, "path": str(release_file), "raw": content}
    except OSError as e:
        return {"present": True, "path": str(release_file), "error": str(e)}


def _ros2() -> dict:
    binary = shutil.which("ros2")
    if not binary:
        return {"present": False}
    try:
        proc = subprocess.run(["ros2", "--version"], capture_output=True, text=True, timeout=5)
        return {"present": True, "binary": binary, "version": proc.stdout.strip() or proc.stderr.strip()}
    except Exception as e:
        return {"present": True, "binary": binary, "error": str(e)}


def _realsense() -> dict:
    result: dict = {}
    rs_binary = shutil.which("realsense-viewer") or shutil.which("rs-enumerate-devices")
    result["librealsense_cli"] = {"present": bool(rs_binary), "binary": rs_binary}
    try:
        import importlib.util
        result["pyrealsense2"] = {"present": importlib.util.find_spec("pyrealsense2") is not None}
    except Exception:
        result["pyrealsense2"] = {"present": False}
    return result


def _thermals_power() -> dict:
    # tegrastats prints one line and exits with --interval/--count on
    # newer L4T; older ones only stream. Bound with a hard timeout either
    # way so a hang can't block the whole qualification run.
    binary = shutil.which("tegrastats")
    if not binary:
        return {"present": False}
    try:
        proc = subprocess.run([binary, "--interval", "1000"], capture_output=True, text=True, timeout=3)
        line = (proc.stdout or proc.stderr).strip().splitlines()[0] if (proc.stdout or proc.stderr) else ""
        return {"present": True, "sample_line": line}
    except subprocess.TimeoutExpired as e:
        # Expected for the streaming (non --count) variant — the process
        # itself proves tegrastats is present and runs even though this
        # script deliberately doesn't wait for a full line.
        partial = (e.stdout or b"").decode("utf-8", errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
        return {"present": True, "sample_line": partial.strip().splitlines()[0] if partial.strip() else None,
                "note": "tegrastats streams continuously on some L4T versions; killed after timeout, which is expected"}
    except Exception as e:
        return {"present": True, "error": str(e)}


def build_qualification() -> dict:
    report = _generic.build_inventory()
    report["role"] = "experiment-edge"
    report["jetpack_l4t"] = _jetpack_l4t_version()
    report["ros2"] = _ros2()
    report["realsense"] = _realsense()
    report["thermals_power"] = _thermals_power()
    report["candidate_capability_tags"] = ["ros2", "realsense", "experiment-capture", "edge-perception", "robotics-logs"]
    report["note"] = (
        "Read-only qualification. Matches config/estate.yaml's glovebox "
        "candidate_capability_tags vocabulary but does NOT itself make "
        "any tag live/binding — that stays a reviewed operator/foreman "
        "step. Never runs a general-purpose LLM on this device."
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = build_qualification()
    if args.json:
        print(json.dumps(report, indent=2))
        return 0

    print(f"Glovebox qualification — {report['collected_at_host']}")
    print(f"  hardware:    {report['hardware']}")
    print(f"  jetpack_l4t: {report['jetpack_l4t']}")
    print(f"  ros2:        {report['ros2']}")
    print(f"  realsense:   {report['realsense']}")
    print(f"  thermals:    {report['thermals_power']}")
    print(f"  tailscale:   {report['tailscale']}")
    print()
    print(report["note"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
