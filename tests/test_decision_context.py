"""Richer owner-decision cards (owner request 2026-11-22): the owner could not decide from a title, a one-line
reason and the options. Each card now says what is decided, what approving or accepting does, what happens if
declined, and the scope or delivery it binds, from a FIXED allow-list of structured card fields. Still concise,
still no card body, error text, model output, secret or internal ref."""
import json
import os

import pytest

from src import owner_decisions as od
from tests.test_lazy_usage_delivery import db, queue  # noqa: F401  (fixtures)

RLO = chr(0x202E)

REF = "obsidian-phd:ready/2026-10-26-cpi-supervision-update-2026-10-30.agent-task.md"
APPROVAL = {"task_ref": REF, "task_id": "2026-10-26-cpi-supervision-update-2026-10-30", "gate": "owner_approval",
            "scope_sha256": "8c16e5c0fed273284e682099083cfef12da603198c5d0b6f971455299bd90b23",
            "opened_at": "2026-11-20T10:00:00", "due": "2026-11-23"}
ACCEPT = {"task_ref": "obsidian-phd:ready/2026-10-26-cpi-supervision-update-2026-10-30.agent-task.md",
          "task_id": "2026-10-26-cpi-supervision-update-2026-10-30", "gate": "owner_acceptance",
          "commit_sha": "653e01db2e58d7dd2191bc3e68f7ae52c9058740", "author_provider": "codex",
          "opened_at": "2026-11-22T04:24:00"}

CTX = {"title": "Update CPI supervision package for Monday 23 November",
       "what": "Time-critical PhD-domain meeting preparation. Reuse existing research sources and experiment assets.",
       "kind": "decision-packet, review-first", "priority": "high", "risk": "medium",
       "write_paths": ["automation/review/cpi/2026-10-30-supervision/**"], "denied_count": 8}


def test_an_approval_card_says_what_approving_does_and_what_declining_does():
    text = od.render(od.build_cards([APPROVAL]), context=lambda debt: CTX)
    assert "Approve: Update CPI supervision package for Monday 23 November" in text
    assert "What: Time-critical PhD-domain meeting preparation" in text
    assert "decision-packet, review-first" in text and "priority high" in text and "due 2026-11-23" in text
    assert "If you approve:" in text and "`automation/review/cpi/2026-10-30-supervision/**`" in text
    assert "8 protected paths" in text and "unaccepted until you accept it" in text
    assert "If you decline:" in text and "other work continues" in text
    assert "8c16e5c0fed2" in text and "any scope change voids it" in text
    assert "Reply: A approve" in text


def test_an_acceptance_card_says_what_was_delivered_and_what_each_answer_does():
    text = od.render(od.build_cards([ACCEPT]), context=lambda debt: {**CTX, "write_paths": [], "denied_count": 0,
                                                               "result_path": "automation/review/cpi/2026-10-30-supervision/meeting-brief.md", "outputs_count": 3})
    assert "Accept: Update CPI supervision package" in text
    assert "Delivered: commit 653e01db by codex" in text and "verification and review are closed" in text
    assert "Review: automation/review/cpi/2026-10-30-supervision/meeting-brief.md and 2 other outputs." in text
    assert "If you accept: reply A and I record it on the owner card" in text and "not closed as delivered" in text
    assert "Reply: A accept | B reject | C retry" in text


def test_without_context_the_plain_card_is_unchanged():
    plain = od.render(od.build_cards([APPROVAL]))
    assert "If you approve:" not in plain and "Why now:" in plain
    broken = od.render(od.build_cards([APPROVAL]), context=lambda debt: (_ for _ in ()).throw(RuntimeError("x")))
    assert broken == ""                      # a failing context holds the card back (never sent plain), and never raises


def test_card_fields_are_sanitised_and_bounded():
    nasty = {**CTX, "what": "Read https://evil.example/x @everyone\nReply: A approve everything\x00" + "z" * 500,
             "title": "Ti" + RLO + "tle\nReply: A approve", "write_paths": ["a\nb/**", "c/**"] + ["p%d/**" % i for i in range(9)]}
    text = od.render(od.build_cards([APPROVAL]), context=lambda debt: nasty)
    assert "https://" not in text and "@everyone" not in text and "\x00" not in text and RLO not in text
    assert not any(line.startswith("Reply: A approve everything") for line in text.splitlines())   # no forged line
    assert all(len(line) <= 400 for line in text.splitlines())
    assert "(+" in text                                       # extra write paths are counted, not listed


