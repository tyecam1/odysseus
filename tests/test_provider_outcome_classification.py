"""A failed call's state must come from its error and stderr, not from the model's own transcript.

Live 2026-11-21: a Codex reconnaissance that merely timed out (180 s) while READING code about authentication
left a partial transcript containing the word "authentication"; the classifier matched it before "timed out" and
recorded `auth_failed`, gating Codex and skipping the next card as provider_unavailable although Codex was logged in."""
import pytest

from src import estate_router

SESSION = "OpenAI Codex v0.171.0\n--------\nsession id: 01a1face\n--------\n"
TRANSCRIPT = (SESSION + "I am reading the authentication module. The 401 handler returns 'unauthorized'. "
              "There is also a usage limit check and a rate limit decorator, and a connection pool.")


def outcome(**fields):
    return estate_router._provider_outcome({"ok": False, "provider": "codex", **fields})


def test_a_timeout_whose_transcript_mentions_authentication_is_a_timeout_not_an_auth_failure():
    result = outcome(error="codex exec timed out after 180.0s", output=TRANSCRIPT, stdout=TRANSCRIPT)
    assert result["state"] == "unreachable" and result["state"] != "auth_failed"


@pytest.mark.parametrize("field", ["output", "stdout"])
def test_words_in_the_model_transcript_never_create_a_quota_or_auth_state(field):
    result = outcome(error="codex exec exited 2", **{field: TRANSCRIPT})
    assert result["state"] not in {"auth_failed", "quota_exhausted", "rate_limited"}


def test_a_real_usage_limit_in_the_error_text_is_still_detected():
    result = outcome(error="codex exec exited 1: ERROR: You've hit your usage limit. try again at Nov 20th, 2026 9:08 PM.",
                     output=TRANSCRIPT)
    assert result["state"] == "quota_exhausted"


def test_a_real_auth_failure_in_stderr_is_still_detected():
    result = outcome(error="codex exec exited 1", stderr="ERROR: 401 Unauthorized: not logged in", output="")
    assert result["state"] == "auth_failed"


def test_with_no_error_text_the_transcript_is_the_fallback_evidence():
    """Existing behaviour for results that carry their only evidence in stdout/output."""
    result = outcome(stdout="ERROR: You've hit your usage limit.")
    assert result["state"] == "quota_exhausted"


# ---- GLM-5.3 review: prose reaches the classifier through the composed `error` field too ------------------------

COMPOSED_PROSE = ("codex exec exited 2: " + SESSION + "I read the authentication module; its 401 unauthorized handler and the usage limit "
                  "check look fine.\nstderr: reading files, a connection pool and a rate limit decorator")


def test_prose_inside_the_composed_error_text_cannot_fake_a_state():
    """execute_codex builds error = 'codex exec exited N: <stdout tail>\\n<stderr tail>'."""
    result = outcome(error=COMPOSED_PROSE)
    assert result["state"] not in {"auth_failed", "quota_exhausted", "rate_limited"}


def test_a_genuine_cli_usage_limit_line_inside_the_composed_error_is_still_detected():
    error = COMPOSED_PROSE + "\nERROR: You've hit your usage limit. try again at Nov 20th, 2026 9:08 PM."
    assert outcome(error=error)["state"] == "quota_exhausted"


def test_a_timestamped_cli_error_line_is_still_detected():
    error = "codex exec exited 1: \nsome prose\n2026-11-21T20:17:28.349979Z ERROR: You've hit your usage limit."
    assert outcome(error=error)["state"] == "quota_exhausted"


def test_the_header_of_the_error_still_classifies_a_timeout():
    assert outcome(error="codex exec timed out after 180.0s\n" + COMPOSED_PROSE)["state"] == "unreachable"
