"""Offline tests for the FT-00 fail-closed runner (src/finance_ft_runner.py)."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from src import finance_ft_runner as ft


GOOD_IMAGE = (
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
    assert any("digest" in f for f in findings)


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
    argv = ft.build_docker_argv(
        "download-data", image_ref=GOOD_IMAGE,
        user_data_dir=Path("/home/agent/finance-paper/user_data"),
        extra_args=["--timeframe", "1h", "--timerange", "20260901-"],
    )
    assert "download-data" in argv
    assert "--timerange" in argv and "20260901-" in argv
    assert GOOD_IMAGE in argv


def test_unknown_action_rejected():
    with pytest.raises(ValueError):
        ft.build_docker_argv(
            "moon", image_ref=GOOD_IMAGE,
            user_data_dir=Path("/home/agent/finance-paper/user_data"),
        )


def test_redact_config_hides_credentials():
    cfg = good_config()
    cfg["exchange"]["key"] = "SECRETKEY"
    red = ft.redact_config(cfg)
    assert red["exchange"]["key"] == "<redacted>"
    assert cfg["exchange"]["key"] == "SECRETKEY"  # original untouched


def test_verify_config_cli_exit_code(tmp_path: Path, capsys):
    cfg_path = tmp_path / "config-ft00.json"
    cfg_path.write_text(json.dumps(good_config()), encoding="utf-8")
    rc = ft.main(["verify-config", "--config", str(cfg_path)])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True and payload["fail_closed"] is True

    bad = good_config()
    bad["dry_run"] = False
    bad["exchange"]["key"] = "leak"
    bad_path = tmp_path / "config-bad.json"
    bad_path.write_text(json.dumps(bad), encoding="utf-8")
    rc = ft.main(["verify-config", "--config", str(bad_path)])
    assert rc == 3
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert len(payload["findings"]) >= 2
