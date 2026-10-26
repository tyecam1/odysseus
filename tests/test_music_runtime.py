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
    out = music_reply(runtime, "pause", "jin", "r1")
    assert out["status"] == "not_connected" and "isn't connected" in out["text"] and http.calls == []


def test_play_resolves_the_duplicate_release_and_reads_the_state_back(tmp_path):
    http = FakeHttp()
    runtime = make_runtime(tmp_path, http)
    row = {"name": "Arevil's Gardens (Rip)", "artists": [{"name": "The Land of Rah"}]}
    http.push(200, DEVICE)                  # the controller resolves the device first
    http.push(200, {"tracks": {"items": [dict(row, uri="spotify:track:aaa111"), dict(row, uri="spotify:track:bbb222")]}})   # the same release twice
    http.push(204)
    http.push(200, dict(PLAYING, item=dict(PLAYING["item"], uri="spotify:track:aaa111")))
    out = music_reply(runtime, "play Arevil's Gardens by The Land of Rah on Spotify", "jin", "r2")
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
    out = music_reply(runtime, "play blue", "jin", "r3")
    assert out["status"] == "clarify" and "Joni Mitchell" in out["text"] and "Eiffel 65" in out["text"] and "Say which one" in out["text"]
    assert {c[0] for c in http.calls} == {"GET"}                     # nothing was written


def test_relative_volume_reads_the_active_device_and_stays_bounded(tmp_path):
    http = FakeHttp()
    runtime = make_runtime(tmp_path, http)
    http.push(200, DEVICE)                  # my own read of the level (40)
    http.push(200, DEVICE)                  # the controller's device resolution
    http.push(204)
    http.push(200, PLAYING)
    out = music_reply(runtime, "turn it down", "jin", "r4")
    put = [c for c in http.calls if c[0] == "PUT"][0]
    assert dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(put[1]).query))["volume_percent"] == "25" and out["status"].startswith("done")


def test_what_is_playing_and_devices_are_read_only(tmp_path):
    http = FakeHttp()
    runtime = make_runtime(tmp_path, http)
    http.push(200, PLAYING)
    http.push(200, DEVICE)
    now = music_reply(runtime, "what's playing", "aoteru", "r5")
    devices = music_reply(runtime, "list my devices", "aoteru", "r6")
    assert "Song" in now["text"] and "Artist" in now["text"] and "Laptop (active)" in devices["text"]
    assert {c[0] for c in http.calls} == {"GET"}


def test_failures_become_honest_sentences(tmp_path):
    http = FakeHttp()
    runtime = make_runtime(tmp_path, http)
    http.push(200, DEVICE)
    http.push(429, {}, {"retry-after": "5"})
    out = music_reply(runtime, "pause", "jin", "r7")
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
