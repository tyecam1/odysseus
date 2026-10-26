"""Spotify binding tests: PKCE, state/scope/redirect checks, token custody and refresh, provider request shapes and failure mapping.

Everything runs against a fake transport: no network, no credentials. Tokens used here are obviously synthetic."""

import json
import os
import time
import urllib.parse

import pytest

from src.music_capability import MusicController, ProviderError
from src import spotify_binding as sb

CLIENT = "synthetic0client0id"
REDIRECT = "http://127.0.0.1:18475/callback"
ACCESS, REFRESH = "SYNTH-ACCESS-TOKEN-1", "SYNTH-REFRESH-TOKEN-1"


class FakeHttp:
    """Scripted transport: queue (status, headers, body-or-dict) answers; records every request."""

    def __init__(self):
        self.script, self.calls = [], []

    def push(self, status, body=None, headers=None):
        raw = body if isinstance(body, bytes) else (json.dumps(body).encode() if body is not None else b"")
        self.script.append((status, headers or {}, raw))

    def __call__(self, method, url, headers, body, timeout):
        self.calls.append({"method": method, "url": url, "headers": dict(headers), "body": body})
        if not self.script:
            raise AssertionError("unexpected request " + method + " " + url)
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def token_body(**over):
    body = {"access_token": ACCESS, "refresh_token": REFRESH, "expires_in": 3600, "scope": " ".join(sb.SCOPES), "token_type": "Bearer"}
    body.update(over)
    return body


def connected(http, now=lambda: 1000.0, expires_at=5000.0):
    store = sb.MemoryTokenStore()
    store.save(sb.TokenRecord(ACCESS, REFRESH, expires_at, " ".join(sb.SCOPES), "synthuser"))
    manager = sb.TokenManager(CLIENT, store, http, now=now)
    return sb.SpotifyProvider(manager, http), manager, store


def query_of(call):
    return dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(call["url"]).query))


# --------------------------------------------------------------------------------------------------------------- PKCE and redirect
def test_pkce_s256_matches_the_rfc7636_vector():
    assert sb.challenge_for("dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk") == "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"


def test_verifiers_are_valid_and_unique():
    seen = {sb.new_verifier() for _ in range(50)}
    assert len(seen) == 50
    assert all(43 <= len(v) <= 128 and all(c.isalnum() or c in "-._~" for c in v) for v in seen)


@pytest.mark.parametrize("uri", ["http://127.0.0.1:18475/callback", "http://[::1]:18475/callback"])
def test_loopback_redirects_are_accepted(uri):
    assert sb.redirect_uri_ok(uri)


@pytest.mark.parametrize("uri", [
    "http://localhost:18475/callback", "https://127.0.0.1:18475/callback", "http://127.0.0.1/callback", "http://127.0.0.1:80/callback",
    "http://127.0.0.1:18475/other", "http://127.0.0.1:18475/callback?x=1", "http://127.0.0.1:18475/callback#f", "http://evil.example/callback",
    "http://u@127.0.0.1:18475/callback", "http://192.168.4.37:18475/callback", "http://0.0.0.0:18475/callback", None, 7, ""])
def test_anything_but_a_loopback_callback_is_refused(uri):
    assert not sb.redirect_uri_ok(uri)
    with pytest.raises(ValueError):
        sb.AuthSession(CLIENT, uri)


def test_authorize_url_is_pkce_with_exactly_the_playback_scopes():
    session = sb.AuthSession(CLIENT, REDIRECT)
    parts = urllib.parse.urlsplit(session.authorize_url())
    q = dict(urllib.parse.parse_qsl(parts.query))
    assert (parts.scheme, parts.netloc, parts.path) == ("https", "accounts.spotify.com", "/authorize")
    assert q["response_type"] == "code" and q["client_id"] == CLIENT and q["redirect_uri"] == REDIRECT
    assert q["code_challenge_method"] == "S256" and q["code_challenge"] == sb.challenge_for(session._verifier)
    assert set(q["scope"].split()) == set(sb.SCOPES) and q["state"] == session.state
    assert "client_secret" not in session.authorize_url() and session._verifier not in session.authorize_url()