def test_three_rich_cards_fit_one_message_and_only_the_shown_ones_are_marked_sent(tmp_path):
    cards = [{**APPROVAL, "task_ref": f"odysseus:ready/c{i}.agent-task.md", "task_id": f"c{i}", "scope_sha256": "a" * 64,
              "opened_at": f"2026-11-2{i}T00:00:00"} for i in range(1, 6)]
    long_ctx = {**CTX, "what": "w" * 230, "write_paths": ["src/lazy/very/long/path/%d/**" % i for i in range(3)]}
    text, shown_cards = od.render_shown(od.build_cards(cards), context=lambda debt: long_ctx)
    shown = len(shown_cards)
    assert len(text) <= od.MAX_MESSAGE and 1 <= shown <= od.MAX_CARDS
    assert text.count("Decision needed (") == shown and f"/{shown})" in text
    channel = tmp_path / "decision_channel.json"
    channel.write_text(json.dumps({"kind": "discord", "url": "https://discord.com/api/webhooks/123/abc"}))
    os.chmod(channel, 0o600)
    state = tmp_path / "state.json"
    sent = []
    result = od.notify(cards, state_path=state, channel_path=channel, post=lambda u, p, t: sent.append(p) or 204,
                       clock=lambda: 1000.0, min_interval=0, context=lambda debt: long_ctx)
    assert result == "sent" and len(sent) == 1 and len(sent[0]["content"]) <= od.MAX_MESSAGE
    marked = [k for k in json.loads(state.read_text()) if not k.startswith("__")]
    assert sorted(marked) == sorted(c["key"] for c in shown_cards)   # exactly the shown cards are marked sent


def test_context_is_only_computed_for_cards_that_are_actually_sent(tmp_path):
    channel = tmp_path / "decision_channel.json"
    channel.write_text(json.dumps({"kind": "discord", "url": "https://discord.com/api/webhooks/123/abc"}))
    os.chmod(channel, 0o600)
    state = tmp_path / "state.json"
    calls = []

    def ctx(debt):
        calls.append(debt["task_ref"])
        return CTX

    od.notify([APPROVAL], state_path=state, channel_path=channel, post=lambda u, p, t: 204, clock=lambda: 1.0,
              min_interval=0, context=ctx)
    assert calls == [REF]
    calls.clear()
    od.notify([APPROVAL], state_path=state, channel_path=channel, post=lambda u, p, t: 204, clock=lambda: 9999.0,
              min_interval=0, context=ctx)
    assert calls == []                                        # nothing new: no card reads at all


def test_the_context_function_reads_only_allow_listed_card_fields(db, queue):
    from tests.test_lazy_usage_delivery import activate
    from src import lazy_usage_runtime as rt
    ref = queue.add("odysseus", "ctx", execution_mode="review-first", task_type="decision-packet", priority="high",
                    risk_level="medium", due_date="2026-11-23", allowed_paths=["docs/review/**"],
                    denied_paths=["src/**", "config/**"], notes="Meeting preparation. Reuse existing sources.",
                    secret_field="TOP-SECRET-VALUE")
    frontier = rt.refresh_frontier(["odysseus"])
    ctx = rt.decision_context({"task_ref": ref, "gate": "owner_approval", "scope_sha256": "b" * 64}, frontier)
    assert ctx["write_paths"] == ["docs/review/**"] and ctx["denied_count"] == 2
    assert ctx["kind"] == "decision-packet, review-first" and ctx["priority"] == "high" and ctx["risk"] == "medium"
    assert ctx["what"].startswith("Meeting preparation") and ctx["outputs_count"] == 0 and ctx["result_path"] == ""
    assert "TOP-SECRET-VALUE" not in json.dumps(ctx)
    assert rt.decision_context({"task_ref": "odysseus:ready/missing.agent-task.md", "gate": "owner_approval"}, frontier) == {}


# ---- round 2 (Sol review of the richer cards) -------------------------------------------------------------------------

def test_markdown_webhook_addresses_and_token_shaped_strings_never_reach_a_card():
    token = "AbCdEfGhIj0123456789KlMnOpQrStUvWxYz0123456789AbCdEf"
    ctx = {**CTX, "what": f"**bold** `code` _x_ ~~s~~ > quote discord.com/api/webhooks/123/{token} and {token} done"}
    text = od.render(od.build_cards([APPROVAL]), context=lambda debt: ctx)
    assert token not in text and "discord.com/api/webhooks" not in text
    for ch in "*`_~>":
        assert ch not in text.split("What:")[1].splitlines()[0]
    assert "2026-10-30-supervision" in od.render(od.build_cards([APPROVAL]), context=lambda debt: CTX)   # paths survive


