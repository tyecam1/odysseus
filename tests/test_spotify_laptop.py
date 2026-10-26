"""Tests for the laptop authorisation helper (scripts/spotify_laptop.py): loopback callback handling, config validation, DPAPI round trip (Windows only)."""

import http.client
import importlib.util
import json
import os
import socket
import sys
import threading
import time
import urllib.request

import pytest

SPEC = importlib.util.spec_from_file_location("spotify_laptop", os.path.join(os.path.dirname(__file__), "..", "scripts", "spotify_laptop.py"))
laptop = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(laptop)


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def serve(port, timeout=10):
    box, started = {}, threading.Event()

    def run():
        try:
            box["query"] = laptop.wait_for_callback(port, timeout=timeout, started=started)
        except Exception as exc:  # noqa: BLE001
            box["error"] = exc

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    assert started.wait(5)
    return box, thread


def get(port, path, host=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    conn.putrequest("GET", path, skip_host=True)
    conn.putheader("Host", host or "127.0.0.1:%d" % port)
    conn.endheaders()
    response = conn.getresponse()
    return response.status, response.read().decode()


def test_the_callback_query_is_captured_and_never_echoed_back():
    port = free_port()
    box, thread = serve(port)
    status, body = get(port, "/callback?code=SYNTH-CODE&state=SYNTH-STATE")
    thread.join(5)
    assert status == 200 and box["query"] == {"code": "SYNTH-CODE", "state": "SYNTH-STATE"}
    assert "SYNTH" not in body


def test_a_wrong_path_or_host_header_is_ignored_and_the_real_callback_still_works():
    port = free_port()
    box, thread = serve(port)
    assert get(port, "/other?code=x&state=y")[0] == 404
    assert get(port, "/callback?code=evil&state=y", host="attacker.example")[0] == 404          # DNS-rebinding style host
    assert "query" not in box
    assert get(port, "/callback?code=good&state=s")[0] == 200
    thread.join(5)
    assert box["query"]["code"] == "good"


def test_nothing_arriving_times_out_and_releases_the_port():
    port = free_port()
    began = time.monotonic()
    with pytest.raises(TimeoutError):
        laptop.wait_for_callback(port, timeout=1.2)
    assert time.monotonic() - began < 5
    with socket.socket() as s:
        s.bind(("127.0.0.1", port))                       # the port is free again


def test_the_listener_binds_loopback_only():
    port = free_port()
    box, thread = serve(port, timeout=3)
    lan = [a for a in socket.gethostbyname_ex(socket.gethostname())[2] if not a.startswith("127.")]
    for address in lan[:1]:
        with socket.socket() as s:
            s.settimeout(1)
            assert s.connect_ex((address, port)) != 0
    get(port, "/callback?code=c&state=s")
    thread.join(5)


def test_config_is_validated(tmp_path):
    path = str(tmp_path / "config.json")
    assert laptop.load_config(path) is None
    laptop.save_config("abc123DEF456ghi789", 18475, path)
    assert laptop.load_config(path) == {"client_id": "abc123DEF456ghi789", "port": 18475}
    for bad in ('{"client_id": "has space", "port": 18475}', '{"client_id": "ok", "port": "18475"}', '{"client_id": 5}', "[]", "not json",
                '{"client_id": "ok", "port": true}'):
        open(path, "w").write(bad)
        assert laptop.load_config(path) is None


def test_setup_rejects_a_secret_shaped_or_short_value_and_saves_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(laptop, "CONFIG_PATH", str(tmp_path / "config.json"))
    monkeypatch.setattr(laptop.webbrowser, "open", lambda url: True)
    monkeypatch.setattr(laptop.os, "system", lambda cmd: 0)
    lines = []

    class Args:
        port, client_id = 18475, "not a client id!"

    assert laptop.cmd_setup(Args, out=lines.append) == 2
    assert laptop.load_config(str(tmp_path / "config.json")) is None
    Args.client_id = "abc123DEF456ghi789"
    saved = []
    monkeypatch.setattr(laptop, "save_config", lambda client, port: saved.append((client, port)))
    assert laptop.cmd_setup(Args, out=lines.append) == 0
    assert saved == [("abc123DEF456ghi789", 18475)]
    assert any("http://127.0.0.1:18475/callback" in line for line in lines)


@pytest.mark.skipif(sys.platform != "win32", reason="DPAPI is Windows-only")
def test_dpapi_round_trip_hides_the_plaintext():
    blob = laptop.dpapi_protect(b"synthetic-secret-token")
    assert b"synthetic-secret-token" not in blob and laptop.dpapi_unprotect(blob) == b"synthetic-secret-token"
    with pytest.raises(OSError):
        laptop.dpapi_unprotect(blob[:-3] + b"xyz")
