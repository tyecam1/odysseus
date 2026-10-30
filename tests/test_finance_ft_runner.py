"""Offline tests for the FT-00 fail-closed runner (src/finance_ft_runner.py)."""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path

import pytest

from src import finance_ft_runner as ft


GOOD_IMAGE = ft.DEFAULT_PINNED_IMAGE
assert GOOD_IMAGE == (
    "freqtradeorg/freqtrade@sha256:"
    "9d67afb8eb5f4e1210f4fb067efcbd5e005bd4f1c27f6f3888b8b9fc7f9b5199"
)


def good_config():
    return {
        "dry_run": True,
        "trading_mode": "spot",
        "margin_enabled": False,
        "strategy": "SMACrossBaseline",
        "exchange": {
            "name": "kraken",
            "key": "",
            "secret": "",
            "pair_whitelist": ["BTC/USD", "ETH/USD"],
        },
        "telegram": {"enabled": False},
        "api_server": {"enabled": False},
    }


def test_good_config_passes():
    assert ft.verify_config(good_config(), GOOD_IMAGE) == []


def test_rejects_tag_instead_of_digest():
    findings = ft.verify_config(good_config(), "freqtradeorg/freqtrade:stable")
    assert any("pinned official" in f for f in findings)


def test_rejects_lookalike_repo_with_same_digest():
    # a digest alone proves nothing about WHICH repository it names
    evil = "evil/freqtrade@" + GOOD_IMAGE.split("@", 1)[1]
    findings = ft.verify_config(good_config(), evil)
    assert any("pinned official" in f for f in findings)


def test_rejects_add_config_files_overlay():
    cfg = good_config()
    cfg["add_config_files"] = ["/freqtrade/user_data/overlay.json"]
    findings = ft.verify_config(cfg, GOOD_IMAGE)
    assert any("add_config_files" in f for f in findings)


def test_rejects_dry_run_false():
    cfg = good_config()
    cfg["dry_run"] = False
    findings = ft.verify_config(cfg, GOOD_IMAGE)
    assert any("dry_run" in f for f in findings)


def test_rejects_any_exchange_credential():
    for field_name in ("key", "secret", "uid", "password"):
        cfg = good_config()
        cfg["exchange"][field_name] = "x" * 8
        findings = ft.verify_config(cfg, GOOD_IMAGE)
        assert any(field_name in f for f in findings), field_name


def test_rejects_margin_futures_and_derivatives():
    cfg = good_config()
    cfg["margin_enabled"] = True
    assert any("margin" in f for f in ft.verify_config(cfg, GOOD_IMAGE))

    cfg = good_config()
    cfg["trading_mode"] = "futures"
    assert any("trading_mode" in f for f in ft.verify_config(cfg, GOOD_IMAGE))

    cfg = good_config()
    cfg["exchange"]["pair_whitelist"] = ["BTC/USD:USD"]
    assert any("spot pair" in f for f in ft.verify_config(cfg, GOOD_IMAGE))


def test_rejects_public_api_listener_and_telegram():
    cfg = good_config()
    cfg["api_server"] = {"enabled": True, "listen_ip_address": "127.0.0.1"}
    assert any("api_server" in f for f in ft.verify_config(cfg, GOOD_IMAGE))

    cfg = good_config()
    cfg["api_server"] = {"enabled": False, "listen_ip_address": "0.0.0.0"}
    assert any("loopback" in f for f in ft.verify_config(cfg, GOOD_IMAGE))

    cfg = good_config()
    cfg["telegram"] = {"enabled": True}
    assert any("telegram" in f for f in ft.verify_config(cfg, GOOD_IMAGE))


def test_rejects_unknown_exchange_and_empty_whitelist():
    cfg = good_config()
    cfg["exchange"]["name"] = "okx"
    assert any("allowlist" in f for f in ft.verify_config(cfg, GOOD_IMAGE))

    cfg = good_config()
    cfg["exchange"]["pair_whitelist"] = []
    assert any("pair_whitelist" in f for f in ft.verify_config(cfg, GOOD_IMAGE))