@pytest.mark.parametrize("client", ["", "  ", "has space", "a&b=c", None, 5])
def test_a_client_id_is_a_plain_alphanumeric_string(client):
    with pytest.raises(ValueError):
        sb.AuthSession(client, REDIRECT)


# --------------------------------------------------------------------------------------------------------------- completion
def test_a_good_callback_exchanges_the_code_with_the_verifier_and_returns_verified_tokens():
    http = FakeHttp()
    session = sb.AuthSession(CLIENT, REDIRECT)
    http.push(200, token_body())
    record = session.complete({"code": "synth-code", "state": session.state}, http, now=lambda: 1000.0)
    assert (record.access_token, record.refresh_token, record.expires_at) == (ACCESS, REFRESH, 4600.0)
    sent = dict(urllib.parse.parse_qsl(http.calls[0]["body"].decode()))
    assert sent["grant_type"] == "authorization_code" and sent["code"] == "synth-code" and sent["code_verifier"] == session._verifier
    assert sent["client_id"] == CLIENT and "client_secret" not in sent and http.calls[0]["url"] == sb.TOKEN_URL


@pytest.mark.parametrize("query,code", [
    ({"code": "c", "state": "wrong"}, "state-mismatch"), ({"code": "c"}, "state-mismatch"), ({"code": "c", "state": None}, "state-mismatch"),
])
def test_a_wrong_or_missing_state_is_refused_before_any_exchange(query, code):
    http = FakeHttp()
    session = sb.AuthSession(CLIENT, REDIRECT)
    with pytest.raises(sb.BindingError) as exc:
        session.complete(query, http)
    assert exc.value.code == code and http.calls == []


def test_a_denied_or_codeless_callback_is_refused():
    for query, code in (({"error": "access_denied", "state": "S"}, "denied"), ({"state": "S"}, "no-code")):
        session = sb.AuthSession(CLIENT, REDIRECT)
        query = dict(query, state=session.state)
        with pytest.raises(sb.BindingError) as exc:
            session.complete(query, FakeHttp())
        assert exc.value.code == code


def test_a_session_is_single_use_even_after_a_failure():
    http = FakeHttp()
    session = sb.AuthSession(CLIENT, REDIRECT)
    http.push(500, {})
    with pytest.raises(sb.BindingError):
        session.complete({"code": "c", "state": session.state}, http)
    with pytest.raises(sb.BindingError) as exc:
        session.complete({"code": "c", "state": session.state}, http)
    assert exc.value.code == "replayed" and len(http.calls) == 1


def test_a_session_expires():
    clock = [0.0]
    session = sb.AuthSession(CLIENT, REDIRECT, clock=lambda: clock[0])
    clock[0] = sb.SESSION_TTL_S + 1
    with pytest.raises(sb.BindingError) as exc:
        session.complete({"code": "c", "state": session.state}, FakeHttp())
    assert exc.value.code == "expired"


@pytest.mark.parametrize("scope", [
    " ".join(sb.SCOPES) + " playlist-modify-public", "user-read-playback-state", "", "user-library-modify " + " ".join(sb.SCOPES)])
def test_extra_or_missing_scopes_are_refused_and_nothing_is_returned(scope):
    http = FakeHttp()
    session = sb.AuthSession(CLIENT, REDIRECT)
    http.push(200, token_body(scope=scope))
    with pytest.raises(sb.BindingError) as exc:
        session.complete({"code": "c", "state": session.state}, http)
    assert exc.value.code == "scope-mismatch"


def test_a_transport_failure_during_exchange_is_a_binding_error_not_a_crash():
    http = FakeHttp()
    session = sb.AuthSession(CLIENT, REDIRECT)
    http.script.append(ProviderError("offline"))
    with pytest.raises(sb.BindingError) as exc:
        session.complete({"code": "c", "state": session.state}, http)
    assert exc.value.code == "exchange-failed"


# --------------------------------------------------------------------------------------------------------------- tokens
def test_token_repr_and_errors_never_carry_secrets():
    http = FakeHttp()
    provider, manager, store = connected(http)
    assert ACCESS not in repr(store.load()) and REFRESH not in repr(store.load())
    http.push(500, {})
    http.push(500, {})
    with pytest.raises(ProviderError) as exc:
        provider.devices()
    assert ACCESS not in str(exc.value) and REFRESH not in str(exc.value)


