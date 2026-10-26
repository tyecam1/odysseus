"""Music in the Misumi path: the command parser, the runtime wiring over a fake Spotify transport, and the /misumi/respond route end to end.

No network and no credentials: tokens here are synthetic and the transport is scripted."""

import json
import urllib.parse

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import routes.misumi_routes as misumi_routes
from src import spotify_binding as sb
from src.misumi_persona_routing import resolve_auto_lead
from src.music_commands import MusicCommand, parse_music_command
from src.music_runtime import MusicRuntime, _speak, music_reply
from services.memory.skills import SkillsManager

ACCESS, REFRESH = "SYNTH-ACCESS-M", "SYNTH-REFRESH-M"
SCOPE = " ".join(sb.SCOPES)


# ---------------------------------------------------------------------------------------------------------------------- parser
@pytest.mark.parametrize("text,expected", [
    ("play Arevil's Gardens by The Land of Rah on Spotify", MusicCommand("play", query="Arevil's Gardens by The Land of Rah")),
    ("Could you please play the album Kind of Blue", MusicCommand("play", query="Kind of Blue", kind="album")),
    ("play the playlist Late Night", MusicCommand("play", query="Late Night", kind="playlist")),
    ("play some music by Nina Simone", MusicCommand("play", query="some music by Nina Simone")),
    ("queue Blue in Green", MusicCommand("queue", query="Blue in Green")),
    ("add Blue in Green to the queue", MusicCommand("queue", query="Blue in Green")),
    ("pause", MusicCommand("pause")), ("pause the music", MusicCommand("pause")), ("stop the music please", MusicCommand("pause")),
    ("resume", MusicCommand("resume")), ("play", MusicCommand("resume")), ("play it", MusicCommand("resume")),
    ("skip", MusicCommand("next")), ("skip this song", MusicCommand("next")), ("next track", MusicCommand("next")),
    ("what's playing", MusicCommand("now_playing")), ("what song is this", MusicCommand("now_playing")),
    ("what are the devices", MusicCommand("devices")), ("list my devices", MusicCommand("devices")),
    ("volume 30", MusicCommand("volume", volume=30)), ("set the volume to 40%", MusicCommand("volume", volume=40)),
    ("turn it down", MusicCommand("volume", volume_delta=-15)), ("louder", MusicCommand("volume", volume_delta=15)),
    ("turn the music up", MusicCommand("volume", volume_delta=15)),
])
def test_music_requests_parse_to_the_right_action(text, expected):
    assert parse_music_command(text) == expected


@pytest.mark.parametrize("text", [
    "", "   ", "I played football yesterday", "the song is playing nicely", "pause the rota", "skip the washing up", "what should I play tonight?",
    "which record should I play?", "play something", "play a game of chess with me", "play cards", "play with me", "we should play more music", "x" * 500, None, 7,
])
def test_talk_that_is_not_a_music_command_is_left_alone(text):
    assert parse_music_command(text) is None


# ---------------------------------------------------------------------------------------------------------------------- runtime
class FakeHttp:
    def __init__(self):
        self.script, self.calls = [], []

    def push(self, status, body=None, headers=None):
        raw = json.dumps(body).encode() if body is not None else b""
        self.script.append((status, headers or {}, raw))

    def __call__(self, method, url, headers, body, timeout):
        self.calls.append((method, url, dict(headers), body))
        if not self.script:
            raise AssertionError("unexpected request %s %s" % (method, url))
        return self.script.pop(0)


def protect(data):
    return b"P:" + data[::-1]


def unprotect(blob):
    assert blob.startswith(b"P:")
    return blob[2:][::-1]


def make_runtime(tmp_path, http, configured=True):
    directory = tmp_path / "data" / "spotify"
    if configured:
        directory.mkdir(parents=True)
        (directory / "client.json").write_text(json.dumps({"client_id": "synthetic0client0id"}))
        sb.FileTokenStore(str(directory / "token.bin"), protect, unprotect).save(
            sb.TokenRecord(ACCESS, REFRESH, 4_000_000_000.0, SCOPE, "synthuser"))
    return MusicRuntime(tmp_path / "data", http=http, protection=(protect, unprotect))