def test_docker_argv_uses_pinned_digest_and_workspace_only():
    user_data = Path("/home/agent/finance-paper/user_data")
    argv = ft.build_docker_argv(
        "dry-run", image_ref=GOOD_IMAGE, user_data_dir=user_data,
        strategy="SMACrossBaseline",
    )
    assert argv[0] == "docker"
    assert GOOD_IMAGE in argv
    assert f"{user_data}:/freqtrade/user_data" in argv
    assert "--dry-run" in argv
    assert "SMACrossBaseline" in argv
    # no port publication, no extra volumes, no privileged flags
    assert not [a for a in argv if a.startswith("-p")]
    volumes = [a for a in argv if a.startswith("/")]
    assert len([a for a in argv if ":" in a and a != GOOD_IMAGE]) >= 1
    joined = " ".join(argv)
    assert "--privileged" not in joined
    assert "-p " not in joined


def test_download_data_argv():
    # first-class typed args travel via data_args (not the raw channel)
    argv = ft.build_docker_argv(
        "download-data", image_ref=GOOD_IMAGE,
        user_data_dir=Path("/home/agent/finance-paper/user_data"),
        data_args=["--pairs", "BTC/USD", "ETH/USD", "--timeframe", "1h"],
        extra_args=["--timerange", "20260901-", "--dl-trades"],
    )
    assert "download-data" in argv
    assert "--timerange" in argv and "20260901-" in argv
    assert "--dl-trades" in argv and "--timeframe" in argv
    assert argv.index("--pairs") < argv.index("BTC/USD")
    assert GOOD_IMAGE in argv


def test_unknown_action_rejected():
    with pytest.raises(ValueError):
        ft.build_docker_argv(
            "moon", image_ref=GOOD_IMAGE,
            user_data_dir=Path("/home/agent/finance-paper/user_data"),
        )


def test_extra_args_restricted_to_safe_allowlist():
    # data-download flags only; overlays are refused
    assert ft.validate_extra_args([]) == []
    assert ft.validate_extra_args(["--dl-trades"]) == []
    assert ft.validate_extra_args(["--timerange", "20260901-"]) == []
    for overlay in (
        ["--config", "/freqtrade/user_data/unsafe.json"],
        ["-c", "/etc/ft.json"],
        ["--userdir", "/etc"],
        ["--strategy", "Evil"],
        ["--db-url", "sqlite:////tmp/x.sqlite"],
        ["--timeframe", "1h"],  # timeframe is first-class, not a raw extra
    ):
        findings = ft.validate_extra_args(overlay)
        assert findings and overlay[0] in findings[0], overlay
    assert ft.validate_extra_args(["--timerange"])[0].endswith(
        "requires a value"
    )
    # a flag-looking token is never consumed as a value
    findings = ft.validate_extra_args(["--timerange", "--config=/tmp/evil"])
    assert findings and "non-flag value" in findings[0]


def test_build_docker_argv_refuses_overlays_and_foreign_images():
    with pytest.raises(ValueError, match="allowlist"):
        ft.build_docker_argv(
            "download-data", image_ref=GOOD_IMAGE,
            user_data_dir=Path("/home/agent/finance-paper/user_data"),
            extra_args=["--config", "/freqtrade/user_data/unsafe.json"],
        )
    for bad_image in (
        "freqtradeorg/freqtrade:stable",  # bare tag
        "evil/freqtrade@sha256:" + "0" * 64,  # foreign repo, valid digest
    ):
        with pytest.raises(ValueError, match="pinned official"):
            ft.build_docker_argv(
                "dry-run", image_ref=bad_image,
                user_data_dir=Path("/home/agent/finance-paper/user_data"),
                strategy="S",
            )


def test_cli_fails_closed_on_config_overlay_extra(tmp_path: Path, capsys):
    cfg_path = tmp_path / "config-ft00.json"
    cfg_path.write_text(json.dumps(good_config()), encoding="utf-8")
    rc = ft.main(
        ["verify-config", "--config", str(cfg_path),
         "--user-data-dir", str(tmp_path),
         "--extra=--config", "--extra=/freqtrade/user_data/unsafe.json"]
    )
    assert rc == 3
    payload = json.loads(capsys.readouterr().out)
    assert payload["fail_closed"] is True
    assert any("--config" in f for f in payload["findings"])


def test_redact_config_hides_credentials():
    cfg = good_config()
    cfg["exchange"]["key"] = "SECRETKEY"
    red = ft.redact_config(cfg)
    assert red["exchange"]["key"] == "<redacted>"
    assert cfg["exchange"]["key"] == "SECRETKEY"  # original untouched