def test_a_valid_token_is_used_without_refreshing_and_sent_as_a_bearer():
    http = FakeHttp()
    provider, _, _ = connected(http)
    http.push(200, {"devices": []})
    provider.devices()
    assert len(http.calls) == 1 and http.calls[0]["headers"]["Authorization"] == "Bearer " + ACCESS


def test_a_token_near_expiry_is_refreshed_first_and_a_rotated_refresh_token_is_kept():
    http = FakeHttp()
    provider, _, store = connected(http, now=lambda: 4990.0, expires_at=5000.0)
    http.push(200, token_body(access_token="SYNTH-ACCESS-2", refresh_token="SYNTH-REFRESH-2"))
    http.push(200, {"devices": []})
    provider.devices()
    assert http.calls[0]["url"] == sb.TOKEN_URL and dict(urllib.parse.parse_qsl(http.calls[0]["body"].decode()))["refresh_token"] == REFRESH
    assert http.calls[1]["headers"]["Authorization"] == "Bearer SYNTH-ACCESS-2"
    assert store.load().refresh_token == "SYNTH-REFRESH-2" and store.load().user_id == "synthuser"


def test_a_refresh_without_a_new_refresh_token_keeps_the_old_one():
    http = FakeHttp()
    provider, _, store = connected(http, now=lambda: 4990.0)
    body = token_body(access_token="SYNTH-ACCESS-3")
    del body["refresh_token"]
    http.push(200, body)
    http.push(200, {"devices": []})
    provider.devices()
    assert store.load().refresh_token == REFRESH


def test_a_revoked_refresh_token_clears_the_store_and_reports_auth():
    http = FakeHttp()
    provider, manager, store = connected(http, now=lambda: 4990.0)
    http.push(400, {"error": "invalid_grant"})
    with pytest.raises(ProviderError) as exc:
        provider.devices()
    assert exc.value.code == "auth" and store.load() is None and not manager.connected()
    with pytest.raises(ProviderError) as again:
        provider.devices()
    assert again.value.code == "auth" and len(http.calls) == 1        # not connected: no request is even attempted


def test_a_refresh_that_widens_the_scope_is_refused_and_disconnects():
    http = FakeHttp()
    provider, _, store = connected(http, now=lambda: 4990.0)
    http.push(200, token_body(scope=" ".join(sb.SCOPES) + " playlist-modify-private"))
    with pytest.raises(ProviderError) as exc:
        provider.devices()
    assert exc.value.code == "auth" and store.load() is None


def test_revoke_forgets_the_tokens():
    http = FakeHttp()
    _, manager, store = connected(http)
    manager.revoke()
    assert store.load() is None


def test_a_401_is_retried_once_with_a_forced_refresh_then_reported_as_auth():
    http = FakeHttp()
    provider, _, _ = connected(http)
    http.push(401, {"error": {"status": 401}})
    http.push(200, token_body(access_token="SYNTH-ACCESS-4"))
    http.push(200, {"devices": []})
    assert provider.devices() == []
    assert http.calls[2]["headers"]["Authorization"] == "Bearer SYNTH-ACCESS-4"
    http2 = FakeHttp()
    provider2, _, _ = connected(http2)
    http2.push(401, {})
    http2.push(200, token_body())
    http2.push(401, {})
    with pytest.raises(ProviderError) as exc:
        provider2.devices()
    assert exc.value.code == "auth" and len(http2.calls) == 3


# --------------------------------------------------------------------------------------------------------------- file token store
def fake_protect(data):
    return b"PROTECTED:" + data[::-1]


def fake_unprotect(blob):
    if not blob.startswith(b"PROTECTED:"):
        raise ValueError("not protected")
    return blob[len(b"PROTECTED:"):][::-1]