DEVICE = {"devices": [{"id": "dev1", "name": "Laptop", "is_active": True, "volume_percent": 40}]}
PLAYING = {"is_playing": True, "device": {"id": "dev1"}, "item": {"uri": "spotify:track:t1", "name": "Song", "type": "track", "artists": [{"name": "Artist"}]}}


def test_not_configured_means_not_connected_and_no_request_is_made(tmp_path):
    http = FakeHttp()
    runtime = make_runtime(tmp_path, http, configured=False)
    assert not runtime.configured()
    out = music_reply(runtime, "pause", "jin", "r1", allow_writes=True)
    assert out["status"] == "not_connected" and "isn't connected" in out["text"] and http.calls == []


def test_play_resolves_the_duplicate_release_and_reads_the_state_back(tmp_path):
    http = FakeHttp()
    runtime = make_runtime(tmp_path, http)
    row = {"name": "Arevil's Gardens (Rip)", "artists": [{"name": "The Land of Rah"}]}
    http.push(200, DEVICE)                  # the controller resolves the device first
    http.push(200, {"tracks": {"items": [dict(row, uri="spotify:track:aaa111"), dict(row, uri="spotify:track:bbb222")]}})   # the same release twice
    http.push(204)
    http.push(200, dict(PLAYING, item=dict(PLAYING["item"], uri="spotify:track:aaa111")))
    out = music_reply(runtime, "play Arevil's Gardens by The Land of Rah on Spotify", "jin", "r2", allow_writes=True)
    assert out["status"] == "done" and out["text"].startswith("Playing on Laptop")
    put = [c for c in http.calls if c[0] == "PUT"][0]
    assert json.loads(put[3]) == {"uris": ["spotify:track:aaa111"]}
    assert all(c[2]["Authorization"] == "Bearer " + ACCESS for c in http.calls)
    assert ACCESS not in out["text"] and REFRESH not in json.dumps(out)


def test_an_ambiguous_request_lists_the_choices_instead_of_guessing(tmp_path):
    http = FakeHttp()
    runtime = make_runtime(tmp_path, http)
    http.push(200, DEVICE)
    http.push(200, {"tracks": {"items": [
        {"uri": "spotify:track:aaa111", "name": "Blue", "artists": [{"name": "Joni Mitchell"}]},
        {"uri": "spotify:track:bbb222", "name": "Blue", "artists": [{"name": "Eiffel 65"}]}]}})
    out = music_reply(runtime, "play blue", "jin", "r3", allow_writes=True)
    assert out["status"] == "clarify" and "Joni Mitchell" in out["text"] and "Eiffel 65" in out["text"] and "Say which one" in out["text"]
    assert {c[0] for c in http.calls} == {"GET"}                     # nothing was written


def test_relative_volume_reads_the_active_device_and_stays_bounded(tmp_path):
    http = FakeHttp()
    runtime = make_runtime(tmp_path, http)
    http.push(200, DEVICE)                  # my own read of the level (40)
    http.push(200, DEVICE)                  # the controller's device resolution
    http.push(204)
    http.push(200, PLAYING)
    out = music_reply(runtime, "turn it down", "jin", "r4", allow_writes=True)
    put = [c for c in http.calls if c[0] == "PUT"][0]
    assert dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(put[1]).query))["volume_percent"] == "25" and out["status"].startswith("done")


def test_what_is_playing_and_devices_are_read_only(tmp_path):
    http = FakeHttp()
    runtime = make_runtime(tmp_path, http)
    http.push(200, PLAYING)
    http.push(200, DEVICE)
    now = music_reply(runtime, "what's playing", "aoteru", "r5", allow_writes=True)
    devices = music_reply(runtime, "list my devices", "aoteru", "r6", allow_writes=True)
    assert "Song" in now["text"] and "Artist" in now["text"] and "Laptop (active)" in devices["text"]
    assert {c[0] for c in http.calls} == {"GET"}


def test_failures_become_honest_sentences(tmp_path):
    http = FakeHttp()
    runtime = make_runtime(tmp_path, http)
    http.push(200, DEVICE)
    http.push(429, {}, {"retry-after": "5"})
    out = music_reply(runtime, "pause", "jin", "r7", allow_writes=True)
    assert out["status"] == "error" and "slow down" in out["text"] and "Try again shortly" in out["text"]