def test_verify_config_cli_exit_code(tmp_path: Path, capsys):
    cfg_path = tmp_path / "config-ft00.json"
    cfg_path.write_text(json.dumps(good_config()), encoding="utf-8")
    rc = ft.main(["verify-config", "--config", str(cfg_path),
                  "--user-data-dir", str(tmp_path)])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True and payload["fail_closed"] is True

    bad = good_config()
    bad["dry_run"] = False
    bad["exchange"]["key"] = "leak"
    bad_path = tmp_path / "config-bad.json"
    bad_path.write_text(json.dumps(bad), encoding="utf-8")
    rc = ft.main(["verify-config", "--config", str(bad_path),
                  "--user-data-dir", str(tmp_path)])
    assert rc == 3
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert len(payload["findings"]) >= 2


def test_cli_fails_closed_when_config_lives_outside_workspace(
    tmp_path: Path, capsys,
):
    # verified config and executed config must be the SAME file: a safe
    # --config elsewhere must not vouch for the workspace's own config
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    cfg_path = elsewhere / "config-ft00.json"
    cfg_path.write_text(json.dumps(good_config()), encoding="utf-8")
    rc = ft.main(["verify-config", "--config", str(cfg_path),
                  "--user-data-dir", str(tmp_path / "user_data")])
    assert rc == 3
    payload = json.loads(capsys.readouterr().out)
    assert any("inside --user-data-dir" in f for f in payload["findings"])


def test_cli_validates_typed_download_args(tmp_path: Path, capsys):
    cfg_path = tmp_path / "config-ft00.json"
    cfg_path.write_text(json.dumps(good_config()), encoding="utf-8")
    base = ["download-data", "--config", str(cfg_path),
            "--user-data-dir", str(tmp_path)]
    # derivatives pair refused before docker is ever invoked
    rc = ft.main(base + ["--pairs", "BTC/USD:USD"])
    assert rc == 3
    findings = json.loads(capsys.readouterr().out)["findings"]
    assert any("spot pair" in f for f in findings)
    rc = ft.main(base + ["--timeframe", "1x"])
    assert rc == 3
    findings = json.loads(capsys.readouterr().out)["findings"]
    assert any("--timeframe" in f for f in findings)
    rc = ft.main(base + ["--timerange", "garbage"])
    assert rc == 3
    findings = json.loads(capsys.readouterr().out)["findings"]
    assert any("--timerange" in f for f in findings)


def test_validate_data_args_shapes():
    assert ft.validate_data_args([]) == []
    assert ft.validate_data_args(
        ["--pairs", "BTC/USD", "ETH/USD", "--timeframe", "1h",
         "--timerange", "20260901-", "--days", "5", "--dl-trades"]
    ) == []
    # unknown token (overlay shapes belong to the --extra channel)
    findings = ft.validate_data_args(
        ["--config", "/freqtrade/user_data/evil.json"])
    assert findings and "typed download grammar" in findings[0]
    # flag-looking value refused
    findings = ft.validate_data_args(["--timerange", "--config=/tmp/evil"])
    assert findings and "non-flag value" in findings[0]
    # --pairs with no values refused
    assert ft.validate_data_args(["--pairs"])[0].endswith("requires >=1 pair")
    # bad value shapes refused
    findings = ft.validate_data_args(["--days", "five"])
    assert findings and "not a positive integer" in findings[0]
    findings = ft.validate_data_args(["--timeframe", "1x"])
    assert findings and "not <n><s|m|h|d>" in findings[0]
    findings = ft.validate_data_args(["--pairs", "BTC/USD:USD"])
    assert findings and "plain spot pair" in findings[0]


def test_builder_validates_data_args_not_trusts_caller():
    user_data = Path("/home/agent/finance-paper/user_data")
    # a caller skipping CLI validation must not smuggle an unvalidated
    # token into the docker argv via data_args
    with pytest.raises(ValueError, match="typed download grammar"):
        ft.build_docker_argv(
            "download-data", image_ref=GOOD_IMAGE, user_data_dir=user_data,
            data_args=["--config", "/freqtrade/user_data/evil.json"],
        )
    with pytest.raises(ValueError, match="non-flag value"):
        ft.build_docker_argv(
            "download-data", image_ref=GOOD_IMAGE, user_data_dir=user_data,
            data_args=["--timerange", "--config=/tmp/evil"],
        )
    with pytest.raises(ValueError, match="plain spot pair"):
        ft.build_docker_argv(
            "download-data", image_ref=GOOD_IMAGE, user_data_dir=user_data,
            data_args=["--pairs", "BTC/USD:USD"],
        )