def test_file_store_round_trips_through_protection_and_never_writes_plaintext(tmp_path):
    path = str(tmp_path / "sub" / "spotify.bin")
    store = sb.FileTokenStore(path, fake_protect, fake_unprotect)
    assert store.load() is None
    store.save(sb.TokenRecord(ACCESS, REFRESH, 123.0, "a b", "synthuser"))
    raw = open(path, "rb").read()
    assert ACCESS.encode() not in raw and REFRESH.encode() not in raw
    loaded = store.load()
    assert (loaded.access_token, loaded.refresh_token, loaded.user_id) == (ACCESS, REFRESH, "synthuser")
    assert [n for n in os.listdir(tmp_path / "sub")] == ["spotify.bin"]            # no temp files left behind
    store.clear()
    assert store.load() is None
    store.clear()                                                                   # clearing twice is fine


def test_file_store_needs_protection_and_treats_damage_as_not_connected(tmp_path):
    with pytest.raises(ValueError):
        sb.FileTokenStore(str(tmp_path / "x"), None, fake_unprotect)
    path = str(tmp_path / "spotify.bin")
    store = sb.FileTokenStore(path, fake_protect, fake_unprotect)
    for junk in (b"", b"plain text", b"PROTECTED:not json", fake_protect(b"[1,2]"), fake_protect(b'{"access_token":"x"}')):
        open(path, "wb").write(junk)
        assert store.load() is None


# --------------------------------------------------------------------------------------------------------------- provider requests
def test_reads_only_ever_issue_get_and_writes_carry_an_explicit_device():
    http = FakeHttp()
    provider, _, _ = connected(http)
    http.push(200, {"tracks": {"items": [{"uri": "spotify:track:abc123", "name": "Blue", "artists": [{"name": "A"}, {"name": "B"}]}]}})
    http.push(200, {"devices": [{"id": "dev1", "name": "Kitchen", "is_active": True, "volume_percent": 30}]})
    http.push(204)
    provider.search("blue", "track")
    provider.devices()
    provider.now_playing()
    assert [c["method"] for c in http.calls] == ["GET", "GET", "GET"]
    assert query_of(http.calls[0]) == {"q": "blue", "type": "track", "limit": "5"}
    for name, args in (("play", ("spotify:track:abc123", "dev1")), ("pause", ("dev1",)), ("resume", ("dev1",)), ("next", ("dev1",)),
                       ("queue", ("spotify:track:abc123", "dev1")), ("set_volume", (35, "dev1"))):
        http.push(204)
        getattr(provider, name)(*args)
        assert http.calls[-1]["method"] in ("PUT", "POST") and query_of(http.calls[-1])["device_id"] == "dev1"


def test_play_uses_uris_for_tracks_and_context_for_collections():
    http = FakeHttp()
    provider, _, _ = connected(http)
    http.push(204)
    http.push(204)
    provider.play("spotify:track:abc123", "d")
    provider.play("spotify:playlist:xyz789", "d")
    assert json.loads(http.calls[0]["body"]) == {"uris": ["spotify:track:abc123"]}
    assert json.loads(http.calls[1]["body"]) == {"context_uri": "spotify:playlist:xyz789"}


def test_now_playing_parses_and_nothing_playing_is_none():
    http = FakeHttp()
    provider, _, _ = connected(http)
    http.push(200, {"is_playing": True, "device": {"id": "dev1"}, "item": {"uri": "spotify:track:t1", "name": "Song", "type": "track",
                                                                           "artists": [{"name": "Artist"}]}})
    now = provider.now_playing()
    assert (now.item.title, now.item.artist, now.playing, now.device_id) == ("Song", "Artist", True, "dev1")
    http.push(204)
    assert provider.now_playing() is None


def test_account_verification_and_wrong_account_refusal():
    http = FakeHttp()
    provider, _, _ = connected(http)
    http.push(200, {"id": "synthuser", "product": "premium", "email": "private@example.invalid"})
    assert provider.account() == {"id": "synthuser", "product": "premium"}               # the email is never surfaced
    provider.expected_user_id = "someone-else"
    http.push(200, {"id": "synthuser", "product": "premium"})
    with pytest.raises(ProviderError) as exc:
        provider.account()
    assert exc.value.code == "forbidden"


