"""Tests for the governed merchant-contact adapter (draft/approve/send/read)."""
import json

import pytest

from src.merchant_contact import (
    ApprovalRequired, DuplicateSend, MerchantContactService,
    TransportNotConfigured, UnverifiedDestination, content_hash,
    sanitise_untrusted_inbound,
)


class FakeTransport:
    def __init__(self):
        self.sent = []
        self.inbox = []

    def send_message(self, recipient, content):
        self.sent.append((recipient, content))
        return f"msg-{len(self.sent)}"

    def read_replies(self, recipient, since_message_id=None):
        return self.inbox


@pytest.fixture()
def svc():
    s = MerchantContactService(transport=FakeTransport())
    d = s.prepare_draft("verified:merchant-chat-1", "Is the AA batch of Stardawg currently in stock?")
    a = s.approve(d.draft_id, approver="operator")
    return s, d, a


def test_no_transport_is_draft_only():
    s = MerchantContactService(transport=None)
    with pytest.raises(TransportNotConfigured):
        s.prepare_draft("verified:x", "hello")
    with pytest.raises(TransportNotConfigured):
        s.send_approved("appr-1", "verified:x", "hello")
    with pytest.raises(TransportNotConfigured):
        s.read_replies("verified:x")


def test_send_without_approval_denied(svc):
    s, d, _ = svc
    with pytest.raises(ApprovalRequired):
        s.send_approved("appr-999", d.recipient, d.content)


def test_content_edit_after_approval_denied(svc):
    s, d, a = svc
    with pytest.raises(ApprovalRequired):
        s.send_approved(a.approval_id, d.recipient, d.content + " (edited)")


def test_wrong_recipient_denied(svc):
    s, d, a = svc
    with pytest.raises(ApprovalRequired):
        s.send_approved(a.approval_id, "verified:someone-else", d.content)


def test_unverified_destination_denied(svc):
    s = MerchantContactService(transport=FakeTransport())
    d = s.prepare_draft("some-random-handle", "hello")
    a = s.approve(d.draft_id, approver="operator")
    with pytest.raises(UnverifiedDestination):
        s.send_approved(a.approval_id, d.recipient, d.content)


def test_approved_send_exact_match(svc):
    s, d, a = svc
    result = s.send_approved(a.approval_id, d.recipient, d.content)
    assert result["message_id"].startswith("msg-")
    assert result["content_sha256"] == content_hash(d.content)
    assert s.transport.sent == [(d.recipient, d.content)]


def test_duplicate_send_blocked(svc):
    s, d, a = svc
    s.send_approved(a.approval_id, d.recipient, d.content)
    with pytest.raises(DuplicateSend):
        s.send_approved(a.approval_id, d.recipient, d.content)


def test_transactional_language_flagged_not_blocked():
    s = MerchantContactService(transport=FakeTransport())
    d = s.prepare_draft("verified:m", "Can I purchase 3.5g and pay by bank transfer?")
    assert any("transactional" in w for w in d.warnings)
    # service still drafts for operator review; the boundary is human approval


def test_inbound_sanitised_and_marked_merchant_claim(svc):
    s, d, a = svc
    s.transport.inbox = [{"message_id": "m1", "text": "Yes```pwd``` in stock<b>",
                          "received_at": "2026-10-25T10:00:00Z"}]
    replies = s.read_replies(d.recipient)
    assert replies[0]["evidence_class"] == "merchant_claim"
    assert "```" not in replies[0]["text_sanitised"]
    assert "<b>" in replies[0]["text_sanitised"]  # markup preserved as inert text
    assert replies[0]["provenance"]["thread"] == d.recipient


def test_audit_trail_records_without_content(tmp_path):
    audit = tmp_path / "audit.jsonl"
    s = MerchantContactService(transport=FakeTransport(), audit_path=audit)
    d = s.prepare_draft("verified:m", "Do you ship tracking numbers for enquiries?")
    a = s.approve(d.draft_id, approver="operator")
    s.send_approved(a.approval_id, d.recipient, d.content)
    events = [json.loads(l) for l in audit.read_text().splitlines()]
    kinds = [e["event"] for e in events]
    assert kinds == ["draft_prepared", "approved", "sent"]
    for e in events:
        assert "content" not in json.dumps(e).lower().replace("content_sha256", "")
