"""Wire contract for the stateless Aoteru estate worker."""
from __future__ import annotations

import re
import uuid
from typing import Any


PROTOCOL = "aoteru-worker/1"
VERBS = frozenset({
    "health",
    "inventory",
    "repo.probe",
    "execute",
    "worktree.prepare",
    "worktree.verify",
    "start",
    "status",
    "cancel",
    "worktree.finalize",
})
ERROR_CODES = frozenset({
    "unsupported_protocol",
    "unknown_verb",
    "bad_request",
    "identity_unregistered",
    "identity_mismatch",
    "executor_unavailable",
    "model_absent",
    "context_limit",
    "repo_unavailable",
    "authority_denied",
    "timeout",
    "execution_failed",
    "not_found",
    "worker_protocol_error",
    "worker_unreachable",
    "placement_mismatch",
})

_REQUEST_KEYS = {
    "protocol", "request_id", "verb", "expected_host_id", "nonce",
    "deadline_s", "payload",
}
_RESPONSE_KEYS = {
    "protocol", "request_id", "ok", "error", "attestation", "result",
}
_ATTESTATION_KEYS = {
    "host_id", "hostname", "machine_fingerprint", "os", "worker_pid",
    "worker_version", "nonce", "observed_at",
}
_HEX_32_RE = re.compile(r"^[0-9a-f]{32}$")
_HEX_16_RE = re.compile(r"^[0-9a-f]{16}$")