@pytest.mark.parametrize("status,body,headers,code,retry", [
    (403, {"error": {"reason": "PREMIUM_REQUIRED"}}, {}, "forbidden", None),
    (404, {"error": {"reason": "NO_ACTIVE_DEVICE"}}, {}, "no_device", None),
    (429, {}, {"retry-after": "7"}, "rate_limited", 7),
    (429, {}, {"retry-after": "99999"}, "rate_limited", 3600),
    (429, {}, {}, "rate_limited", None),
    (500, {}, {}, "offline", None),
    (502, b"<html>", {}, "offline", None),
    (418, {}, {}, "unexpected", None),
])
def test_failures_become_typed_provider_errors(status, body, headers, code, retry):
    http = FakeHttp()
    provider, _, _ = connected(http)
    http.push(status, body, headers)
    with pytest.raises(ProviderError) as exc:
        provider.pause("dev1")
    assert exc.value.code == code and exc.value.retry_after == retry


def test_a_transport_exception_is_offline_and_a_write_is_never_retried():
    http = FakeHttp()
    provider, _, _ = connected(http)
    http.script.append(TimeoutError("connection details"))
    with pytest.raises(ProviderError) as exc:
        provider.pause("dev1")
    assert exc.value.code == "offline" and len(http.calls) == 1 and "connection details" not in str(exc.value)


def test_garbage_bodies_do_not_crash_the_reads():
    http = FakeHttp()
    provider, _, _ = connected(http)
    for body in (b"not json", b"[]", b'{"tracks": 5}', b'{"devices": [1, null, {"name": "no id"}]}'):
        http.push(200, body)
    assert provider.search("x", "track") == []
    assert provider.search("x", "track") == []
    assert provider.search("x", "track") == []
    assert provider.devices() == []


def test_the_real_transport_refuses_non_spotify_hosts_without_any_request(monkeypatch):
    """The guard must refuse BEFORE any opener exists: an offline network error (also a ProviderError) must not satisfy this test."""
    def forbidden(*args, **kwargs):
        raise AssertionError("the transport was reached for a non-Spotify url")

    monkeypatch.setattr(sb.urllib.request, "build_opener", forbidden)
    monkeypatch.setattr(sb.urllib.request, "urlopen", forbidden)
    for url in ("http://api.spotify.com/v1/me", "https://evil.example/token", "https://api.spotify.com.evil.example/v1/me",
                "https://accounts.spotify.com.evil.example/api/token", "ftp://api.spotify.com/v1/me", "https://api.spotify.com@evil.example/v1/me"):
        with pytest.raises(ProviderError) as exc:
            sb.urllib_http("GET", url, {}, None, 1)
        assert exc.value.code == "unexpected" and "non-Spotify" in str(exc.value)


# --------------------------------------------------------------------------------------------------------------- through the governed controller
def test_the_controller_governs_the_real_provider_guest_duplicates_and_reads():
    http = FakeHttp()
    provider, _, _ = connected(http)
    controller = MusicController(provider)
    http.push(200, {"devices": [{"id": "dev1", "name": "Kitchen", "is_active": True, "volume_percent": 30}]})
    http.push(204)
    http.push(200, {"is_playing": False, "item": {"uri": "spotify:track:t1", "name": "Song", "type": "track", "artists": []}})
    result = controller.handle("pause", request_id="r1", explicit_command=True)
    assert result.ok and result.status == "done" and not result.simulated and not result.message.startswith("[simulation]")
    assert [c["method"] for c in http.calls] == ["GET", "PUT", "GET"]       # devices, the write, then a read-back of the real state
    duplicate = controller.handle("pause", request_id="r1", explicit_command=True)
    assert duplicate.ok and len(http.calls) == 3                                          # a repeat request id never writes twice
    before = len(http.calls)
    assert controller.handle("pause", request_id="r2", explicit_command=True, guest=True).status == "refused"
    assert controller.handle("pause", request_id="r3").status == "refused"                # no explicit command
    assert len(http.calls) == before
    http.push(200, {"devices": [{"id": "dev1", "name": "Kitchen", "is_active": True}]})
    http.push(429, {}, {"retry-after": "5"})
    failed = controller.handle("resume", request_id="r4", explicit_command=True)
    assert failed.status == "error" and failed.data == {"retry_after": 5} and ACCESS not in json.dumps(failed.trace)


