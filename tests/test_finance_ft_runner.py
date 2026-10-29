"""Offline tests for the FT-00 fail-closed runner (src/finance_ft_runner.py)."""
from __future__ import annotations

import copy
import json
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