def test_materialise_verified_config_closes_verify_execute_gap(tmp_path: Path):
    # the executed config is a content-addressed snapshot of the VERIFIED
    # bytes: swapping the original file after verification cannot change
    # what runs
    cfg = good_config()
    cfg_path = tmp_path / "config-ft00.json"
    cfg_path.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
    verified_raw = cfg_path.read_bytes()
    snap = ft.materialise_verified_config(cfg_path, tmp_path, cfg,
                                          verified_raw)
    assert snap.parent == tmp_path  # directly inside the workspace
    digest = hashlib.sha256(verified_raw).hexdigest()[:12]
    assert snap.name == f".verified-{digest}.json"
    assert snap.read_bytes() == verified_raw
    # post-verification tamper of the ORIGINAL: the snapshot still
    # carries the verified bytes and the argv still names the snapshot
    cfg_path.write_text(json.dumps({**cfg, "dry_run": False}),
                        encoding="utf-8")
    assert json.loads(snap.read_text(encoding="utf-8"))["dry_run"] is True
    argv = ft.build_docker_argv(
        "dry-run", image_ref=GOOD_IMAGE, user_data_dir=tmp_path,
        strategy="SMACrossBaseline", config_name=snap.name,
    )
    assert f"/freqtrade/user_data/{snap.name}" in argv
    # re-materialising while the guard's verified bytes still bind is
    # idempotent (same content address); a CHANGED file under the same
    # claim is refused instead of silently executing new bytes
    with pytest.raises(ft.ConfigUnsafeError):
        ft.materialise_verified_config(cfg_path, tmp_path, cfg,
                                       verified_raw)
    # a fresh verification of the new bytes snapshots to a new address
    new_raw = cfg_path.read_bytes()
    again = ft.materialise_verified_config(
        cfg_path, tmp_path, json.loads(new_raw.decode("utf-8")), new_raw)
    assert again.name != snap.name  # different verified content -> new address
    assert json.loads(again.read_text())["dry_run"] is False


def test_snapshot_delegation_argv_uses_pinned_image_and_workspace_only():
    # a running freqtrade container chowns the mounted workspace to its
    # internal uid, so snapshot write/cleanup may have to go through
    # one-shot pinned-image containers — these argv builders are the
    # ONLY new docker surface, and they must stay pinned + workspace-only
    write_argv = ft.build_snapshot_write_argv(
        Path("/home/agent/finance-paper/user_data"), ".verified-abc.json")
    assert write_argv[0] == "docker"
    assert "--rm" in write_argv and "-i" in write_argv
    assert GOOD_IMAGE in write_argv
    assert write_argv[write_argv.index("--entrypoint") + 1] == "/bin/sh"
    assert "/home/agent/finance-paper/user_data:/freqtrade/user_data" in write_argv
    assert write_argv[-1] == (
        "set -C; cat > /freqtrade/user_data/.verified-abc.json"
    )  # noclobber: a replanted path is refused, never truncated
    assert "--privileged" not in write_argv

    rm_argv = ft.build_snapshot_rm_argv(
        Path("/home/agent/finance-paper/user_data"), ".verified-abc.json")
    assert rm_argv[0] == "docker" and GOOD_IMAGE in rm_argv
    assert rm_argv[rm_argv.index("--entrypoint") + 1] == "/bin/rm"
    assert rm_argv[-2:] == ["-f", "/freqtrade/user_data/.verified-abc.json"]
    # removal can never target anything outside the mounted workspace
    assert all(a.startswith("-") or a in (
        "docker", "run", GOOD_IMAGE, "/bin/rm",
        "/freqtrade/user_data/.verified-abc.json") or ":" in a
        for a in rm_argv)


# --- round-5 review findings: snapshot must be a regular file of the
# --- EXACT verified bytes (symlinks and parsed-equality tricks fail closed)


def _write_config(path, cfg):
    path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    return path