# --------------------------------------------------------------------------------------------------------------- Sol review of #176
def test_a_write_that_gets_a_401_is_never_replayed():
    http = FakeHttp()
    provider, _, _ = connected(http)
    http.push(401, {})
    http.push(200, token_body(access_token="SYNTH-ACCESS-5"))
    with pytest.raises(ProviderError) as exc:
        provider.next("dev1")
    assert exc.value.code == "auth"
    assert [c["method"] for c in http.calls] == ["POST", "POST"] and http.calls[0]["url"] != sb.TOKEN_URL and http.calls[1]["url"] == sb.TOKEN_URL
    assert len([c for c in http.calls if "/me/player/next" in c["url"]]) == 1          # the write went out exactly once
    http.push(204)
    provider.next("dev1")                                                              # the refreshed token serves the NEXT request
    assert http.calls[-1]["headers"]["Authorization"] == "Bearer SYNTH-ACCESS-5"


def test_two_managers_sharing_a_store_do_not_spend_a_refresh_token_twice():
    """Both read the same expiring grant; the second must reuse the first's rotated tokens instead of replaying a spent refresh token."""
    http = FakeHttp()
    store = sb.MemoryTokenStore()
    store.save(sb.TokenRecord(ACCESS, REFRESH, 1000.0, " ".join(sb.SCOPES), "synthuser"))
    first = sb.TokenManager(CLIENT, store, http, now=lambda: 990.0)
    second = sb.TokenManager(CLIENT, store, http, now=lambda: 990.0)
    http.push(200, token_body(access_token="SYNTH-ACCESS-R", refresh_token="SYNTH-REFRESH-R"))
    stale = store.load()
    assert first.access_token() == "SYNTH-ACCESS-R"
    # the second manager decided to refresh on the SAME stale record, before it saw the first's result
    assert second._refresh(stale, False).access_token == "SYNTH-ACCESS-R"
    assert len(http.calls) == 1 and store.load().refresh_token == "SYNTH-REFRESH-R"


def test_a_concurrent_refresh_race_across_threads_makes_one_token_request():
    import threading
    gate = threading.Event()
    seen = []

    def http(method, url, headers, body, timeout):
        seen.append(url)
        gate.wait(2)
        return 200, {}, json.dumps(token_body(access_token="SYNTH-ACCESS-T", refresh_token="SYNTH-REFRESH-T")).encode()

    store = sb.MemoryTokenStore()
    store.save(sb.TokenRecord(ACCESS, REFRESH, 1000.0, " ".join(sb.SCOPES), "synthuser"))
    managers = [sb.TokenManager(CLIENT, store, http, now=lambda: 990.0) for _ in range(4)]
    results = []
    threads = [threading.Thread(target=lambda m=m: results.append(m.access_token())) for m in managers]
    for th in threads:
        th.start()
    gate.set()
    for th in threads:
        th.join(5)
    assert results == ["SYNTH-ACCESS-T"] * 4 and len(seen) == 1 and store.load().refresh_token == "SYNTH-REFRESH-T"


def test_a_refresh_in_flight_cannot_resurrect_revoked_credentials():
    import threading
    entered, release = threading.Event(), threading.Event()

    def http(method, url, headers, body, timeout):
        entered.set()
        release.wait(3)
        return 200, {}, json.dumps(token_body(access_token="SYNTH-ACCESS-Z", refresh_token="SYNTH-REFRESH-Z")).encode()

    store = sb.MemoryTokenStore()
    store.save(sb.TokenRecord(ACCESS, REFRESH, 1000.0, " ".join(sb.SCOPES), "synthuser"))
    manager = sb.TokenManager(CLIENT, store, http, now=lambda: 990.0)
    worker = threading.Thread(target=lambda: manager.access_token())
    worker.start()
    assert entered.wait(3)
    revoker = threading.Thread(target=manager.revoke)
    revoker.start()                     # queued behind the refresh: it must run AFTER the refresh saves, and win
    release.set()
    worker.join(5)
    revoker.join(5)
    assert store.load() is None and not manager.connected()


