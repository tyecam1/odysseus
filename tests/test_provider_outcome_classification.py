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


# --- Codex deadline after a verified model response is an attempt, not a transport verdict (option D) -------------
MODEL = "gpt-6.2-sol"
PROMPT = "Read-only reconnaissance of the card; quote nothing.\ncodex\nexec\n"


def codex_transcript(model=MODEL, *, marker="codex", prompt=PROMPT, tail=""):
    return (f"OpenAI Codex v0.172.0\n--------\nworkdir: /w\nmodel: {model}\nprovider: openai\n"
            f"session id: 01a1face\n--------\nuser\n{prompt}\n{marker}\nI read the file.\n{tail}")


def verified(stderr, *, stdout="", model=MODEL, objective=PROMPT):
    return estate_router._codex_model_response_verified(stdout, stderr, model=model, objective=objective)


def test_a_banner_model_line_and_model_turn_verify_a_response():
    assert verified(codex_transcript()) is True
    assert verified(codex_transcript("gpt-6.2-sol").encode()) is True      # TimeoutExpired carries bytes
    assert verified(codex_transcript(marker="exec")) is True


@pytest.mark.parametrize("stderr,why", [
    (codex_transcript("gpt-6.1-sol"), "a different model than the one requested"),
    ("OpenAI Codex v0.172.0\n--------\nmodel: gpt-6.2-sol\nsession id: 01a1face\n--------\n", "a banner alone is a launch"),
    (codex_transcript(marker="nothing"), "no model turn"),
    (codex_transcript(tail="ERROR: stream disconnected\n"), "a CLI error line"),
    ("model: gpt-6.2-sol\nsession id: 01a1face\ncodex\n", "no CLI banner"),
    ("", "no output"),
])
def test_incomplete_or_contradicted_evidence_does_not_verify(stderr, why):
    assert verified(stderr) is False, why


def test_an_unremovable_prompt_echo_fails_closed():
    assert verified(codex_transcript(prompt="a reworded echo\ncodex")) is False


def test_a_prompt_that_is_itself_a_turn_word_cannot_erase_the_real_turn_marker():
    assert verified(codex_transcript(prompt="codex"), objective="codex") is True
    no_turn = ("OpenAI Codex v0.172.0\n--------\nmodel: gpt-6.2-sol\nsession id: 01a1face\n--------\nuser\ncodex\n")
    assert verified(no_turn, objective="codex") is False


def test_a_real_error_line_vetoes_even_when_the_prompt_quotes_the_same_line():
    prompt = "Explain this log:\nERROR: stream disconnected\n"
    assert verified(codex_transcript(prompt=prompt, tail="ERROR: stream disconnected\n"), objective=prompt) is False
    assert verified(codex_transcript(prompt=prompt), objective=prompt) is True


def test_piped_stdin_appended_to_the_echo_fails_closed():
    stdin_block = codex_transcript(tail="").replace(PROMPT + "\ncodex\nI read the file.\n",
                                                   PROMPT + "\n<stdin>\ncodex\n</stdin>\n")
    assert "<stdin>" in stdin_block and verified(stdin_block) is False


@pytest.mark.parametrize("line,vetoes", [
    ("ERROR: stream disconnected", True),
    ("2026-11-25T10:47:00Z  ERROR codex_core: request failed", True),
    ("FATAL: out of memory", True),
    ("\x1b[31mERROR\x1b[0m: stream disconnected", True),                       # coloured by the CLI
    ("[ERROR] stream disconnected before completion", True),
    ("ERROR : request failed", True),
    ("2026-11-25T10:47:00+01:00 ERROR codex_core: request failed", True),      # numeric timezone offset
    ("[2026-11-25T10:47:00Z] ERROR codex_core: request failed", True),
    ("2026-11-25T10:47:00.123456Z ERROR codex_core::client: stream error", True),
    ("error: something broke", False),                          # a tool's output (git, cargo...), not the CLI failing
    ("421:    error = parse(x)", False),                         # a `grep -n` line of source code Codex was reading
    ("12:def error(msg):", False),
    ("231:    ERROR_CODES = {}", False),
    ("ERROR = 'x'", False),
    ("    ERROR: indented tool output", False),
    ("    raise error", False),
    ("the error handler returns early", False),
    ("def error(msg):", False),
])
def test_only_cli_style_error_lines_veto(line, vetoes):
    assert (verified(codex_transcript(tail=line + "\n")) is False) is vetoes