def test_planted_symlink_at_snapshot_path_is_cleared_not_followed(tmp_path):
    # a symlink planted at the content-addressed name would make the
    # executed config follow the still-mutable original: it is REMOVED
    # and replaced by a fresh regular file of the verified bytes — the
    # planted link itself is never executed
    cfg = good_config()
    src = _write_config(tmp_path / "config-ft00.json", cfg)
    workspace = tmp_path / "user_data"
    workspace.mkdir()
    digest = hashlib.sha256(src.read_bytes()).hexdigest()[:12]
    link = workspace / f".verified-{digest}.json"
    try:
        link.symlink_to(src)
    except OSError as exc:  # pragma: no cover - platform without symlinks
        pytest.skip(f"cannot create symlinks here: {exc}")
    target = ft.materialise_verified_config(src, workspace, cfg,
                                            src.read_bytes())
    assert not target.is_symlink()
    assert target.is_file()
    assert target.read_bytes() == src.read_bytes()


def test_planted_hardlink_at_snapshot_path_is_neutralised(tmp_path):
    # a HARDLINK to the original passes lstat + byte checks while
    # sharing the original's inode (an in-place edit of the original
    # would change the "snapshot"); materialise must create a FRESH
    # inode with nlink == 1 instead of accepting it
    cfg = good_config()
    src = _write_config(tmp_path / "config-ft00.json", cfg)
    workspace = tmp_path / "user_data"
    workspace.mkdir()
    digest = hashlib.sha256(src.read_bytes()).hexdigest()[:12]
    planted = workspace / f".verified-{digest}.json"
    try:
        os.link(src, planted)
    except OSError as exc:  # pragma: no cover - platform without hardlinks
        pytest.skip(f"cannot create hardlinks here: {exc}")
    target = ft.materialise_verified_config(src, workspace, cfg,
                                            src.read_bytes())
    assert target == planted
    assert os.lstat(target).st_nlink == 1
    assert (os.lstat(target).st_dev, os.lstat(target).st_ino) != (
        os.lstat(src).st_dev, os.lstat(src).st_ino)
    assert os.lstat(src).st_nlink == 1  # original no longer aliased either
    assert target.read_bytes() == src.read_bytes()


def test_unclearable_preexisting_snapshot_refuses(tmp_path, monkeypatch):
    # if the pre-existing entry cannot be removed (permissions, mount
    # oddity), materialise fails closed instead of reusing it
    cfg = good_config()
    src = _write_config(tmp_path / "config-ft00.json", cfg)
    workspace = tmp_path / "user_data"
    workspace.mkdir()
    digest = hashlib.sha256(src.read_bytes()).hexdigest()[:12]
    planted = workspace / f".verified-{digest}.json"
    planted.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        ft, "remove_snapshot_best_effort", lambda *a, **k: None)
    with pytest.raises(ft.ConfigUnsafeError):
        ft.materialise_verified_config(src, workspace, cfg,
                                      src.read_bytes())


def test_materialise_round_trip_is_byte_exact(tmp_path):
    cfg = good_config()
    src = _write_config(tmp_path / "config-ft00.json", cfg)
    workspace = tmp_path / "user_data"
    workspace.mkdir()
    target = ft.materialise_verified_config(src, workspace, cfg,
                                            src.read_bytes())
    # BYTE equality with the verified source, not parsed equality
    assert target.read_bytes() == src.read_bytes()
    assert not target.is_symlink()
    # idempotent: re-materialising the same bytes is fine
    again = ft.materialise_verified_config(src, workspace, cfg,
                                           src.read_bytes())
    assert again == target


def test_materialise_catches_true_vs_one_source_swap(tmp_path):
    # parsed-object equality thinks JSON true == 1; byte equality does
    # not. A source file swapped between verification and materialisation
    # to bytes that parse "equal" must still be refused.
    workspace = tmp_path / "user_data"
    workspace.mkdir()
    cfg = {"dry_run": True, "trading_mode": "spot"}
    src = tmp_path / "config-ft00.json"
    src.write_text('{"dry_run": true, "trading_mode": "spot"}',
                   encoding="utf-8")
    # the guard parsed `cfg` from the true-form bytes; the file on disk
    # is then swapped to the 1-form (json.loads-equal, byte-different)
    src.write_text('{"dry_run": 1, "trading_mode": "spot"}',
                   encoding="utf-8")
    with pytest.raises(ft.ConfigUnsafeError):
        ft.materialise_verified_config(
            src, workspace, cfg,
            b'{"dry_run": true, "trading_mode": "spot"}')


# --- round-6: container-side config binding + argv grammar guards ---