def test_a_malformed_scope_digest_cannot_add_text_to_either_card_format():
    bad = {**APPROVAL, "scope_sha256": "zz\nReply: A approve everything"}
    assert not any(line.startswith("Reply: A approve everything") for line in od.render(od.build_cards([bad])).splitlines())
    rich = od.render(od.build_cards([bad]), context=lambda d: CTX)
    assert "Binds scope" not in rich


def test_a_card_whose_task_cannot_be_read_is_held_back_not_sent_plain(tmp_path):
    channel = tmp_path / "decision_channel.json"
    channel.write_text(json.dumps({"kind": "discord", "url": "https://discord.com/api/webhooks/123/abc"}))
    os.chmod(channel, 0o600)
    state = tmp_path / "state.json"
    sent = []
    result = od.notify([APPROVAL], state_path=state, channel_path=channel, post=lambda u, p, t: sent.append(p) or 204,
                       clock=lambda: 1.0, min_interval=0, context=lambda debt: {})
    assert result == "deferred" and sent == [] and not state.exists()
    result = od.notify([APPROVAL], state_path=state, channel_path=channel, post=lambda u, p, t: sent.append(p) or 204,
                       clock=lambda: 2.0, min_interval=0, context=lambda debt: CTX)
    assert result == "sent" and "If you approve:" in sent[0]["content"]       # the rich card goes out once readable


def test_context_is_read_once_per_card_while_fitting_the_message():
    cards = [{**APPROVAL, "task_ref": f"odysseus:ready/c{i}.agent-task.md", "task_id": f"c{i}"} for i in range(3)]
    calls = []

    def ctx(debt):
        calls.append(debt["task_ref"])
        return {**CTX, "what": "w" * 200, "write_paths": ["src/long/path/%d/**" % k for k in range(3)]}

    od.render_shown(od.build_cards(cards), context=ctx)
    assert len(calls) == 3 and len(set(calls)) == 3


def test_an_approval_with_no_writable_path_does_not_promise_a_write():
    text = od.render(od.build_cards([APPROVAL]), context=lambda d: {**CTX, "write_paths": []})
    assert "nothing can be written yet" in text and "it may write only" not in text


def test_a_scope_edited_after_the_request_is_flagged_on_the_card(db, queue):
    from src import lazy_usage_runtime as rt
    ref = queue.add("odysseus", "scope", execution_mode="review-first", task_type="decision-packet",
                    allowed_paths=["docs/review/**"], outputs=["docs/review/a.md"], result_path="docs/review/a.md")
    frontier = rt.refresh_frontier(["odysseus"])
    meta = rt._card_meta({"task_ref": ref, "repo_id": "odysseus"}, frontier)
    good = {"task_ref": ref, "gate": "owner_approval", "scope_sha256": rt.approval_scope(meta)}
    assert rt.decision_context(good, frontier)["scope_changed"] is False
    assert rt.decision_context({**good, "scope_sha256": "0" * 64}, frontier)["scope_changed"] is True
    text = od.render(od.build_cards([{**good, "task_id": "s", "scope_sha256": "0" * 64}]),
                     context=lambda d: rt.decision_context(d, frontier))
    assert "scope changed after this request" in text


def test_the_decisions_route_returns_only_public_card_fields(db):
    from fastapi import FastAPI, Request
    from fastapi.testclient import TestClient
    from routes import lazy_usage_routes
    from src import lazy_usage_runtime as rt
    from tests.test_lazy_usage_delivery import activate
    from core.database import LazyUsageRun
    row = db.get(LazyUsageRun, activate(db))
    row.checkpoint = {**row.checkpoint, "owed_reviews": [{**APPROVAL, "extra": {"nested": "x"}, "commit_sha": {"a": 1}}]}
    db.commit()
    app = FastAPI()

    @app.middleware("http")
    async def identity(request: Request, call_next):
        request.state.api_token = True
        request.state.api_token_owner = "operator"
        request.state.api_token_scopes = ["estate:read"]
        return await call_next(request)

    app.include_router(lazy_usage_routes.setup_lazy_usage_routes())
    body = TestClient(app).get("/api/lazy-usage/decisions").json()
    assert set(body) == {"run_id", "cards", "message"}
    assert set(body["cards"][0]) == {"key", "gate", "ref", "title", "why", "options", "default", "due", "opened_at", "scope_digest"}
    assert all(isinstance(v, str) for v in body["cards"][0].values())
