"""Deterministic FT-00 Freqtrade dry-run guard and runner.

Task card ``agent-tasks/inbox/finance-paper-trading-goals-2026-10-29.md``
(canonical spec ``misumi/docs/core/finance-paper-trading-goals-v0.1.md``,
goal FT-00: "Attest safe paper-only environment").

The guard is fail-closed: a configuration is runnable only when EVERY
safety property holds (simulation-only, spot, no credentials, no
leverage/margin/derivatives, no public listeners, exactly the pinned
official image, workspace outside the knowledgebase). Anything ambiguous
is rejected. Overlay routes around the verified configuration —
``add_config_files`` in the config, or extra ``--config``/``--userdir``/
``--strategy`` freqtrade arguments — are rejected outright. The runner
never sends anything but ``docker`` commands against the pinned image;
there is no exchange credential path and no order routing other than
Freqtrade's own simulated wallet.

Deployment fact (observed live against the pinned digest 2026-10-29):
a running freqtrade container recursively re-chowns the mounted
user_data tree to its internal user (uid 1000 — a different account on
the host), so the invoking user cannot keep write access to the
workspace across runs. The verified-config snapshot write/cleanup is
therefore DELEGATED to one-shot pinned-image containers (stdin -> file,
and rm) whenever a direct write is not permitted, with the bytes
re-read from the host afterwards to assert the round trip.

Simulation only. This module must never be used to place real orders —
real-money execution requires a separately ratified authority that this
programme does not hold (see misumi finance framework).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

RUNNER_NAME = "finance-ft-runner"
RUNNER_VERSION = "0.1"

# Official image pinned by digest (tag ``stable`` resolved 2026-10-29,
# image created 2026-09-29, Python 3.14.7 / CCXT 4.5.84). The guard
# requires this reference EXACTLY: a digest alone proves nothing about
# which repository it names, so ``evil/freqtrade@sha256:<same digest>``
# must not pass, and a bare tag is never accepted — pinning must be by
# digest so a re-pulled "stable" cannot silently change the engine under
# an attestation.
DEFAULT_PINNED_IMAGE = (
    "freqtradeorg/freqtrade@sha256:"
    "9d67afb8eb5f4e1210f4fb067efcbd5e005bd4f1c27f6f3888b8b9fc7f9b5199"
)
DIGEST_RE = re.compile(r"^[a-z0-9./_-]+@sha256:[0-9a-f]{64}$")
SPOT_PAIR_RE = re.compile(r"^[A-Z0-9.]+/[A-Z0-9.]+$")
TIMEFRAME_RE = re.compile(r"^\d+[smhd]$")
TIMERANGE_RE = re.compile(r"^\d{8}(-\d{8})?(-)?$")

# Extra freqtrade arguments are restricted to this allowlist. Freqtrade
# merges multiple --config files with later files taking precedence and
# lets --userdir/--strategy/--db-url override verified values, so those
# (and anything unrecognised) are refused: they could re-introduce
# credentials, derivatives settings or listeners the guard just rejected.
ALLOWED_EXTRA_FLAGS = {
    "--dl-trades", "--erase", "--prepend",
    "--timerange", "--days", "--new-pairs-days",
}
VALUE_EXTRA_FLAGS = {"--timerange", "--days", "--new-pairs-days"}

# The TYPED data channel (--pairs/--timeframe/--timerange -> data_args) is
# validated by the same grammar the CLI applies: these flags, these value
# shapes. data_args reaches docker only through build_docker_argv, which
# enforces this allowlist itself — a caller forgetting CLI validation must
# not be able to smuggle an unvalidated token into the argv.
DATA_FLAGS_BOOLEAN = {"--dl-trades", "--erase", "--prepend"}
DATA_FLAGS_VALUE = {"--timeframe", "--timerange", "--days", "--new-pairs-days"}
DATA_FLAGS_MULTI = {"--pairs"}
DAYS_RE = re.compile(r"^\d+$")

STRATEGY_RE = re.compile(r"^[A-Za-z0-9_]+$")
CONTAINER_NAME = "finance-ft00-dryrun"

# Exchanges usable with PUBLIC data only (no key required for OHLCV).
ALLOWED_PUBLIC_SPOT_EXCHANGES = {"kraken", "binance"}

DEFAULT_READY_MARKERS = [
    "Dry run is enabled",
    "Using resolved strategy",
    "Bot heartbeat",
]


class ConfigUnsafeError(ValueError):
    """Raised (or returned as findings) when a config fails the guard."""


def validate_extra_args(extra_args: Optional[List[str]]) -> List[str]:
    """Findings for extra freqtrade tokens outside the safe allowlist.
    Empty list == safe. Freqtrade overlays later ``--config`` files onto
    earlier ones, so an unchecked extra ``--config`` could re-introduce
    credentials, futures settings or an enabled API server after the
    main config passed the guard."""
    findings: List[str] = []
    tokens = list(extra_args or [])
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token not in ALLOWED_EXTRA_FLAGS:
            findings.append(
                f"extra freqtrade argument {token!r} is not in the safe "
                f"allowlist {sorted(ALLOWED_EXTRA_FLAGS)} (overlay flags "
                "such as --config/-c/--userdir/--strategy are never "
                "permitted)"
            )
            i += 1
            continue
        if token in VALUE_EXTRA_FLAGS:
            if i + 1 >= len(tokens):
                findings.append(f"extra argument {token!r} requires a value")
            elif tokens[i + 1].startswith("-"):
                # a flag-looking token is never accepted as a value: it
                # would smuggle a disallowed flag past the allowlist
                findings.append(
                    f"extra argument {token!r} requires a non-flag value "
                    f"(got {tokens[i + 1]!r})"
                )
            else:
                i += 1  # consume the flag's value
        i += 1
    return findings


def validate_data_args(data_args: Optional[List[str]]) -> List[str]:
    """Findings for typed download tokens outside the safe grammar.
    Empty list == safe. Mirrors the CLI's typed validation so
    build_docker_argv enforces the same shapes itself."""
    findings: List[str] = []
    tokens = list(data_args or [])
    value_checkers: Dict[str, Any] = {
        "--timeframe": (TIMEFRAME_RE, "<n><s|m|h|d>"),
        "--timerange": (TIMERANGE_RE, "YYYYMMDD[-YYYYMMDD][-]"),
        "--days": (DAYS_RE, "a positive integer"),
        "--new-pairs-days": (DAYS_RE, "a positive integer"),
    }
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token in DATA_FLAGS_BOOLEAN:
            i += 1
            continue
        if token in value_checkers:
            pattern, shape = value_checkers[token]
            if i + 1 >= len(tokens):
                findings.append(f"data argument {token!r} requires a value")
            elif tokens[i + 1].startswith("-"):
                findings.append(
                    f"data argument {token!r} requires a non-flag value "
                    f"(got {tokens[i + 1]!r})"
                )
            elif not pattern.match(tokens[i + 1]):
                findings.append(
                    f"data argument {token!r} value {tokens[i + 1]!r} is "
                    f"not {shape}"
                )
            i += 2
            continue
        if token == "--pairs":
            pairs: List[str] = []
            j = i + 1
            while j < len(tokens) and not tokens[j].startswith("-"):
                pairs.append(tokens[j])
                j += 1
            if not pairs:
                findings.append("data argument '--pairs' requires >=1 pair")
            for pair in pairs:
                if not SPOT_PAIR_RE.match(pair):
                    findings.append(
                        f"--pairs entry {pair!r} is not a plain spot pair "
                        "(no ':' derivatives)"
                    )
            i = j
            continue
        findings.append(
            f"data argument {token!r} is not in the typed download grammar "
            f"(boolean {sorted(DATA_FLAGS_BOOLEAN)}, value "
            f"{sorted(DATA_FLAGS_VALUE)}, multi {sorted(DATA_FLAGS_MULTI)}); "
            "raw tokens belong to the --extra allowlist channel"
        )
        i += 1
    return findings


def verify_config(cfg: Dict[str, Any], image_ref: str) -> List[str]:
    """Return a list of safety findings. Empty list == safe to run."""
    findings: List[str] = []

    if image_ref != DEFAULT_PINNED_IMAGE:
        findings.append(
            f"engine image {image_ref!r} is not the pinned official "
            f"reference — only the exact digest-pinned official image "
            f"{DEFAULT_PINNED_IMAGE!r} may run"
        )

    if cfg.get("add_config_files"):
        findings.append(
            "add_config_files is present — overlay config files bypass "
            "the verified configuration and are not permitted"
        )

    if cfg.get("dry_run") is not True:
        findings.append("dry_run is not strictly true")

    mode = cfg.get("trading_mode")
    if mode is not None and mode != "spot":
        findings.append(f"trading_mode is {mode!r}, only spot is permitted")
    if cfg.get("margin_enabled"):
        findings.append("margin_enabled is true")
    if cfg.get("liquidation_buffer") is not None:
        findings.append("liquidation_buffer present (derivatives surface)")

    exchange = cfg.get("exchange") or {}
    name = (exchange.get("name") or "").lower()
    if name not in ALLOWED_PUBLIC_SPOT_EXCHANGES:
        findings.append(
            f"exchange.name {name!r} not in public-data spot allowlist "
            f"{sorted(ALLOWED_PUBLIC_SPOT_EXCHANGES)}"
        )
    for cred_field in ("key", "secret", "uid", "password"):
        if exchange.get(cred_field):
            findings.append(
                f"exchange.{cred_field} is set — no exchange credentials are "
                "permitted in simulation-only mode"
            )

    whitelist = exchange.get("pair_whitelist") or []
    if not whitelist:
        findings.append("pair_whitelist is empty")
    for pair in whitelist:
        if not isinstance(pair, str) or not SPOT_PAIR_RE.match(pair):
            findings.append(f"pair {pair!r} is not a plain spot pair (no ':' derivatives)")

    api_server = cfg.get("api_server")
    if api_server:
        if api_server.get("enabled"):
            findings.append("api_server.enabled is true")
        listen = (api_server.get("listen_ip_address") or "")
        if listen and listen not in ("127.0.0.1", "localhost"):
            findings.append(
                f"api_server.listen_ip_address {listen!r} is not loopback"
            )

    telegram = cfg.get("telegram")
    if telegram and telegram.get("enabled"):
        findings.append("telegram.enabled is true")

    strategy = cfg.get("strategy")
    if not isinstance(strategy, str) or not STRATEGY_RE.match(strategy):
        findings.append(f"strategy {strategy!r} is not a plain identifier")

    return findings


def load_config(path: Path) -> Dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def build_docker_argv(
    action: str,
    *,
    image_ref: str,
    user_data_dir: Path,
    config_name: str = "config-ft00.json",
    strategy: Optional[str] = None,
    extra_args: Optional[List[str]] = None,
    data_args: Optional[List[str]] = None,
    name: str = CONTAINER_NAME,
    detach: bool = False,
    uid_gid: Optional[str] = None,
) -> List[str]:
    """Construct the docker command for a supported action. The pinned
    image is embedded verbatim; the user_data workspace is the only
    volume; no network publication is ever added.

    ``data_args`` carries FIRST-CLASS typed download arguments (pairs /
    timeframe / timerange) and must pass :func:`validate_data_args` —
    the builder does not trust the caller to have validated them;
    ``extra_args`` is the raw user-supplied remainder and must pass
    :func:`validate_extra_args`.

    By default the container runs with the image's own lifecycle (root →
    entrypoint chown of user_data to its internal ftuser → drop to
    ftuser): freqtrade is pip-installed under ftuser's 0700 home, so an
    explicit ``--user`` cannot reach the binary. Pass ``uid_gid``
    explicitly only with an image that supports it."""
    if image_ref != DEFAULT_PINNED_IMAGE or not DIGEST_RE.match(image_ref):
        raise ValueError(
            "image_ref must be exactly the pinned official reference "
            f"{DEFAULT_PINNED_IMAGE!r}: got {image_ref!r}"
        )
    overlay = validate_extra_args(extra_args)
    if overlay:
        raise ValueError("; ".join(overlay))
    data_findings = validate_data_args(data_args)
    if data_findings:
        raise ValueError("; ".join(data_findings))
    volume = f"{user_data_dir.resolve()}:/freqtrade/user_data"
    # Foreground commands self-clean with --rm; a detached smoke run must
    # NOT use --rm, so a crash leaves the container's logs inspectable
    # until we remove it explicitly after capturing evidence.
    argv = ["docker", "run"]
    if not detach:
        argv.append("--rm")
    argv += ["--name", name, "--stop-timeout", "60", "-v", volume]
    if uid_gid:
        argv += ["--user", uid_gid]
    if detach:
        argv.append("-d")
    argv.append(image_ref)

    config_arg = f"/freqtrade/user_data/{config_name}"
    if action == "version":
        argv += ["--version"]
    elif action == "download-data":
        argv += [
            "download-data", "--config", config_arg,
            "--userdir", "/freqtrade/user_data",
        ] + list(data_args or []) + list(extra_args or [])
    elif action == "dry-run":
        argv += [
            "trade", "--config", config_arg,
            "--userdir", "/freqtrade/user_data",
            "--dry-run", "--strategy", strategy or "",
        ] + list(extra_args or [])
    else:
        raise ValueError(f"unknown action {action!r}")
    return argv


def run_command(argv: List[str], *, timeout_s: float, log_path: Optional[Path] = None,
                capture: bool = True) -> Dict[str, Any]:
    """Run a subprocess, streaming combined output to log_path."""
    try:
        proc = subprocess.run(
            argv, capture_output=capture, text=True, timeout=timeout_s,
        )
        output = (proc.stdout or "") + (proc.stderr or "")
        returncode = proc.returncode
    except subprocess.TimeoutExpired as exc:
        output = ((exc.stdout or "") + (exc.stderr or "")) if isinstance(
            exc.stdout, str) else ""
        returncode = 124
        output += f"\n[runner] timed out after {timeout_s}s"
    if log_path is not None:
        Path(log_path).parent.mkdir(parents=True, exist_ok=True)
        Path(log_path).write_text(output, encoding="utf-8")
    return {
        "argv": argv,
        "returncode": returncode,
        "output_tail": output[-4000:],
        "log": str(log_path) if log_path else None,
    }


def dry_run_smoke(
    *,
    image_ref: str,
    user_data_dir: Path,
    strategy: str,
    log_dir: Path,
    config_name: str = "config-ft00.json",
    cycles: int = 2,
    ready_timeout_s: float = 180.0,
    ready_markers: Optional[List[str]] = None,
    post_ready_s: float = 20.0,
    runner: Any = None,
) -> Dict[str, Any]:
    """Start/stop (and restart) the dry-run bot. Each cycle: start
    detached, poll logs for ALL ready markers, dwell, ``docker stop``
    (SIGTERM graceful, --stop-timeout 60), require exit 0."""
    markers = ready_markers or DEFAULT_READY_MARKERS
    log_dir.mkdir(parents=True, exist_ok=True)
    runner = runner or subprocess
    evidence: List[Dict[str, Any]] = []

    for cycle in range(1, cycles + 1):
        name = f"{CONTAINER_NAME}-c{cycle}"
        log_path = log_dir / f"dryrun-cycle{cycle}.log"
        argv = build_docker_argv(
            "dry-run", image_ref=image_ref, user_data_dir=user_data_dir,
            config_name=config_name, strategy=strategy, name=name,
            detach=True,
        )
        started = runner.run(argv, capture_output=True, text=True, timeout=120)
        if started.returncode != 0:
            return {
                "ok": False,
                "cycle": cycle,
                "stage": "start",
                "error": (started.stderr or started.stdout or "")[-2000:],
                "evidence": evidence,
            }
        deadline = time.monotonic() + ready_timeout_s
        ready_at: Optional[float] = None
        output = ""
        while time.monotonic() < deadline:
            logs = runner.run(
                ["docker", "logs", name], capture_output=True, text=True, timeout=30
            )
            if logs.returncode != 0 and "No such container" in (
                logs.stderr or ""
            ):
                log_path.write_text(output, encoding="utf-8")
                return {
                    "ok": False, "cycle": cycle, "stage": "crashed_early",
                    "error": "container exited before readiness; logs captured "
                             f"so far in {log_path}",
                    "run_stdout": (started.stdout or "")[-500:],
                    "evidence": evidence,
                }
            output = (logs.stdout or "") + (logs.stderr or "")
            if all(marker in output for marker in markers):
                ready_at = time.monotonic()
                break
            time.sleep(5)
        if ready_at is None:
            stop = runner.run(
                ["docker", "stop", "--time", "60", name],
                capture_output=True, text=True, timeout=120,
            )
            runner.run(["docker", "rm", "-f", name],
                       capture_output=True, text=True, timeout=60)
            log_path.write_text(output, encoding="utf-8")
            return {
                "ok": False,
                "cycle": cycle,
                "stage": "ready",
                "missing_markers": [
                    m for m in markers if m not in output
                ],
                "log": str(log_path),
                "evidence": evidence,
            }
        time.sleep(post_ready_s)
        final_logs = runner.run(
            ["docker", "logs", name], capture_output=True, text=True, timeout=30
        )
        output = (final_logs.stdout or "") + (final_logs.stderr or "")
        stop = runner.run(
            ["docker", "stop", "--time", "60", name],
            capture_output=True, text=True, timeout=120,
        )
        runner.run(["docker", "rm", "-f", name],
                   capture_output=True, text=True, timeout=60)
        log_path.write_text(output, encoding="utf-8")
        evidence.append(
            {
                "cycle": cycle,
                "ready_markers_seen": markers,
                "stop_returncode": stop.returncode,
                "log": str(log_path),
                "log_tail": output[-500:],
            }
        )
        if stop.returncode != 0:
            return {
                "ok": False, "cycle": cycle, "stage": "stop",
                "error": (stop.stderr or "")[-2000:],
                "evidence": evidence,
            }
    return {"ok": True, "cycles": cycles, "evidence": evidence}


def redact_config(cfg: Dict[str, Any]) -> Dict[str, Any]:
    safe = json.loads(json.dumps(cfg))  # deep copy
    ex = safe.get("exchange") or {}
    for field_name in ("key", "secret", "uid", "password"):
        if ex.get(field_name):
            ex[field_name] = "<redacted>"
    return safe


def build_snapshot_write_argv(user_data_dir: Path, name: str) -> List[str]:
    """docker argv writing the verified-config snapshot via the pinned
    image (bytes on stdin -> file). Needed because a running freqtrade
    container chowns the mounted user_data tree to its internal user,
    locking the invoking account out of direct writes."""
    return [
        "docker", "run", "--rm", "-i",
        "--entrypoint", "/bin/sh",
        "-v", f"{user_data_dir.resolve()}:/freqtrade/user_data",
        DEFAULT_PINNED_IMAGE,
        "-c", f"cat > /freqtrade/user_data/{name}",
    ]


def build_snapshot_rm_argv(user_data_dir: Path, name: str) -> List[str]:
    """docker argv removing a snapshot file via the pinned image
    (best-effort cleanup under the same uid-1000 constraint)."""
    return [
        "docker", "run", "--rm",
        "--entrypoint", "/bin/rm",
        "-v", f"{user_data_dir.resolve()}:/freqtrade/user_data",
        DEFAULT_PINNED_IMAGE,
        "-f", f"/freqtrade/user_data/{name}",
    ]


def _assert_snapshot_regular(target: Path) -> None:
    """The snapshot must be a REGULAR file, not a symlink: docker would
    otherwise follow the link at container start and execute whatever it
    points at — e.g. the still-mutable original config."""
    st = os.lstat(target)
    if stat.S_ISLNK(st.st_mode) or not stat.S_ISREG(st.st_mode):
        raise ConfigUnsafeError(
            f"verified-config snapshot {target.name} is not a regular "
            "file (symlink?) — refusing to execute it"
        )


def materialise_verified_config(
    cfg_path: Path, user_data: Path, cfg: Dict[str, Any],
    verified_raw: bytes,
) -> Path:
    """Snapshot the VERIFIED config bytes to a content-addressed file
    directly inside the workspace and return its path.

    Closes the verify→execute TOCTOU window: the guard verifies content
    loaded from ``cfg_path``, but docker later loads whatever bytes are
    at that path when the container starts. ``verified_raw`` MUST be the
    exact bytes of the single read the guard parsed — captured by the
    caller at verification time — and the file's CURRENT bytes must
    still equal them (byte comparison; parsed equality would let JSON
    ``true`` stand in for ``1``). The executed file is then
    ``.verified-<sha12>.json`` — a REGULAR file whose name encodes the
    sha256 of exactly those bytes, re-read from the host after writing
    and asserted byte-for-byte. A pre-existing symlink or unexpected
    file at the content-addressed path is rejected rather than followed
    or overwritten. Raises ConfigUnsafeError on any mismatch (fail
    closed).

    When the invoking user cannot write the workspace directly (the
    freqtrade container re-chowns it to its internal uid on every run),
    the write is delegated to a one-shot pinned-image container; the
    bytes are still re-read from the host and asserted afterwards."""
    raw = Path(cfg_path).read_bytes()
    if raw != verified_raw:
        raise ConfigUnsafeError(
            "the config file changed between guard verification and "
            "snapshot materialisation — refusing to execute it"
        )
    digest = hashlib.sha256(raw).hexdigest()[:12]
    target = Path(user_data) / f".verified-{digest}.json"
    if os.path.lexists(target):
        # a pre-existing entry at the content-addressed path must not be
        # followed (symlink → mutable original) or silently overwritten
        if target.is_symlink() or not target.is_file():
            raise ConfigUnsafeError(
                f"verified-config snapshot path {target.name} exists and "
                "is not a regular file (symlink?) — refusing to write"
            )
        if target.read_bytes() != raw:
            raise ConfigUnsafeError(
                f"verified-config snapshot path {target.name} exists with "
                "different bytes — refusing to overwrite"
            )
        # idempotent re-run: the verified bytes are already materialised
        _assert_snapshot_regular(target)
        return target
    try:
        target.write_bytes(raw)
    except PermissionError:
        proc = subprocess.run(
            build_snapshot_write_argv(Path(user_data), target.name),
            input=raw, capture_output=True, timeout=120,
        )
        if proc.returncode != 0:
            raise ConfigUnsafeError(
                "verified-config snapshot could not be written (direct "
                "write not permitted and pinned-image delegation failed): "
                + proc.stderr.decode("utf-8", errors="replace")[-300:]
            )
    try:
        _assert_snapshot_regular(target)
        reread = target.read_bytes()
        if reread != raw:
            # byte-exact: not parsed-object equality (which would accept
            # true↔1 swaps) and not a truncated-hash comparison
            raise ConfigUnsafeError(
                f"verified-config round-trip mismatch for {target}: "
                "snapshotted bytes differ from the verified bytes"
            )
        reparsed = json.loads(raw.decode("utf-8"))
        if reparsed != cfg:
            raise ConfigUnsafeError(
                "verified bytes do not parse as the config the guard "
                "verified — refusing to execute"
            )
    except Exception:
        remove_snapshot_best_effort(Path(user_data), target.name)
        raise
    return target


def remove_snapshot_best_effort(user_data: Path, name: str) -> None:
    """Remove a snapshot file, delegating to the pinned image when the
    invoking user lacks write permission on the workspace. Never raises."""
    try:
        (Path(user_data) / name).unlink(missing_ok=True)
    except OSError:
        try:
            subprocess.run(
                build_snapshot_rm_argv(Path(user_data), name),
                capture_output=True, timeout=120,
            )
        except Exception:
            pass


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog=RUNNER_NAME,
        description="FT-00 fail-closed Freqtrade dry-run guard/runner",
    )
    parser.add_argument("action", choices=[
        "verify-config", "version", "download-data", "dry-run-smoke",
        "show-config",
    ])
    parser.add_argument("--config", required=True)
    parser.add_argument("--image", default=DEFAULT_PINNED_IMAGE)
    parser.add_argument("--user-data-dir", default="/home/agent/finance-paper/user_data")
    parser.add_argument("--log-dir", default="/home/agent/finance-paper/logs")
    parser.add_argument("--pairs", nargs="+", default=[],
                        help="download-data: spot pairs, e.g. BTC/USD ETH/USD")
    parser.add_argument("--timeframe", default=None,
                        help="download-data: candle timeframe, e.g. 1h")
    parser.add_argument("--timerange", default=None,
                        help="download-data: e.g. 20260901-")
    parser.add_argument("--extra", action="append", default=[],
                        help="raw freqtrade argument token, repeatable "
                             "(e.g. --extra=--dl-trades)")
    parser.add_argument("--cycles", type=int, default=2)
    args = parser.parse_args(argv)

    cfg_path = Path(args.config)
    try:
        # ONE read: the parsed config and its exact bytes must come from
        # the same read, so the verified-bytes binding enforced later by
        # materialise_verified_config is sound (a second read would
        # reopen a swap window between parse and capture)
        verified_raw = cfg_path.read_bytes()
        cfg = json.loads(verified_raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "error": f"config unreadable: {exc}"}, indent=2))
        return 2

    if args.action == "show-config":
        print(json.dumps(redact_config(cfg), indent=2))
        return 0

    findings = verify_config(cfg, args.image)
    findings += validate_extra_args(args.extra)

    # The VERIFIED config and the EXECUTED config must be the same file:
    # docker loads the config from the mounted user_data workspace, so a
    # --config anywhere else would let a safe file pass the guard while
    # an unsafe one runs.
    user_data = Path(args.user_data_dir)
    try:
        config_in_workspace = (
            cfg_path.resolve().parent == user_data.resolve()
        )
    except OSError:
        config_in_workspace = False
    if not config_in_workspace:
        findings.append(
            "--config must point at a file directly inside "
            f"--user-data-dir (verified config and executed config must "
            f"be the same file): {cfg_path} vs {user_data}"
        )

    # First-class download arguments are typed and validated here; they
    # travel via data_args (never the raw --extra channel).
    data_args: List[str] = []
    for pair in args.pairs:
        if not SPOT_PAIR_RE.match(pair):
            findings.append(f"--pairs entry {pair!r} is not a plain spot pair")
    if args.pairs:
        data_args += ["--pairs"] + list(args.pairs)
    if args.timeframe:
        if not TIMEFRAME_RE.match(args.timeframe):
            findings.append(
                f"--timeframe {args.timeframe!r} is not <n><s|m|h|d>"
            )
        data_args += ["--timeframe", args.timeframe]
    if args.timerange:
        if not TIMERANGE_RE.match(args.timerange):
            findings.append(
                f"--timerange {args.timerange!r} is not YYYYMMDD[-YYYYMMDD][-]"
            )
        data_args += ["--timerange", args.timerange]

    if findings:
        print(json.dumps(
            {
                "ok": False,
                "action": args.action,
                "fail_closed": True,
                "findings": findings,
            }, indent=2))
        return 3

    strategy = cfg.get("strategy")
    config_name = cfg_path.name
    log_dir = Path(args.log_dir)

    if args.action == "verify-config":
        print(json.dumps(
            {
                "ok": True, "fail_closed": True, "findings": [],
                "image": args.image, "strategy": strategy,
                "dry_run": cfg.get("dry_run"),
                "trading_mode": cfg.get("trading_mode") or "spot(default)",
            }, indent=2))
        return 0

    if args.action == "version":
        result = run_command(
            build_docker_argv("version", image_ref=args.image,
                              user_data_dir=user_data,
                              config_name=config_name),
            timeout_s=120, log_path=log_dir / "version.log",
        )
        print(json.dumps(result, indent=2))
        return 0 if result["returncode"] == 0 else 4

    # Actions that EXECUTE the config close the verify→execute TOCTOU
    # window first: docker loads a content-addressed snapshot of the
    # verified bytes, not the mutable original path.
    try:
        verified_path = materialise_verified_config(
            cfg_path, user_data, cfg, verified_raw)
    except (OSError, ConfigUnsafeError) as exc:
        print(json.dumps(
            {
                "ok": False, "action": args.action, "fail_closed": True,
                "findings": [f"verified config could not be snapshotted: {exc}"],
            }, indent=2))
        return 3
    try:
        config_name = verified_path.name
        try:
            # re-assert immediately before handing the path to docker: the
            # snapshot must still be a regular file whose bytes hash to
            # the digest encoded in its content-addressed name
            _assert_snapshot_regular(verified_path)
            snap_digest = hashlib.sha256(
                verified_path.read_bytes()
            ).hexdigest()[:12]
            if snap_digest != config_name[len(".verified-"):-len(".json")]:
                raise ConfigUnsafeError(
                    "verified-config snapshot no longer matches its "
                    "content-addressed name — refusing to execute it"
                )
        except (OSError, ConfigUnsafeError) as exc:
            print(json.dumps(
                {
                    "ok": False, "action": args.action, "fail_closed": True,
                    "findings": [f"verified config snapshot invalid: {exc}"],
                }, indent=2))
            return 3

        if args.action == "download-data":
            result = run_command(
                build_docker_argv(
                    "download-data", image_ref=args.image,
                    user_data_dir=user_data, config_name=config_name,
                    data_args=data_args, extra_args=list(args.extra),
                ),
                timeout_s=1800, log_path=log_dir / "download-data.log",
            )
            print(json.dumps(result, indent=2))
            return 0 if result["returncode"] == 0 else 4

        if args.action == "dry-run-smoke":
            result = dry_run_smoke(
                image_ref=args.image, user_data_dir=user_data,
                strategy=strategy or "", log_dir=log_dir,
                config_name=config_name, cycles=args.cycles,
            )
            print(json.dumps(result, indent=2))
            return 0 if result.get("ok") else 5
    finally:
        # best-effort cleanup; the snapshot is evidence-addressed, so a
        # leftover never collides with a future run's snapshot
        remove_snapshot_best_effort(user_data, verified_path.name)

    return 1


if __name__ == "__main__":
    sys.exit(main())
