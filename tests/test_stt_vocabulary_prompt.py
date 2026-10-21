"""The STT vocabulary hint (stt_initial_prompt): passed to local Whisper and to OpenAI-compatible endpoints, empty by default."""

from services.stt import stt_service
from services.stt.stt_service import STTService, clean_stt_prompt

HINT = "Household voice assistant. Names: Aoteru, Misumi, Jin, Sanji, Misato."


class FakeSegment:
    text = " hello there "


class FakeInfo:
    language = "en"
    language_probability = 1.0


class CapturingWhisper:
    def __init__(self):
        self.calls = []

    def transcribe(self, path, **kwargs):
        self.calls.append(kwargs)
        return [FakeSegment()], FakeInfo()


def _service(settings):
    service = STTService()
    service._load_settings = lambda: {"stt_enabled": True, "stt_provider": "local", "stt_model": "small.en", "stt_language": "",
                                      "stt_initial_prompt": "", **settings}
    whisper = CapturingWhisper()
    service._get_whisper = lambda: whisper
    return service, whisper


def test_the_hint_reaches_local_whisper_and_stops_it_leaking_into_clipped_segments():
    service, whisper = _service({"stt_initial_prompt": HINT})
    assert service.transcribe(b"audio") == "hello there"
    assert whisper.calls[0]["initial_prompt"] == HINT and whisper.calls[0]["condition_on_previous_text"] is False


def test_without_a_hint_the_call_is_exactly_what_it_was_before():
    service, whisper = _service({})
    service.transcribe(b"audio")
    assert "initial_prompt" not in whisper.calls[0] and "condition_on_previous_text" not in whisper.calls[0]


def test_the_language_setting_still_applies_alongside_the_hint():
    service, whisper = _service({"stt_language": "en", "stt_initial_prompt": HINT})
    service.transcribe(b"audio")
    assert whisper.calls[0]["language"] == "en" and whisper.calls[0]["initial_prompt"] == HINT


def test_the_hint_is_cleaned_and_bounded():
    assert clean_stt_prompt("a\x00b\x1b[31m  c\n\nd") == "a b [31m c d"
    assert len(clean_stt_prompt("x" * 5000)) == 600
    for bad in (None, 5, [], {}, b"bytes"):
        assert clean_stt_prompt(bad) == ""


def test_the_hint_is_sent_as_prompt_to_an_openai_compatible_endpoint(monkeypatch):
    sent = {}

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"text": "ok"}

    def fake_post(url, headers=None, files=None, data=None, timeout=None):
        sent.update(url=url, data=data)
        return Response()

    class Endpoint:
        base_url = "http://stt.local/v1"
        api_key = ""

    class Query:
        def filter(self, *args):
            return self

        def first(self):
            return Endpoint()

    class Session:
        def query(self, *args):
            return Query()

        def close(self):
            pass

    import src.database as database

    monkeypatch.setattr(database, "SessionLocal", lambda: Session())
    monkeypatch.setattr(stt_service.httpx, "post", fake_post)
    service = STTService()
    assert service._transcribe_api(b"audio", "ep1", "whisper-1", "", HINT) == "ok"
    assert sent["data"]["prompt"] == HINT
    sent.clear()
    service._transcribe_api(b"audio", "ep1", "whisper-1", "", "")
    assert "prompt" not in sent["data"]


def test_the_setting_has_an_empty_default():
    from src.settings import DEFAULT_SETTINGS

    assert DEFAULT_SETTINGS["stt_initial_prompt"] == ""