def _error(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def build_request(verb: str, expected_host_id: str, payload: dict, deadline_s: float) -> dict:
    """Build one request envelope with fresh replay-correlation values."""
    return {
        "protocol": PROTOCOL,
        "request_id": str(uuid.uuid4()),
        "verb": verb,
        "expected_host_id": expected_host_id,
        "nonce": uuid.uuid4().hex,
        "deadline_s": deadline_s,
        "payload": payload,
    }


def validate_request(obj: Any) -> tuple[bool, dict[str, str] | None]:
    """Validate the exact ``aoteru-worker/1`` request envelope."""
    if not isinstance(obj, dict):
        return False, _error("bad_request", "request must be a JSON object")
    if obj.get("protocol") != PROTOCOL:
        return False, _error("unsupported_protocol", f"protocol must be {PROTOCOL!r}")
    if set(obj) != _REQUEST_KEYS:
        return False, _error("bad_request", "request envelope fields do not match aoteru-worker/1")
    try:
        parsed_id = uuid.UUID(obj["request_id"])
    except (AttributeError, TypeError, ValueError):
        return False, _error("bad_request", "request_id must be a UUID")
    if parsed_id.version != 4:
        return False, _error("bad_request", "request_id must be a UUID4")
    verb = obj.get("verb")
    if not isinstance(verb, str):
        return False, _error("bad_request", "verb must be a string")
    if verb not in VERBS:
        return False, _error("unknown_verb", f"unknown worker verb {verb!r}")
    if not isinstance(obj.get("expected_host_id"), str) or not obj["expected_host_id"]:
        return False, _error("bad_request", "expected_host_id must be a non-empty string")
    if not isinstance(obj.get("nonce"), str) or not _HEX_32_RE.fullmatch(obj["nonce"]):
        return False, _error("bad_request", "nonce must be 32 lowercase hex characters")
    deadline_s = obj.get("deadline_s")
    if isinstance(deadline_s, bool) or not isinstance(deadline_s, (int, float)) or deadline_s <= 0:
        return False, _error("bad_request", "deadline_s must be a positive number")
    if not isinstance(obj.get("payload"), dict):
        return False, _error("bad_request", "payload must be an object")
    return True, None


def validate_response(obj: Any, request: dict) -> tuple[bool, dict[str, str] | None]:
    """Validate a response envelope and its echoes against ``request``."""
    if not isinstance(obj, dict):
        return False, _error("worker_protocol_error", "response must be a JSON object")
    if obj.get("protocol") != PROTOCOL:
        return False, _error("unsupported_protocol", f"response protocol must be {PROTOCOL!r}")
    if set(obj) != _RESPONSE_KEYS:
        return False, _error("worker_protocol_error", "response envelope fields do not match aoteru-worker/1")
    if obj.get("request_id") != request.get("request_id"):
        return False, _error("worker_protocol_error", "response request_id does not match request")
    if not isinstance(obj.get("ok"), bool):
        return False, _error("worker_protocol_error", "response ok must be boolean")
    error = obj.get("error")
    if obj["ok"]:
        if error is not None:
            return False, _error("worker_protocol_error", "successful response error must be null")
    else:
        if not isinstance(error, dict) or set(error) != {"code", "message"}:
            return False, _error("worker_protocol_error", "failed response must carry code and message")
        if error.get("code") not in ERROR_CODES or not isinstance(error.get("message"), str):
            return False, _error("worker_protocol_error", "response error is not in the closed error-code set")
    if not isinstance(obj.get("result"), dict):
        return False, _error("worker_protocol_error", "response result must be an object")

    attestation = obj.get("attestation")
    if not isinstance(attestation, dict) or set(attestation) != _ATTESTATION_KEYS:
        return False, _error("worker_protocol_error", "response attestation fields do not match aoteru-worker/1")
    host_id = attestation.get("host_id")
    if host_id is not None and (not isinstance(host_id, str) or not host_id):
        return False, _error("worker_protocol_error", "attestation host_id must be a string or null")
    if not isinstance(attestation.get("hostname"), str) or not attestation["hostname"]:
        return False, _error("worker_protocol_error", "attestation hostname must be a non-empty string")
    fingerprint = attestation.get("machine_fingerprint")
    if not isinstance(fingerprint, str) or not _HEX_16_RE.fullmatch(fingerprint):
        return False, _error("worker_protocol_error", "attestation machine_fingerprint must be 16 lowercase hex characters")
    if not isinstance(attestation.get("os"), str) or not attestation["os"]:
        return False, _error("worker_protocol_error", "attestation os must be a non-empty string")
    if isinstance(attestation.get("worker_pid"), bool) or not isinstance(attestation.get("worker_pid"), int) or attestation["worker_pid"] <= 0:
        return False, _error("worker_protocol_error", "attestation worker_pid must be a positive integer")
    if not isinstance(attestation.get("worker_version"), str) or not attestation["worker_version"]:
        return False, _error("worker_protocol_error", "attestation worker_version must be a non-empty string")
    if not isinstance(attestation.get("nonce"), str) or not _HEX_32_RE.fullmatch(attestation["nonce"]):
        # Shape only: the canonical wire shape (32 lowercase hex
        # characters, same `_HEX_32_RE` the request's own nonce is held
        # to in `validate_request`) is what makes this a malformed
        # envelope. Whether a well-formed nonce actually *matches* the
        # request's (the replay-correlation/identity question) is
        # estate_worker_client.verify_attestation()'s job, not this
        # envelope-shape validator's -- a well-shaped-but-wrong nonce is
        # an attestation/placement concern (`placement_mismatch`), not a
        # malformed envelope (Stage 3 review finding: the mismatch used
        # to be caught here first via an equality check, so
        # `call_worker()` never reached `verify_attestation()` for it and
        # misclassified it as `worker_protocol_error`; a later pass
        # correctly moved the equality check but over-relaxed this shape
        # check to "any non-empty string" in the process).
        return False, _error("worker_protocol_error", "attestation nonce must be 32 lowercase hex characters")
    if not isinstance(attestation.get("observed_at"), str) or not attestation["observed_at"]:
        return False, _error("worker_protocol_error", "attestation observed_at must be a non-empty string")
    return True, None


def error_response(request: dict, code: str, message: str, attestation: dict) -> dict:
    """Build a failed response while preserving the mandatory attestation."""
    if code not in ERROR_CODES:
        raise ValueError(f"unknown worker error code {code!r}")
    return {
        "protocol": PROTOCOL,
        "request_id": request.get("request_id"),
        "ok": False,
        "error": {"code": code, "message": message},
        "attestation": attestation,
        "result": {},
    }
