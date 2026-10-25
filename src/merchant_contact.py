"""Governed merchant-contact drafting/approval over a Telegram MCP transport.

Domain-neutral adapter per the Odysseus task card: draft -> review ->
EXPLICIT per-recipient/per-content approval -> send -> read replies.
Non-transactional customer-service/product-information use only. Draft-only
when no transport is configured; never sends without a matching approval
record (exact recipient + exact content hash). No credentials live here: the
transport is injected and resolves secrets from the operator's environment.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

MAX_DRAFT_LENGTH = 4096  # Telegram message hard limit

FORBIDDEN_PATTERNS = (
    "buy ", "purchase ", "order ", "pay ", "payment", "bank transfer",
    "deliver to", "my address", "cash on delivery",
)


class TransportNotConfigured(RuntimeError):
    """No Telegram transport is connected. Draft-only mode."""


class ApprovalRequired(RuntimeError):
    """Send attempted without an exact matching operator approval."""


class DuplicateSend(RuntimeError):
    """The exact approved message was already sent (idempotency guard)."""


class UnverifiedDestination(RuntimeError):
    """Recipient has not been established as a verified merchant chat."""


@dataclass
class Approval:
    approval_id: str
    recipient: str
    content_sha256: str
    created_at: str
    used: bool = False


@dataclass
class Draft:
    draft_id: str
    recipient: str
    content: str
    content_sha256: str
    warnings: List[str] = field(default_factory=list)


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sanitise_untrusted_inbound(raw: str) -> str:
    """Merchant replies are untrusted merchant_claim data: neutralise control
    characters and markup-looking sequences before storage/display."""
    cleaned = "".join(ch for ch in (raw or "") if ch >= " " or ch in "\t\n")
    cleaned = cleaned.replace("```", "'''")
    return cleaned


class MerchantContactService:
    """Transport-agnostic service. `transport` must expose
    send_message(recipient, content) -> message_id and
    read_replies(recipient, since_message_id) -> list[dict];
    raise TransportNotConfigured when unconnected."""

    def __init__(self, transport=None, audit_path: Optional[Path] = None):
        self.transport = transport
        self.audit_path = Path(audit_path) if audit_path else None
        self.approvals: Dict[str, Approval] = {}
        self.sent_keys: set = set()
        self.drafts: Dict[str, Draft] = {}
        self._seq = 0

    # -- audit ------------------------------------------------------------
    def _audit(self, event: Dict[str, Any]) -> None:
        event = {"at": datetime.now(timezone.utc).isoformat(), **event}
        if self.audit_path is None:
            return
        self.audit_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
        fd = os.open(self.audit_path, flags, stat.S_IRUSR | stat.S_IWUSR)
        try:
            os.write(fd, (json.dumps(event, sort_keys=True) + "\n").encode())
        finally:
            os.close(fd)

    # -- draft ------------------------------------------------------------
    def prepare_draft(self, recipient: str, content: str) -> Draft:
        if self.transport is None:
            raise TransportNotConfigured(
                "no Telegram transport connected: draft-only mode requires "
                "an operator-configured transport with an established chat")
        content = content.strip()
        if not content:
            raise ValueError("empty draft")
        if len(content) > MAX_DRAFT_LENGTH:
            raise ValueError(f"draft exceeds Telegram limit ({MAX_DRAFT_LENGTH})")
        warnings = []
        low = content.lower()
        for pat in FORBIDDEN_PATTERNS:
            if pat in low:
                warnings.append(f"transactional-language risk: contains {pat!r}")
        self._seq += 1
        draft = Draft(draft_id=f"draft-{self._seq}", recipient=recipient,
                      content=content, content_sha256=content_hash(content),
                      warnings=warnings)
        self.drafts[draft.draft_id] = draft
        self._audit({"event": "draft_prepared", "draft_id": draft.draft_id,
                     "recipient": recipient, "content_sha256": draft.content_sha256})
        return draft

    # -- approve ----------------------------------------------------------
    def approve(self, draft_id: str, approver: str) -> Approval:
        d = self.drafts.get(draft_id)
        if d is None:
            raise KeyError(draft_id)
        self._seq += 1
        approval = Approval(approval_id=f"appr-{self._seq}",
                            recipient=d.recipient,
                            content_sha256=d.content_sha256,
                            created_at=datetime.now(timezone.utc).isoformat())
        self.approvals[approval.approval_id] = approval
        self._audit({"event": "approved", "approval_id": approval.approval_id,
                     "draft_id": draft_id, "recipient": d.recipient,
                     "content_sha256": d.content_sha256, "approver": approver})
        return approval

    # -- send -------------------------------------------------------------
    def send_approved(self, approval_id: str, recipient: str, content: str) -> Dict[str, Any]:
        if self.transport is None:
            raise TransportNotConfigured("no transport connected; cannot send")
        approval = self.approvals.get(approval_id)
        if approval is None:
            raise ApprovalRequired(
                "send requires an operator approval matching the exact "
                "recipient and exact content")
        key = (recipient, approval.content_sha256)
        if key in self.sent_keys or (approval.used and key in self.sent_keys):
            raise DuplicateSend("this exact approved message was already sent")
        if approval.used:
            raise ApprovalRequired("approval already used")
        if approval.recipient != recipient or approval.content_sha256 != content_hash(content):
            raise ApprovalRequired(
                "approval does not match this recipient/content: edit content "
                "or recipient and re-approve")
        if not recipient.startswith("verified:"):
            raise UnverifiedDestination(
                "recipient is not a verified established merchant chat "
                "(bot API cannot initiate arbitrary DMs)")
        message_id = self.transport.send_message(recipient, content)
        approval.used = True
        self.sent_keys.add(key)
        self._audit({"event": "sent", "approval_id": approval_id,
                     "recipient": recipient, "content_sha256": approval.content_sha256,
                     "message_id": message_id})
        return {"message_id": message_id, "recipient": recipient,
                "content_sha256": approval.content_sha256}

    # -- read -------------------------------------------------------------
    def read_replies(self, recipient: str, since_message_id: Optional[str] = None
                     ) -> List[Dict[str, Any]]:
        if self.transport is None:
            raise TransportNotConfigured("no transport connected")
        replies = self.transport.read_replies(recipient, since_message_id) or []
        out = []
        for m in replies:
            out.append({
                "transport_message_id": m.get("message_id"),
                "recipient": recipient,
                "text_sanitised": sanitise_untrusted_inbound(m.get("text", "")),
                "received_at": m.get("received_at"),
                "evidence_class": "merchant_claim",  # unverified until reconciled
                "provenance": {"transport": type(self.transport).__name__,
                               "thread": recipient},
            })
        self._audit({"event": "replies_read", "recipient": recipient,
                     "count": len(out)})
        return out