# ---------------------------------------------------------------------------------------------------------------------- who handles what
@pytest.mark.parametrize("prompt,lead,handled", [
    ("play Blue by Joni Mitchell", "jin", True),
    ("play Blue by Joni Mitchell on Spotify", "aoteru", True),         # naming Spotify is explicit
    ("play a game of chess", "aoteru", False),                          # a play request routed elsewhere without Spotify is not music
    ("play a game of chess", "lelouch", False),
    ("pause", "aoteru", True), ("skip", "aoteru", True), ("what's playing", "sanji", True),
    ("I like to play", "jin", False), ("shopping list", "jin", False),
])
def test_only_plainly_musical_turns_are_taken(tmp_path, prompt, lead, handled):
    runtime = make_runtime(tmp_path, FakeHttp(), configured=False)
    assert runtime.wants(parse_music_command(prompt), prompt, lead) is handled


def test_speak_never_invents_state():
    from src.music_capability import MusicResult
    assert _speak(MusicResult("play", "done_unconfirmed", "Playing on Laptop, but I could not confirm the player's state.")).endswith("state.")


# ---------------------------------------------------------------------------------------------------------------------- through /misumi/respond
@pytest.fixture
def app_client(tmp_path, monkeypatch):
    http = FakeHttp()
    runtime = make_runtime(tmp_path, http)
    monkeypatch.setattr(misumi_routes, "MusicRuntime", lambda data_dir: runtime)
    monkeypatch.setenv("MISUMI_HOUSEHOLD_ROOT", str(tmp_path / "household"))
    (tmp_path / "household").mkdir()
    app = FastAPI()
    app.include_router(misumi_routes.setup_misumi_routes(SkillsManager(str(tmp_path / "skills"))))
    return TestClient(app), http


def ask(client, prompt, persona="auto"):
    response = client.post("/misumi/respond", json={"prompt": prompt, "persona": persona, "persist_turn": False, "retention_mode": "off"})
    assert response.status_code == 200
    return response.json()


def test_asking_aoteru_to_play_spotify_is_answered_by_jin_through_the_respond_route(app_client):
    client, http = app_client
    http.push(200, DEVICE)
    http.push(200, {"tracks": {"items": [{"uri": "spotify:track:aaa111", "name": "Arevil's Gardens (Rip)", "artists": [{"name": "The Land of Rah"}]}]}})
    http.push(204)
    http.push(200, dict(PLAYING, item=dict(PLAYING["item"], uri="spotify:track:aaa111")))
    body = ask(client, "Aoteru, play Arevil's Gardens by The Land of Rah on Spotify")
    assert body["source"] == "music" and body["persona"] == "jin" and body["who"] == "Jin"
    assert body["text"].startswith("Playing on Laptop") and body["history_persisted"] is False
    assert body["music"] == {"status": "done", "capability": "music.*", "provider": "spotify"}
    assert ACCESS not in json.dumps(body) and REFRESH not in json.dumps(body)


def test_a_plain_pause_works_when_music_is_playing(app_client):
    client, http = app_client
    http.push(200, DEVICE)
    http.push(204)
    http.push(200, dict(PLAYING, is_playing=False))
    body = ask(client, "pause the music")
    assert body["source"] == "music" and body["text"].startswith("Paused on Laptop")


def test_other_questions_are_untouched_by_the_music_hook(app_client):
    client, http = app_client
    body = ask(client, "What should I play tonight?", persona="jin")
    assert body["source"] != "music" and http.calls == []
    body = ask(client, "play a game of chess with me")
    assert body["source"] != "music" and http.calls == []


def test_without_authorisation_the_answer_says_so_and_nothing_is_attempted(tmp_path, monkeypatch):
    runtime = make_runtime(tmp_path, FakeHttp(), configured=False)
    monkeypatch.setattr(misumi_routes, "MusicRuntime", lambda data_dir: runtime)
    monkeypatch.setenv("MISUMI_HOUSEHOLD_ROOT", str(tmp_path))
    app = FastAPI()
    app.include_router(misumi_routes.setup_misumi_routes(SkillsManager(str(tmp_path / "skills"))))
    body = ask(TestClient(app), "play Blue by Joni Mitchell on Spotify")
    assert body["source"] == "music" and "isn't connected" in body["text"]


