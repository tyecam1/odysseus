import copy

from src.estate_worker_protocol import (
    ERROR_CODES,
    PROTOCOL,
    VERBS,
    build_request,
    error_response,
    validate_request,
    validate_response,
)


EXPECTED_ERROR_CODES = {
    "unsupported_protocol", "unknown_verb", "bad_request",
    "identity_unregistered", "identity_mismatch", "executor_unavailable",
    "model_absent", "context_limit", "repo_unavailable", "authority_denied",
    "timeout", "execution_failed", "not_found", "worker_protocol_error",
    "worker_unreachable", "placement_mismatch",
}


def _attestation(request):
    return {
        "host_id": "test-lab",
        "hostname": "THIS-HOST",
        "machine_fingerprint": "0123456789abcdef",
        "os": "linux",
        "worker_pid": 123,
        "worker_version": "abc123",
        "nonce": request["nonce"],
        "observed_at": "2026-09-22T12:00:00Z",
    }


def test_build_request_and_request_validation():
    request = build_request("health", "test-lab", {}, 10)
    assert set(request) == {
        "protocol", "request_id", "verb", "expected_host_id", "nonce",
        "deadline_s", "payload",
    }
    assert request["protocol"] == PROTOCOL
    assert len(request["nonce"]) == 32
    assert validate_request(request) == (True, None)


def test_unknown_verb_and_bad_protocol_are_distinct():
    request = build_request("health", "test-lab", {}, 10)
    request["verb"] = "not-a-verb"
    assert validate_request(request)[1]["code"] == "unknown_verb"

    request = build_request("health", "test-lab", {}, 10)
    request["protocol"] = "aoteru-worker/999"
    assert validate_request(request)[1]["code"] == "unsupported_protocol"


def test_response_validation_and_echo_checks():
    request = build_request("health", "test-lab", {}, 10)
    response = {
        "protocol": PROTOCOL,
        "request_id": request["request_id"],
        "ok": True,
        "error": None,
        "attestation": _attestation(request),
        "result": {},
    }
    assert validate_response(response, request) == (True, None)

    # A well-formed but *wrong* nonce is an attestation/replay-correlation
    # concern (estate_worker_client.verify_attestation's job -> a
    # placement_mismatch), not a malformed envelope -- validate_response
    # only checks the nonce is a non-empty string (Stage 3 contract fix:
    # this used to be an equality check here, which meant
    # verify_attestation never even ran for a real mismatch).
    wrong_nonce = copy.deepcopy(response)
    wrong_nonce["attestation"]["nonce"] = "0" * 32
    assert validate_response(wrong_nonce, request) == (True, None)

    malformed_nonce = copy.deepcopy(response)
    malformed_nonce["attestation"]["nonce"] = ""
    assert validate_response(malformed_nonce, request)[1]["code"] == "worker_protocol_error"


def test_error_response_validates_and_error_codes_are_closed():
    assert set(ERROR_CODES) == EXPECTED_ERROR_CODES
    assert set(VERBS) == {
        "health", "inventory", "repo.probe", "execute", "worktree.prepare",
        "worktree.verify", "start", "status", "cancel", "worktree.finalize",
    }
    request = build_request("health", "test-lab", {}, 10)
    response = error_response(request, "bad_request", "bad", _attestation(request))
    assert validate_response(response, request) == (True, None)

    invalid = copy.deepcopy(response)
    invalid["error"]["code"] = "new_unversioned_code"
    assert validate_response(invalid, request)[1]["code"] == "worker_protocol_error"