def test_a_rejected_refresh_token_that_someone_else_already_replaced_is_not_cleared():
    http = FakeHttp()
    store = sb.MemoryTokenStore()
    store.save(sb.TokenRecord(ACCESS, REFRESH, 1000.0, " ".join(sb.SCOPES), "synthuser"))
    manager = sb.TokenManager(CLIENT, store, http, now=lambda: 990.0)
    store.save(sb.TokenRecord("SYNTH-ACCESS-N", "SYNTH-REFRESH-N", 5000.0, " ".join(sb.SCOPES), "synthuser"))   # another process rotated
    stale = sb.TokenRecord(ACCESS, REFRESH, 1000.0, " ".join(sb.SCOPES), "synthuser")
    assert manager._refresh(stale, False).access_token == "SYNTH-ACCESS-N" and http.calls == []
    assert store.load().refresh_token == "SYNTH-REFRESH-N"


def test_file_store_exclusive_section_serialises_other_processes(tmp_path):
    import subprocess
    import sys
    path = str(tmp_path / "spotify.bin")
    store = sb.FileTokenStore(path, fake_protect, fake_unprotect)
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    code = ("import sys, time; sys.path.insert(0, %r)\n"
            "from src import spotify_binding as sb\n"
            "s = sb.FileTokenStore(%r, lambda b: b, lambda b: b)\n"
            "with s.exclusive():\n    print('locked', flush=True); time.sleep(1.5)\n") % (root, path)
    holder = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, text=True)
    try:
        assert holder.stdout.readline().strip() == "locked"
        began = time.monotonic()
        with store.exclusive():
            waited = time.monotonic() - began
        assert waited >= 0.8
    finally:
        holder.wait(10)


def test_refresh_coalescing_also_works_when_spotify_keeps_the_same_refresh_token():
    """Sol: coalescing keyed on the refresh-token string refreshed twice when Spotify omits a new refresh token, and a 503 on the second broke valid credentials."""
    http = FakeHttp()
    store = sb.MemoryTokenStore()
    store.save(sb.TokenRecord(ACCESS, REFRESH, 1000.0, " ".join(sb.SCOPES), "synthuser"))
    first = sb.TokenManager(CLIENT, store, http, now=lambda: 990.0)
    second = sb.TokenManager(CLIENT, store, http, now=lambda: 990.0)
    stale = store.load()
    body = token_body(access_token="SYNTH-ACCESS-K")
    del body["refresh_token"]
    http.push(200, body)
    http.push(503, {})                                                  # a second, unnecessary refresh would fail with this
    assert first.access_token() == "SYNTH-ACCESS-K"
    assert second._refresh(stale, False).access_token == "SYNTH-ACCESS-K" and len(http.calls) == 1
    assert second._refresh(stale, True).access_token == "SYNTH-ACCESS-K" and len(http.calls) == 1      # a forced refresh coalesces too


def test_lock_contention_that_outlasts_the_bound_is_a_typed_offline_error(tmp_path, monkeypatch):
    """Sol: msvcrt.LK_LOCK raises a bare OSError after ~10 s; contention now polls to a bound and reports offline."""
    store = sb.FileTokenStore(str(tmp_path / "spotify.bin"), fake_protect, fake_unprotect)
    monkeypatch.setattr(sb, "LOCK_WAIT_S", 0.3)
    monkeypatch.setattr(sb, "_lock_file", lambda handle, wait_s: (_ for _ in ()).throw(ProviderError("offline", "token store busy")))
    with pytest.raises(ProviderError) as exc:
        with store.exclusive():
            pass
    assert exc.value.code == "offline"
    store.save(sb.TokenRecord(ACCESS, REFRESH, 1000.0, "a", "u"))
    manager = sb.TokenManager(CLIENT, store, FakeHttp(), now=lambda: 990.0)
    with pytest.raises(ProviderError) as busy:
        manager.access_token()                                          # expired grant -> refresh -> lock busy
    assert busy.value.code == "offline"