def test_music_can_be_switched_off(tmp_path, monkeypatch):
    monkeypatch.setenv("MISUMI_MUSIC", "0")
    monkeypatch.setenv("MISUMI_HOUSEHOLD_ROOT", str(tmp_path))
    app = FastAPI()
    app.include_router(misumi_routes.setup_misumi_routes(SkillsManager(str(tmp_path / "skills"))))
    assert ask(TestClient(app), "pause the music")["source"] != "music"


# ---------------------------------------------------------------------------------------------------------------------- Sol review of #179
@pytest.mark.parametrize("text,expected", [
    ("play Thank You on Spotify", MusicCommand("play", query="Thank You")),
    ("play Please on Spotify", MusicCommand("play", query="Please")),
    ("play No Thanks on Spotify", MusicCommand("play", query="No Thanks")),
    ("play Blue, please", MusicCommand("play", query="Blue")),
    ("pause please", MusicCommand("pause")),
])
def test_politeness_words_that_are_titles_stay_in_the_query(text, expected):
    assert parse_music_command(text) == expected


@pytest.mark.parametrize("text", ["What is this?", "what is this", "continue", "carry on", "skip it", "stop it", "stop this", "keep going"])
def test_ordinary_conversation_is_not_taken_for_a_music_command(text):
    assert parse_music_command(text) is None


def test_a_bare_volume_change_needs_a_musical_context(tmp_path):
    runtime = make_runtime(tmp_path, FakeHttp(), configured=False)
    for prompt in ("turn it down", "louder"):
        assert runtime.wants(parse_music_command(prompt), prompt, "aoteru") is False       # could be the TV
        assert runtime.wants(parse_music_command(prompt), prompt, "jin") is True
    assert runtime.wants(parse_music_command("turn the music down"), "turn the music down", "aoteru") is True


def test_play_by_an_artist_is_enough_but_a_bare_play_is_not(tmp_path):
    runtime = make_runtime(tmp_path, FakeHttp(), configured=False)
    assert runtime.wants(parse_music_command("play Blue by Joni Mitchell"), "play Blue by Joni Mitchell", "aoteru") is True
    assert runtime.wants(parse_music_command("play Kind of Blue"), "play Kind of Blue", "aoteru") is False


def test_relative_volume_acts_on_the_device_it_can_read_not_a_guess(tmp_path):
    """Sol: with only an inactive speaker at 10%, 'turn it down' used to assume 50% and set 35%."""
    http = FakeHttp()
    runtime = make_runtime(tmp_path, http)
    http.push(200, {"devices": [{"id": "d1", "name": "Hall", "is_active": False, "volume_percent": 10}]})
    http.push(200, {"devices": [{"id": "d1", "name": "Hall", "is_active": False, "volume_percent": 10}]})
    http.push(204)
    http.push(200, PLAYING)
    music_reply(runtime, "turn the music down", "jin", "rv1", allow_writes=True)
    put = [c for c in http.calls if c[0] == "PUT"]
    assert put and dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(put[0][1]).query))["volume_percent"] == "0"
    http2 = FakeHttp()
    runtime2 = make_runtime(tmp_path / "b", http2)
    http2.push(200, {"devices": [{"id": "d1", "name": "Hall", "is_active": False}, {"id": "d2", "name": "Den", "is_active": False}]})
    out = music_reply(runtime2, "turn the music down", "jin", "rv2", allow_writes=True)
    assert out["status"] == "clarify" and "Say a number" in out["text"] and {c[0] for c in http2.calls} == {"GET"}


def test_two_inactive_speakers_produce_a_choice_not_a_crash(tmp_path):
    http = FakeHttp()
    runtime = make_runtime(tmp_path, http)
    http.push(200, {"devices": [{"id": "d1", "name": "Hall", "is_active": False}, {"id": "d2", "name": "Den", "is_active": False}]})
    out = music_reply(runtime, "pause", "jin", "rd1", allow_writes=True)
    assert out["status"] == "clarify" and "Hall" in out["text"] and "Den" in out["text"] and "failed" not in out["text"]


