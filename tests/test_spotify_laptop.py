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


def test_the_listener_binds_loopback_only(monkeypatch):
    """Record the address the server really binds (not a LAN probe that passes vacuously when there is no LAN address)."""
    bound = []

    class Recording(laptop.http.server.HTTPServer):
        def __init__(self, address, handler):
            bound.append(address)
            super().__init__(address, handler)

    monkeypatch.setattr(laptop.http.server, "HTTPServer", Recording)
    port = free_port()
    box, thread = serve(port, timeout=3)
    get(port, "/callback?code=c&state=s")
    thread.join(5)
    assert bound == [("127.0.0.1", port)]


def test_a_forged_callback_does_not_end_the_authorisation():
    """Sol: any request with the right Host used to be accepted and close the listener before state validation."""
    port = free_port()
    box, started = {}, threading.Event()

    def run():
        try:
            box["query"] = laptop.wait_for_callback(port, timeout=10, started=started, expected_state="REAL-STATE")
        except Exception as exc:  # noqa: BLE001
            box["error"] = exc

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    assert started.wait(5)
    assert get(port, "/callback?code=forged&state=wrong")[0] == 400
    assert get(port, "/callback?code=forged")[0] == 400
    assert "query" not in box and thread.is_alive()
    assert get(port, "/callback?code=real&state=REAL-STATE")[0] == 200
    thread.join(5)
    assert box["query"] == {"code": "real", "state": "REAL-STATE"}


def test_a_half_sent_request_cannot_hold_the_listener_past_its_deadline():
    port = free_port()
    box, thread = serve(port, timeout=1.5)
    stalled = socket.create_connection(("127.0.0.1", port), timeout=5)
    stalled.sendall(b"GET /callback HTTP/1.1\r\n")                 # never finishes the headers
    began = time.monotonic()
    thread.join(15)
    stalled.close()
    assert not thread.is_alive() and isinstance(box.get("error"), TimeoutError)
    assert time.monotonic() - began < 12


def test_consent_is_not_opened_when_the_port_cannot_be_bound(monkeypatch, tmp_path):
    """Sol: with the port squatted the helper still opened consent, so a squatter could receive the code and state."""
    squatter = socket.socket()
    squatter.bind(("127.0.0.1", 0))
    squatter.listen(1)
    port = squatter.getsockname()[1]
    try:
        monkeypatch.setattr(laptop, "load_config", lambda: {"client_id": "abc123DEF456ghi789", "port": port})
        opened, lines = [], []
        monkeypatch.setattr(laptop.webbrowser, "open", lambda url: opened.append(url) or True)

        class Args:
            pass

        assert laptop.cmd_authorise(Args, out=lines.append) == 1
        assert opened == [] and any("NOT opened" in line for line in lines)
    finally:
        squatter.close()


def test_authorise_reports_pending_acceptance_not_connected(monkeypatch, tmp_path):
    port = free_port()
    monkeypatch.setattr(laptop, "load_config", lambda: {"client_id": "abc123DEF456ghi789", "port": port})
    monkeypatch.setattr(laptop, "TOKEN_PATH", str(tmp_path / "token.bin"))
    monkeypatch.setattr(laptop, "dpapi_protect", lambda b: b"P" + b)
    monkeypatch.setattr(laptop, "dpapi_unprotect", lambda b: b[1:])
    seen = {}

    def fake_open(url):
        query = dict(laptop.urllib.parse.parse_qsl(laptop.urllib.parse.urlsplit(url).query))
        seen["state"] = query["state"]
        threading.Thread(target=lambda: get(port, "/callback?code=synth&state=" + query["state"]), daemon=True).start()
        return True

    monkeypatch.setattr(laptop.webbrowser, "open", fake_open)
    scripted = [
        (200, {}, json.dumps({"access_token": "SYNTH-A", "refresh_token": "SYNTH-R", "expires_in": 3600,
                              "scope": " ".join(laptop.sb.SCOPES)}).encode()),
        (200, {}, json.dumps({"id": "synthuser", "product": "premium"}).encode()),
    ]
    monkeypatch.setattr(laptop.sb, "urllib_http", lambda *a, **k: scripted.pop(0))
    lines = []

    class Args:
        pass

    assert laptop.cmd_authorise(Args, out=lines.append) == 0
    text = "\n".join(lines)
    assert "Authorised and verified" in text and "NOT yet counted as connected" in text and "Connected:" not in text
    assert "SYNTH-A" not in text and "SYNTH-R" not in text
    assert os.path.exists(str(tmp_path / "token.bin"))


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


def test_a_client_that_trickles_bytes_is_cut_at_the_absolute_connection_deadline(monkeypatch):
    """Sol: the 5 s timeout measures inactivity, so a client sending a byte every few seconds could hold the single listener indefinitely."""
    monkeypatch.setattr(laptop, "CONNECTION_DEADLINE_S", 1.0)
    port = free_port()
    box, thread = serve(port, timeout=8)
    trickler = socket.create_connection(("127.0.0.1", port), timeout=5)
    trickler.sendall(b"GET /callback?code=x&state=y HTTP/1.1\r\n")
    began = time.monotonic()
    dropped = False
    try:
        for _ in range(40):
            time.sleep(0.25)
            trickler.sendall(b"X-A: 1\r\n")
    except OSError:
        dropped = True
    assert dropped and time.monotonic() - began < 5
    trickler.close()
    assert get(port, "/callback?code=real&state=s")[0] == 200            # the listener is free again for the real callback
    thread.join(5)
    assert box["query"]["code"] == "real"


def test_revoke_goes_through_the_manager_so_a_refresh_in_flight_cannot_undo_it(monkeypatch, tmp_path):
    calls = []

    class FakeManager:
        def __init__(self, client_id, store, http):
            calls.append("manager")

        def revoke(self):
            calls.append("revoke")

    monkeypatch.setattr(laptop.sb, "TokenManager", FakeManager)
    monkeypatch.setattr(laptop, "make_store", lambda: object())
    lines = []
    assert laptop.cmd_revoke(None, out=lines.append) == 0
    assert calls == ["manager", "revoke"]