def test_the_real_file_lock_polls_and_gives_up_with_a_typed_error(tmp_path):
    import subprocess
    import sys
    path = str(tmp_path / "spotify.bin")
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    code = ("import sys, time; sys.path.insert(0, %r)\n"
            "from src import spotify_binding as sb\n"
            "s = sb.FileTokenStore(%r, lambda b: b, lambda b: b)\n"
            "with s.exclusive():\n    print('locked', flush=True); time.sleep(3)\n") % (root, path)
    holder = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, text=True)
    try:
        assert holder.stdout.readline().strip() == "locked"
        original = sb.LOCK_WAIT_S
        sb.LOCK_WAIT_S = 0.4
        try:
            began = time.monotonic()
            with pytest.raises(ProviderError) as exc:
                with sb.FileTokenStore(path, fake_protect, fake_unprotect).exclusive():
                    pass
            assert exc.value.code == "offline" and time.monotonic() - began < 2.5
        finally:
            sb.LOCK_WAIT_S = original
    finally:
        holder.wait(10)


def test_a_delayed_401_for_an_already_replaced_token_reuses_the_newer_one():
    """Sol third pass: a second caller's 401 for token A, after another caller already refreshed to B, forced a needless second refresh."""
    store = sb.MemoryTokenStore()
    store.save(sb.TokenRecord(ACCESS, REFRESH, 5000.0, " ".join(sb.SCOPES), "synthuser"))
    seen = []

    def http(method, url, headers, body, timeout):
        seen.append((method, url, headers.get("Authorization")))
        if len(seen) == 1:                                          # token A is sent, and meanwhile another caller refreshes to B
            store.save(sb.TokenRecord("SYNTH-ACCESS-B", "SYNTH-REFRESH-B", 5000.0, " ".join(sb.SCOPES), "synthuser"))
            return 401, {}, b"{}"
        if url == sb.TOKEN_URL:
            return 503, {}, b"{}"                                   # an unnecessary refresh would fail here
        return 200, {}, json.dumps({"devices": []}).encode()

    provider = sb.SpotifyProvider(sb.TokenManager(CLIENT, store, http, now=lambda: 1000.0), http)
    assert provider.devices() == []
    assert [s[1] == sb.TOKEN_URL for s in seen] == [False, False]
    assert seen[0][2] == "Bearer " + ACCESS and seen[1][2] == "Bearer SYNTH-ACCESS-B"


# ---------------------------------------------------------------------------------------------------------------------- read retries (live: Spotify answers an intermittent 503 on /search)
@pytest.fixture(autouse=True)
def _no_backoff(monkeypatch):
    monkeypatch.setattr(sb, "READ_BACKOFF_S", 0)


def test_a_read_is_repeated_after_transient_5xx_and_succeeds():
    http = FakeHttp()
    provider, _, _ = connected(http)
    http.push(503, {})
    http.push(502, b"<html>")
    http.push(200, {"devices": []})
    assert provider.devices() == [] and [c["method"] for c in http.calls] == ["GET", "GET", "GET"]


def test_a_read_gives_up_after_the_bounded_retries_with_a_typed_error():
    http = FakeHttp()
    provider, _, _ = connected(http)
    for _ in range(sb.READ_RETRIES + 1):
        http.push(503, {})
    with pytest.raises(ProviderError) as exc:
        provider.devices()
    assert exc.value.code == "offline" and len(http.calls) == sb.READ_RETRIES + 1


def test_a_transport_failure_on_a_read_is_repeated_too():
    http = FakeHttp()
    provider, _, _ = connected(http)
    http.script.append(TimeoutError("slow"))
    http.push(200, {"devices": []})
    assert provider.devices() == [] and len(http.calls) == 2


def test_writes_and_non_transient_read_errors_are_never_repeated():
    http = FakeHttp()
    provider, _, _ = connected(http)
    http.push(503, {})
    with pytest.raises(ProviderError):
        provider.pause("dev1")
    assert len(http.calls) == 1                                           # a write: one attempt only
    for status, code in ((429, "rate_limited"), (403, "forbidden"), (404, "no_device")):
        http2 = FakeHttp()
        provider2, _, _ = connected(http2)
        http2.push(status, {})
        with pytest.raises(ProviderError) as exc:
            provider2.devices()
        assert exc.value.code == code and len(http2.calls) == 1