def test_docker_argv_binds_config_sha_inside_container():
    # with a full sha256 the container entrypoint COPIES the mounted
    # snapshot to container-private storage, verifies the COPY's sha256
    # (check and use are then the same host-unreachable inode), and only
    # then execs freqtrade, which reads the copy; freqtrade's own
    # arguments travel as positional parameters, never the shell string
    sha = "a" * 64
    argv = ft.build_docker_argv(
        "dry-run", image_ref=GOOD_IMAGE,
        user_data_dir=Path("/home/agent/finance-paper/user_data"),
        strategy="SMACrossBaseline",
        config_name=".verified-f330b591b66a.json",
        config_sha256=sha, detach=True,
    )
    assert argv[argv.index("--entrypoint") + 1] == "/bin/sh"
    script = argv[argv.index("-c") + 1]
    # argv0 is a placeholder; the EXECUTED command is "$@" = freqtrade
    # <subcommand> ... (exec "$@" never runs argv0 itself)
    assert argv[argv.index("-c") + 2] == "sh"
    assert argv[argv.index("-c") + 3] == "freqtrade"
    assert script.startswith("cp /freqtrade/user_data/")
    assert ("cp /freqtrade/user_data/.verified-f330b591b66a.json "
            + ft.PRIVATE_CONFIG_PATH + " && ") in script
    assert ("printf '%s  %s" + "\\n' " + sha + " " +
            ft.PRIVATE_CONFIG_PATH) in script
    assert "/freqtrade/user_data/.verified-f330b591b66a.json" not in (
        script.split(" && ", 1)[1]
    )  # after the cp, only the private copy is referenced
    assert "sha256sum -c --status -" in script
    assert 'exec "$@"' in script
    assert "SMACrossBaseline" not in script
    assert "trade" not in script.replace("freqtrade", "")
    assert argv[argv.index("-c") + 4] == "trade"
    assert "SMACrossBaseline" in argv


def test_sha_bound_freqtrade_reads_the_private_copy_not_the_mount():
    # the --config VALUE must be the container-private path: a path
    # inside the mounted volume stays replaceable by any workspace
    # writer, which is exactly the check-to-use race round 6 found
    for action, extra in (
        ("dry-run", {"strategy": "SMACrossBaseline"}),
        ("download-data", {"data_args": ["--timeframe", "1h"]}),
    ):
        argv = ft.build_docker_argv(
            action, image_ref=GOOD_IMAGE,
            user_data_dir=Path("/w"), config_sha256="b" * 64, **extra,
        )
        cmd = argv[argv.index("-c") + 3:]
        assert cmd[0] == "freqtrade"
        cfg_value = cmd[cmd.index("--config") + 1]
        assert cfg_value == ft.PRIVATE_CONFIG_PATH
        assert not cfg_value.startswith("/freqtrade/user_data")
        assert not ft.PRIVATE_CONFIG_PATH.startswith("/freqtrade/user_data/")


def test_snapshot_write_argv_refuses_to_clobber_noclobber():
    # the delegated snapshot write must open with O_EXCL semantics
    # (set -C): a symlink replanted between the clear and the
    # container's open is REFUSED, never followed and truncated
    argv = ft.build_snapshot_write_argv(Path("/w"), ".verified-abc.json")
    script = argv[argv.index("-c") + 1]
    assert script.startswith("set -C; cat > ")
    assert script.endswith("/freqtrade/user_data/.verified-abc.json")


def test_docker_argv_sha_binding_rejects_bad_inputs():
    with pytest.raises(ValueError):
        ft.build_docker_argv(
            "version", image_ref=GOOD_IMAGE,
            user_data_dir=Path("/w"), config_sha256="a" * 64,
        )  # version does not execute the config
    with pytest.raises(ValueError):
        ft.build_docker_argv(
            "download-data", image_ref=GOOD_IMAGE,
            user_data_dir=Path("/w"), config_sha256="short",
        )  # not a full digest


def test_strategy_and_config_name_grammar_guarded():
    # config-controlled text reaches docker argv (and the hash-bound
    # shell prelude); only plain identifiers / safe names pass
    with pytest.raises(ValueError):
        ft.build_docker_argv(
            "dry-run", image_ref=GOOD_IMAGE, user_data_dir=Path("/w"),
            strategy="x; touch /tmp/pwn",
        )
    with pytest.raises(ValueError):
        ft.build_docker_argv(
            "dry-run", image_ref=GOOD_IMAGE, user_data_dir=Path("/w"),
            config_name="a b.json",
        )