def test_a_huge_digit_line_cannot_stall_verification():
    import time
    started = time.monotonic()
    assert verified(codex_transcript(tail="1" * 200000 + "\n")) is True
    assert verified(codex_transcript(tail=" " * 200000 + "x\n")) is True
    assert time.monotonic() - started < 1.0


def test_the_leader_check_never_reaps_the_process():
    import os
    import subprocess
    import time
    running = subprocess.Popen(["sleep", "30"])
    done = subprocess.Popen(["true"])
    try:
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and not estate_router._leader_exited(done):
            time.sleep(0.02)
        assert estate_router._leader_exited(running) is False
        assert estate_router._leader_exited(done) is True
        assert done.returncode is None                      # not reaped by the check ...
        assert os.waitpid(done.pid, os.WNOHANG)[0] == done.pid   # ... so its pid was still reserved until now
    finally:
        running.kill()
        running.wait()


def test_the_launcher_closes_stdin_for_the_paid_cli():
    import inspect
    assert "stdin=subprocess.DEVNULL" in inspect.getsource(estate_router._execute_codex_with_sandbox)


def test_the_echo_must_follow_the_banner_not_appear_anywhere_in_the_transcript():
    late = ("OpenAI Codex v0.172.0\n--------\nmodel: gpt-6.2-sol\nsession id: 01a1face\n--------\nuser\nsomething else\n"
            "codex\nanswer mentions: " + PROMPT)
    assert verified(late) is False


def test_stdout_before_the_transcript_does_not_disturb_the_banner_position():
    assert verified(codex_transcript(), stdout="final message\n") is True


def test_a_crlf_prompt_echo_is_removed_and_a_quoted_log_line_does_not_veto():
    prompt = "Re-adjudicate:\r\nERROR: the card quotes this log line\r\ncodex\r\n"
    assert verified(codex_transcript(prompt=prompt.replace("\r\n", "\n")), objective=prompt) is True
    answered_nothing = codex_transcript(prompt=prompt.replace("\r\n", "\n")).replace("codex\nI read the file.\n", "")
    assert verified(answered_nothing, objective=prompt) is False


def test_turn_words_in_the_echoed_prompt_cannot_fake_a_response():
    banner_only = ("OpenAI Codex v0.172.0\n--------\nmodel: gpt-6.2-sol\nsession id: 01a1face\n--------\nuser\n" + PROMPT)
    assert verified(banner_only) is False


def test_a_timeout_after_a_verified_response_is_an_attempt_that_changes_no_health():
    result = outcome(error="codex exec timed out after 180.0s", model_response_verified=True,
                     stderr_tail=codex_transcript())
    assert result["state"] == "unknown" and result["retry_after"] is None
    assert result["attempt_only"] is True and "attempt only" in result["reason"]


@pytest.mark.parametrize("fields", [
    {"error": "codex exec timed out after 180.0s"},                                   # no evidence
    {"error": "codex exec timed out after 180.0s", "model_response_verified": "yes"}, # not structurally True
    {"error": "codex exec timed out after 180.0s", "model_response_verified": 1},
    {"error": "codex exec timed out after 180.0s", "model_response_verified": False},
])
def test_a_timeout_without_structural_evidence_stays_unreachable(fields):
    result = outcome(**fields)
    assert result["state"] == "unreachable" and "attempt_only" not in result
    assert result["retry_after"] is not None


def test_the_evidence_flag_never_softens_a_real_failure():
    quota = outcome(error="codex exec exited 1: ERROR: usage limit reached, try again at 9:00 pm",
                    model_response_verified=True)
    assert quota["state"] == "quota_exhausted" and "attempt_only" not in quota
    exited = outcome(error="codex exec exited 2: connection reset", model_response_verified=True)
    assert exited["state"] == "unreachable" and "attempt_only" not in exited


def test_the_flag_is_codex_only():
    result = estate_router._provider_outcome({"ok": False, "provider": "glm", "error_code": "timeout",
                                              "error": "codex exec timed out after 180.0s",
                                              "model_response_verified": True})
    assert result["state"] == "unreachable" and "attempt_only" not in result