def test_a_caller_without_execute_authority_can_read_but_never_change_playback(tmp_path):
    http = FakeHttp()
    runtime = make_runtime(tmp_path, http)
    out = music_reply(runtime, "skip this song", "jin", "ra1", allow_writes=False)
    assert out["status"] == "refused" and "isn't allowed to change playback" in out["text"] and http.calls == []
    http.push(200, PLAYING)
    assert "Song" in music_reply(runtime, "what's playing", "jin", "ra2", allow_writes=False)["text"]


def test_the_same_request_id_never_plays_twice(tmp_path):
    http = FakeHttp()
    runtime = make_runtime(tmp_path, http)
    http.push(200, DEVICE)
    http.push(204)
    http.push(200, dict(PLAYING, is_playing=False))
    music_reply(runtime, "pause", "jin", "same-key", allow_writes=True)
    before = len(http.calls)
    again = music_reply(runtime, "pause", "jin", "same-key", allow_writes=True)
    assert again["status"].startswith("done") and len(http.calls) == before


def test_playlists_and_albums_with_equal_names_are_separate_choices(tmp_path):
    http = FakeHttp()
    runtime = make_runtime(tmp_path, http)
    provider = runtime._build() and runtime._provider
    http.push(200, {"playlists": {"items": [
        {"uri": "spotify:playlist:p1", "name": "Road Trip", "owner": {"display_name": "Alex"}},
        {"uri": "spotify:playlist:p2", "name": "Road Trip", "owner": {"display_name": "Alex"}}]}})
    assert [i.uri for i in provider.search("road trip", "playlist")] == ["spotify:playlist:p1", "spotify:playlist:p2"]


def test_a_context_only_turn_is_never_a_music_command(tmp_path, monkeypatch):
    http = FakeHttp()
    runtime = make_runtime(tmp_path, http)
    monkeypatch.setattr(misumi_routes, "MusicRuntime", lambda data_dir: runtime)
    monkeypatch.setenv("MISUMI_HOUSEHOLD_ROOT", str(tmp_path))
    app = FastAPI()
    app.include_router(misumi_routes.setup_misumi_routes(SkillsManager(str(tmp_path / "skills"))))
    response = TestClient(app).post("/misumi/respond", json={"prompt": "", "context": "resume", "persist_turn": False, "retention_mode": "off"})
    assert response.status_code == 200 and response.json()["source"] != "music" and http.calls == []


def _scoped_client(tmp_path, monkeypatch, scopes):
    http = FakeHttp()
    runtime = make_runtime(tmp_path, http)
    monkeypatch.setattr(misumi_routes, "MusicRuntime", lambda data_dir: runtime)
    monkeypatch.setenv("MISUMI_HOUSEHOLD_ROOT", str(tmp_path))
    app = FastAPI()

    @app.middleware("http")
    async def as_api_token(request, call_next):
        request.state.api_token = True
        request.state.api_token_scopes = scopes
        return await call_next(request)

    app.include_router(misumi_routes.setup_misumi_routes(SkillsManager(str(tmp_path / "skills"))))
    return TestClient(app), http


def test_a_read_only_token_cannot_skip_a_track_through_respond(tmp_path, monkeypatch):
    client, http = _scoped_client(tmp_path, monkeypatch, ["misumi:read"])
    body = client.post("/misumi/respond", json={"prompt": "skip this song", "persist_turn": False, "retention_mode": "off"}).json()
    assert body["source"] == "music" and "isn't allowed to change playback" in body["text"] and http.calls == []


def test_an_execute_token_can_and_a_client_key_makes_a_retry_safe(tmp_path, monkeypatch):
    client, http = _scoped_client(tmp_path, monkeypatch, ["misumi:read", "misumi:execute"])
    http.push(200, DEVICE)
    http.push(204)
    http.push(200, PLAYING)
    first = client.post("/misumi/respond", json={"prompt": "skip this song", "request_id": "client-op-1", "persist_turn": False,
                                                  "retention_mode": "off"}).json()
    calls = len(http.calls)
    second = client.post("/misumi/respond", json={"prompt": "skip this song", "request_id": "client-op-1", "persist_turn": False,
                                                   "retention_mode": "off"}).json()
    assert first["source"] == second["source"] == "music" and len(http.calls) == calls                    # the retry did not skip twice


