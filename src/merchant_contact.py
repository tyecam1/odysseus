"""Merchant enquiry drafts and inspection of untrusted inbound messages.

Outbound capability is DISABLED for every transport. This module has no
integration with the existing governed approval/tool boundary, and caller
strings (including a ``verified:`` prefix) establish no authority or chat
identity. It must not mint approvals or attempt delivery. A future integration
must use the existing authority, not add an approval registry here.
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


class OutboundDisabled(RuntimeError):
    """No governed outbound integration exists; no transport may send."""


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
    """Drafts need no transport. An optional injected inbound adapter exposes
    read_replies(recipient, since_message_id) -> list[dict]. No connection is
    established here and its outbound methods are never called."""

    outbound_enabled = False
    outbound_blocker = "DISABLED: existing governed approval/tool integration is absent"

    def __init__(self, transport=None, audit_path: Optional[Path] = None):
        self.transport = transport
        self.audit_path = Path(audit_path) if audit_path else None
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

    def review(self, draft_id: str) -> Draft:
        """Inspect a prepared draft, without granting send authority."""
        return self.drafts[draft_id]

    def approve(self, draft_id: str, approver: str) -> None:
        """Compatibility entry point: standalone callers cannot mint authority."""
        raise OutboundDisabled(self.outbound_blocker)

    # -- send -------------------------------------------------------------
    def send_approved(self, approval_id: str, recipient: str, content: str) -> Dict[str, Any]:
        """Fail closed regardless of transport, caller strings, retry or restart."""
        raise OutboundDisabled(self.outbound_blocker)

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