# ---------------------------------------------------------------------------------------------------------------------- the token import
def _import_module():
    import importlib.util
    import os
    spec = importlib.util.spec_from_file_location("spotify_import_token", os.path.join(os.path.dirname(__file__), "..", "scripts", "spotify_import_token.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _record(token="SYNTH-ACCESS-I", refresh="SYNTH-REFRESH-I"):
    return sb.TokenRecord(token, refresh, 4_000_000_000.0, SCOPE, "synthuser")


def test_import_writes_the_pair_and_a_failure_restores_the_previous_pair(tmp_path, monkeypatch):
    imp = _import_module()
    directory = str(tmp_path / "spotify")
    imp.install(directory, "clientaaaaaaaaaaaa", _record("A1", "R1"), protect, unprotect)
    store = sb.FileTokenStore(directory + "/token.bin", protect, unprotect)
    assert store.load().refresh_token == "R1" and json.load(open(directory + "/client.json"))["client_id"] == "clientaaaaaaaaaaaa"
    real_replace = imp.os.replace
    monkeypatch.setattr(imp.os, "replace", lambda a, b: (_ for _ in ()).throw(PermissionError("denied")) if str(b).endswith("client.json") else real_replace(a, b))
    with pytest.raises(PermissionError):
        imp.install(directory, "clientbbbbbbbbbbbb", _record("B1", "R2"), protect, unprotect)
    monkeypatch.undo()
    assert store.load().refresh_token == "R1"                                                   # the old token is back
    assert json.load(open(directory + "/client.json"))["client_id"] == "clientaaaaaaaaaaaa"      # and so is the old client
    assert not [n for n in __import__("os").listdir(directory) if n.endswith(".tmp")]


def test_import_waits_for_a_refresh_in_flight_and_then_wins(tmp_path):
    import threading
    imp = _import_module()
    directory = str(tmp_path / "spotify")
    store = sb.FileTokenStore(directory + "/token.bin", protect, unprotect)
    imp.install(directory, "clientaaaaaaaaaaaa", _record("A1", "R1"), protect, unprotect)
    inside, release = threading.Event(), threading.Event()

    def refresher():
        with store.exclusive():                                  # what TokenManager._refresh holds while it talks to Spotify
            inside.set()
            release.wait(5)
            store.save(_record("OLD-ACCOUNT", "R-OLD"))           # the late refresh result of the OLD account

    worker = threading.Thread(target=refresher)
    worker.start()
    assert inside.wait(3)
    installer = threading.Thread(target=lambda: imp.install(directory, "clientbbbbbbbbbbbb", _record("NEW", "R-NEW"), protect, unprotect))
    installer.start()
    release.set()
    worker.join(5)
    installer.join(5)
    assert store.load().refresh_token == "R-NEW"                  # the import ran AFTER the refresh and replaced it


def test_import_refuses_wrong_scopes_and_writes_nothing(tmp_path):
    imp = _import_module()
    payload = json.dumps({"client_id": "synthetic0client0id", "access_token": "a", "refresh_token": "r", "expires_at": 4e9,
                          "scope": SCOPE + " playlist-modify-public", "user_id": "u"})
    with pytest.raises(SystemExit):
        imp.parse_payload(payload)


def test_a_device_with_no_readable_level_is_never_guessed_at(tmp_path):
    http = FakeHttp()
    runtime = make_runtime(tmp_path, http)
    http.push(200, {"devices": [{"id": "d1", "name": "Hall", "is_active": True}]})
    out = music_reply(runtime, "turn the music down", "jin", "rg1", allow_writes=True)
    assert out["status"] == "clarify" and "Say a number" in out["text"] and {c[0] for c in http.calls} == {"GET"}


# ---------------------------------------------------------------------------------------------------------------------- Sol second pass on #179
@pytest.mark.parametrize("text", ["add the album to my wishlist", "add milk to the shopping list", "start the music lesson", "start the dishwasher"])
def test_adding_or_starting_things_that_are_not_music_is_left_alone(text):
    assert parse_music_command(text) is None


def test_only_the_queue_forms_queue():
    assert parse_music_command("add Blue in Green to the queue") == MusicCommand("queue", query="Blue in Green")
    assert parse_music_command("add Blue in Green to up next") == MusicCommand("queue", query="Blue in Green")
    assert parse_music_command("queue up Blue").action == "queue"


def test_a_title_made_of_politeness_words_is_kept_and_a_trailing_please_is_a_fallback_only():
    assert parse_music_command("play Please Please Please on Spotify").query == "Please Please Please"
    cmd = parse_music_command("play Blue please")
    assert cmd.query == "Blue please" and cmd.fallback_query == "Blue"
    assert parse_music_command("could you play Blue please") == MusicCommand("play", query="Blue")


def test_the_trailing_please_fallback_is_used_only_when_the_literal_finds_nothing(tmp_path):
    http = FakeHttp()
    runtime = make_runtime(tmp_path, http)
    http.push(200, {"tracks": {"items": []}})                       # "Blue please" matches nothing
    http.push(200, DEVICE)
    http.push(200, {"tracks": {"items": [{"uri": "spotify:track:aaa111", "name": "Blue", "artists": [{"name": "Joni Mitchell"}]}]}})
    http.push(204)
    http.push(200, dict(PLAYING, item=dict(PLAYING["item"], uri="spotify:track:aaa111")))
    out = music_reply(runtime, "play Blue please on Spotify", "jin", "rf1", allow_writes=True)
    assert out["status"] == "done"
    searches = [urllib.parse.parse_qs(urllib.parse.urlsplit(c[1]).query).get("q") for c in http.calls if "/search" in c[1]]
    assert searches == [["Blue please"], ["Blue"]]
    http2 = FakeHttp()
    runtime2 = make_runtime(tmp_path / "b", http2)
    http2.push(200, {"tracks": {"items": [{"uri": "spotify:track:p1", "name": "Please Please Please", "artists": [{"name": "Sabrina Carpenter"}]}]}})
    http2.push(200, DEVICE)
    http2.push(200, {"tracks": {"items": [{"uri": "spotify:track:p1", "name": "Please Please Please", "artists": [{"name": "Sabrina Carpenter"}]}]}})
    http2.push(204)
    http2.push(200, dict(PLAYING, item=dict(PLAYING["item"], uri="spotify:track:p1")))
    music_reply(runtime2, "play Please Please Please on Spotify", "jin", "rf2", allow_writes=True)
    assert [urllib.parse.parse_qs(urllib.parse.urlsplit(c[1]).query).get("q") for c in http2.calls if "/search" in c[1]] == [["Please Please Please"]] * 2


def test_long_distinct_request_keys_never_collide(tmp_path):
    http = FakeHttp()
    runtime = make_runtime(tmp_path, http)
    for _ in range(2):
        http.push(200, DEVICE)
        http.push(204)
        http.push(200, PLAYING)
    first = music_reply(runtime, "skip this song", "jin", "a" * 48 + "-first", allow_writes=True)
    second = music_reply(runtime, "skip this song", "jin", "a" * 48 + "-second", allow_writes=True)
    assert first["status"].startswith("done") and second["status"].startswith("done")
    assert len([c for c in http.calls if c[0] == "POST" and "/next" in c[1]]) == 2                 # both really skipped


def test_a_retried_relative_volume_returns_the_first_answer_without_recomputing(tmp_path):
    http = FakeHttp()
    runtime = make_runtime(tmp_path, http)
    http.push(200, DEVICE)                                          # level 40 -> 25
    http.push(200, DEVICE)
    http.push(204)
    http.push(200, PLAYING)
    first = music_reply(runtime, "turn the music down", "jin", "vol-key", allow_writes=True)
    calls = len(http.calls)
    retry = music_reply(runtime, "turn the music down", "jin", "vol-key", allow_writes=True)
    assert retry == first and len(http.calls) == calls                # no device read, no write, no "different command" refusal


def test_installing_a_different_client_rebuilds_the_controller_so_the_old_client_is_never_paired_with_the_new_token(tmp_path):
    http = FakeHttp()
    runtime = make_runtime(tmp_path, http)
    first = runtime._build()
    assert first is not None and runtime._built_for == "synthetic0client0id"
    (runtime.directory / "client.json").write_text(json.dumps({"client_id": "anotherclientid0001"}))
    second = runtime._build()
    assert second is not first and runtime._built_for == "anotherclientid0001"
    assert runtime._build() is second                                # stable until the credentials change again
