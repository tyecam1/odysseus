"""The phone inbox: short packages, rationed interrupts, and replies in plain words where only a plain-word yes, matched by
code after the echo really reached the phone, can approve anything.

Nothing here touches the network or a model: transport, author, parser and the actions are fakes."""
import json
import os
import stat
from datetime import datetime, timezone

import pytest

from src import owner_inbox as ib

NOON = datetime(2026, 11, 26, 12, 0, tzinfo=timezone.utc).timestamp()          # GMT in November: London == UTC
T0 = datetime(2026, 11, 26, 9, 0, tzinfo=timezone.utc).timestamp()
FP = "f" * 64


@pytest.fixture
def home(tmp_path):
    d = tmp_path / "home"
    d.mkdir(mode=0o700)
    d.chmod(0o700)
    return d


def write_channel(home, **over):
    data = {"kind": "ntfy", "base_url": "http://100.75.149.126:8091", "topic": "alerts-topic-1234",
            "user": "odysseus", "password": "pw", "owner": "operator", "reply_topic": "reply-topic-1234", **over}
    path = home / "ntfy_channel.json"
    path.write_text(json.dumps(data))
    path.chmod(0o600)
    return path


class Phone:
    """A fake phone: records what is sent and serves what the owner 'typed' (honouring `since`, like ntfy)."""

    def __init__(self):
        self.sent, self.inbox, self.fail_sends, self.refuse_sends = [], [], 0, 0
        self.posted = 0
        self.refuse_code = 403

    def send(self, channel, title, body, priority, *a, **k):
        if self.refuse_sends:
            self.refuse_sends -= 1
            if isinstance(channel.get("_refused"), list):
                channel["_refused"].append(self.refuse_code)
            return False                      # the server answered and refused
        if self.fail_sends:
            self.fail_sends -= 1
            raise OSError("timed out")        # outcome unknown
        self.sent.append({"title": title, "body": body, "priority": priority, "url": channel["url"]})
        if isinstance(channel.get("_published"), list):
            channel["_published"].append(f"pub{self.posted}")                   # the broker's id for the post (never reused)
        self.posted += 1
        return True

    def fetch(self, channel, since):
        if since == "all":
            return list(self.inbox)
        ids = [m["id"] for m in self.inbox]
        return list(self.inbox[ids.index(since) + 1:]) if since in ids else list(self.inbox)

    def say(self, text, at, mid=None, **extra):
        self.inbox.append({"id": mid or f"m{len(self.inbox)}", "time": at, "text": text, **extra})


def cand(**over):
    base = {"kind": "approval", "task_ref": "odysseus:ready/glove.md", "task_id": "glove", "scope": "a" * 64, "fp": FP,
            "priority": "high", "opened_at": "2026-11-20", "title": "Glovebox shortlist", "card_line": "Glovebox shortlist, medium risk",
            "context": {"risk": "medium"}}              # readable facts and no decision class: not a protected request
    return {**base, **over}


def fields(**over):
    return {"what": "Agents compare glovebox suppliers and write a draft shortlist for you to read.",
            "if_yes": "A draft shortlist is written in the review area; nothing is ordered or sent to anyone.",
            "if_no": "The task stays parked and nothing changes.", "advice": "yes",
            "advice_reason": "It only produces a draft and spends nothing.",
            "detail": "Agents compare glovebox options and write a draft. Nothing is ordered.", **over}


class Rig:
    def __init__(self, home, now=T0, digest=False):
        self.home, self.phone, self.now = home, Phone(), now
        self.channel = write_channel(home)
        self.state = home / "inbox.json"
        self.candidates, self.applied, self.parsed, self.verdicts = [cand()], [], [], []
        self.review, self.deleted = None, []
        self.facts = {"advisor_decided": 0, "acceptances": 0, "run": "Last run stopped."}
        if digest is False:                 # most tests are about packages: today's digest is already out
            fingerprint = ib.load_channel(self.channel)[1]["fingerprint"]
            self.state.write_text(json.dumps({"owner": "operator", "channel": fingerprint, "last_digest_day": "2026-11-26"}))

    def parse(self, text, open_items, echo):
        self.parsed.append(text)
        v = self.verdicts.pop(0) if self.verdicts else {"target": None, "verdict": "unclear", "condition": False, "confidence": 0.9}
        return {"condition": False, "confidence": 0.95, "target": None, **v}

    def apply(self, do, items, digest):
        self.applied.append(do)
        return {"approve": "Approved.", "decline": "Declined.", "defer": "Later.", "stop_advisor": "Advisor stopped.",
                "pause_run": "Paused."}[do["op"]], "done"

    def run(self, at=None):
        if at is not None:
            self.now = at
        return ib.cycle("operator", gather=lambda: list(self.candidates), author=lambda c: fields(),
                        parse=self.parse, apply=self.apply, digest_facts=lambda: self.facts, state_path=self.state,
                        channel_path=self.channel, clock=lambda: self.now,
                        transport={"send": self.phone.send, "fetch": self.phone.fetch, "delete": lambda ch, url, msg: self.deleted.append((url, msg)) or True}, review=self.review)

    def open_one(self):
        self.run(T0)                      # first run: records, sends nothing
        self.run(T0 + 31 * 60)            # waited past the batch window: one interrupt
        assert len(self.phone.sent) == 1
        self.phone.sent.clear()

    def echo(self, at=T0 + 41 * 60):
        """The owner asks to approve; the echo is delivered (and so armed)."""
        self.phone.say("go ahead with the glovebox one", at - 30)
        self.verdicts = [{"target": "glovebox shortlist", "verdict": "yes"}]
        self.run(at)
        assert self.phone.sent[-1]["body"].startswith("Understood: approve glovebox shortlist")

    def saved(self):
        return json.loads(self.state.read_text())


# ---- the message itself

def test_the_delegation_package_passes_the_fifteen_second_check():
    title, body = ib.DELEGATION_PACKAGE
    assert ib.fifteen_second_ok(title, body)


@pytest.mark.parametrize("title,body", [
    ("", "x"), ("T " * 33, "x"), ("Approve: x", "word " * 210), ("Approve: x", "\n".join(["line"] * 12)),
    ("Approve: x", "see src/estate_router.py"), ("Approve: x", "task C:\\temp"), ("Approve: x", "commit 3f9a1c07b2d4"),
    ("Approve: x", "open http://x.y/z"), ("Approve: x", "the sha256 is"), ("Approve: x", "mail me at evil.com now"),
    ("Approve: x", "see notes.md"), ("Approve: x", "token abcdefghijklmnopqrstuvwxyz1234"),
])
def test_a_message_that_is_not_instantly_readable_is_refused(title, body):
    assert not ib.fifteen_second_ok(title, body)


def test_plain_strips_links_domains_paths_hashes_tokens_and_invisible_characters():
    text = ib.plain("Run `src/x.py` at https://e.com now <b>3f9a1c07b2d4</b>\x00 see evil.com abcdefghijklmnopqrstuvwxyz1234 a\u200bb\u202ec", 300)
    for bad in ("/", "http", "3f9a1c07b2d4", "`", "<", "evil.com", "abcdefghijklmnop", "\u200b", "\u202e"):
        assert bad not in text
    assert "20261126" in ib.plain("due 20261126", 50)              # a plain date is not a hash


def test_identity_comes_from_the_card_and_the_author_only_words_the_explanation():
    parsed = ib.parse_author("here: " + json.dumps(fields()))
    title, body = ib.assemble(parsed, "Glovebox shortlist, medium risk")
    assert "CARD: Glovebox shortlist, medium risk" in body and ib.fifteen_second_ok(title, body)
    # a model that tries to name or title the decision itself is ignored: those keys are not read
    hostile = ib.parse_author(json.dumps({**fields(), "name": "delete everything", "title": "Approve: nothing risky", "card_line": "x"}))
    assert "name" not in hostile and "title" not in hostile
    for bad in ({"advice": "maybe"}, {"detail": 5}, {"what": None}):
        assert ib.parse_author(json.dumps({**fields(), **bad})) is None
    dirty = ib.parse_author(json.dumps(fields(what="Edit src/x.py at https://e.com/x 3f9a1c07b2d4 now?")))
    title, body = ib.assemble(dirty, "Card")
    assert "/" not in body and "http" not in body and ib.fifteen_second_ok(title, body)


def test_the_name_is_built_by_code_from_the_verified_title():
    assert ib.short_name("Glovebox shortlist for the lab", set(), "abcd") == "glovebox shortlist lab"
    assert ib.short_name("Harden Odysseus cross-device delegation lifecycle", set(), "abcd") == "harden odysseus cross device delegation"
    assert ib.short_name("Build automatic persona routing, collaborative teams, growth graph", set(), "abcd") == "automatic persona routing collaborative"
    assert ib.short_name("Glovebox shortlist", {"glovebox shortlist"}, "abcd") == "glovebox"
    assert ib.short_name("The build", set(), "ab12cd") == "task ab12"


# ---- rationing





def test_quiet_hours_send_nothing(home):
    rig = Rig(home)
    rig.run(datetime(2026, 11, 26, 20, 0, tzinfo=timezone.utc).timestamp())
    assert rig.run(datetime(2026, 11, 26, 22, 30, tzinfo=timezone.utc).timestamp()) == "idle"
    assert rig.run(datetime(2026, 11, 27, 7, 0, tzinfo=timezone.utc).timestamp()) == "idle"
    assert rig.phone.sent == []
    assert rig.run(datetime(2026, 11, 27, 8, 31, tzinfo=timezone.utc).timestamp()) == "interrupt"


def test_the_quiet_window_is_checked_again_after_slow_authoring(home):
    rig = Rig(home)
    clock = iter([datetime(2026, 11, 26, 20, 59, tzinfo=timezone.utc).timestamp()] + [datetime(2026, 11, 26, 21, 1, tzinfo=timezone.utc).timestamp()] * 20)
    rig.run(datetime(2026, 11, 26, 19, 0, tzinfo=timezone.utc).timestamp())
    out = ib.cycle("operator", gather=lambda: list(rig.candidates), author=lambda c: fields(), parse=rig.parse, apply=rig.apply,
                   digest_facts=lambda: {}, state_path=rig.state, channel_path=rig.channel, clock=lambda: next(clock),
                   transport={"send": rig.phone.send, "fetch": rig.phone.fetch})
    assert "interrupt" not in out and rig.phone.sent == []


def test_london_summer_time_moves_the_quiet_window():
    summer_21_30_london = datetime(2026, 7, 1, 20, 30, tzinfo=timezone.utc).timestamp()      # BST = UTC+1
    assert ib.quiet(summer_21_30_london) and not ib.quiet(datetime(2026, 7, 1, 19, 30, tzinfo=timezone.utc).timestamp())


def test_an_item_that_is_resolved_elsewhere_is_withdrawn_without_a_word(home):
    rig = Rig(home)
    rig.run(T0)
    rig.candidates = []
    assert rig.run(T0 + 31 * 60) == "idle"
    assert rig.phone.sent == []
    assert [i["state"] for i in rig.saved()["items"].values()] == ["withdrawn"]


def test_a_failed_send_gives_the_slot_back_and_retries_later(home):
    rig = Rig(home)
    rig.run(T0)
    rig.phone.refuse_sends = 1
    assert rig.run(T0 + 31 * 60) == "idle"
    state = rig.saved()
    assert state["interrupts"] == [] and [i["state"] for i in state["items"].values()] == ["queued"]
    assert rig.run(T0 + 40 * 60) == "idle" and rig.phone.sent == []                  # not before the retry delay
    assert rig.run(T0 + 62 * 60) == "interrupt"


def test_the_slot_is_reserved_durably_before_the_post(home):
    rig = Rig(home)
    rig.run(T0)
    seen = {}
    real = rig.phone.send

    def spy(channel, title, body, priority, *a, **k):
        if priority == 4:
            seen["state"] = rig.saved()                    # what is on disk at the moment of the post
        return real(channel, title, body, priority)
    rig.phone.send = spy
    rig.run(T0 + 31 * 60)
    assert seen["state"]["interrupts"] and [i["state"] for i in seen["state"]["items"].values()] == ["open"]




def test_health_reports_a_recent_finished_cycle(home):
    rig = Rig(home)
    assert not ib.healthy(T0, rig.state)
    rig.run(T0)
    assert ib.healthy(T0 + 60, rig.state) and not ib.healthy(T0 + ib.HEALTHY_SECONDS + 60, rig.state)


# ---- replies: only a plain-word yes, after a delivered echo, confirms

def test_an_approval_is_echoed_and_only_a_following_plain_yes_applies_it(home):
    rig = Rig(home)
    rig.open_one()
    rig.echo()
    assert rig.applied == [] and rig.saved()["echo"]["armed_at"] is not None
    rig.phone.say("yes", T0 + 42 * 60)
    rig.run(T0 + 43 * 60)
    assert [d["op"] for d in rig.applied] == ["approve"] and rig.applied[0]["confirmed"] is True
    assert rig.phone.sent[-1]["body"] == "Approved." and [i["state"] for i in rig.saved()["items"].values()] == ["answered"]
    assert rig.parsed == ["go ahead with the glovebox one"]            # the model never saw the confirmation


def test_a_model_yes_is_never_a_confirmation(home):
    rig = Rig(home)
    rig.open_one()
    rig.echo()
    rig.phone.say("yes but only the cheap one", T0 + 42 * 60)           # not a bare yes: it goes to the parser, which cannot confirm
    rig.verdicts = [{"target": "glovebox shortlist", "verdict": "yes", "condition": True}]
    rig.run(T0 + 43 * 60)
    assert rig.applied == []


def test_a_yes_with_no_echo_pending_never_approves(home):
    rig = Rig(home)
    rig.open_one()
    rig.phone.say("yes", T0 + 40 * 60)
    rig.verdicts = [{"target": None, "verdict": "yes"}]
    rig.run(T0 + 41 * 60)
    assert rig.applied == []                                           # it was echoed, not applied


def test_a_yes_typed_before_the_echo_was_sent_does_not_confirm_it(home):
    rig = Rig(home)
    rig.open_one()
    rig.phone.say("approve the glovebox one", T0 + 40 * 60 + 1)
    rig.phone.say("yes", T0 + 40 * 60 + 2)                              # already waiting in the feed when the echo goes out
    rig.verdicts = [{"target": "glovebox shortlist", "verdict": "yes"}]
    rig.run(T0 + 45 * 60)
    assert rig.applied == []


def test_an_echo_that_never_reached_the_phone_confirms_nothing(home):
    rig = Rig(home)
    rig.open_one()
    rig.phone.say("approve glovebox", T0 + 40 * 60)
    rig.verdicts = [{"target": "glovebox shortlist", "verdict": "yes"}]
    rig.phone.fail_sends = 1
    rig.run(T0 + 41 * 60)
    assert rig.saved()["echo"] is None
    rig.phone.say("yes", T0 + 42 * 60)
    rig.verdicts = [{"target": None, "verdict": "yes"}]
    rig.run(T0 + 43 * 60)
    assert rig.applied == []


def test_an_expired_echo_does_not_carry_a_later_yes(home):
    rig = Rig(home)
    rig.open_one()
    rig.echo()
    late = T0 + 41 * 60 + ib.ECHO_TTL_SECONDS + 600
    rig.phone.say("yes", late)
    rig.verdicts = [{"target": None, "verdict": "yes"}]
    rig.run(late + 60)
    assert rig.applied == []


@pytest.mark.parametrize("change,word", [("later", "not today, ask me next week"), ("no", "nah leave that")])
def test_a_postponement_or_refusal_cancels_a_pending_echo_so_a_later_yes_cannot_override_it(home, change, word):
    rig = Rig(home)
    rig.open_one()
    rig.echo()
    rig.phone.say(word, T0 + 42 * 60)
    rig.verdicts = [{"target": "glovebox shortlist", "verdict": change}]
    rig.run(T0 + 43 * 60)
    assert [d["op"] for d in rig.applied] == [{"later": "defer", "no": "decline"}[change]]
    rig.phone.say("yes", T0 + 44 * 60)
    rig.verdicts = [{"target": None, "verdict": "yes"}]
    rig.run(T0 + 45 * 60)
    assert [d["op"] for d in rig.applied] == [{"later": "defer", "no": "decline"}[change]]       # nothing new was approved


def test_stop_advisor_cancels_a_pending_echo(home):
    rig = Rig(home)
    rig.open_one()
    rig.echo()
    rig.phone.say("stop advisor approvals", T0 + 42 * 60)
    rig.run(T0 + 43 * 60)
    assert rig.saved()["echo"] is None and [d["op"] for d in rig.applied] == ["stop_advisor"]


def test_a_withdrawn_item_voids_its_echo(home):
    rig = Rig(home)
    rig.open_one()
    rig.echo()
    rig.candidates = []                                                # resolved elsewhere
    rig.phone.say("yes", T0 + 42 * 60)
    rig.run(T0 + 43 * 60)
    assert rig.applied == [] and rig.saved()["echo"] is None


def test_a_card_that_changed_goes_back_to_the_queue_and_voids_its_echo(home):
    rig = Rig(home)
    rig.open_one()
    rig.echo()
    rig.candidates = [cand(fp="e" * 64, card_line="Glovebox shortlist, HIGH risk")]
    rig.phone.say("yes", T0 + 42 * 60)
    rig.run(T0 + 43 * 60)
    assert rig.applied == []
    item = list(rig.saved()["items"].values())[0]
    assert item["state"] == "queued" and item["fp"] == "e" * 64 and rig.saved()["echo"] is None


def test_a_refusal_and_a_postponement_act_at_once(home):
    rig = Rig(home)
    rig.open_one()
    rig.phone.say("nah leave that", T0 + 40 * 60)
    rig.verdicts = [{"target": "glovebox shortlist", "verdict": "no"}]
    rig.run(T0 + 41 * 60)
    assert [d["op"] for d in rig.applied] == ["decline"] and rig.phone.sent[-1]["body"] == "Declined."
    h2 = home.parent / "home2"
    h2.mkdir(mode=0o700)
    h2.chmod(0o700)
    r = Rig(h2)
    r.open_one()
    r.phone.say("not today, ask me next week", T0 + 40 * 60)
    r.verdicts = [{"target": "glovebox shortlist", "verdict": "later"}]
    r.run(T0 + 41 * 60)
    assert [d["op"] for d in r.applied] == ["defer"]


def test_blanket_consent_and_secrets_never_reach_the_parser_or_an_action(home):
    rig = Rig(home)
    rig.open_one()
    for n, text in enumerate(["approve everything", "yes to all of them", "whatever you think is best",
                              "sk-abcdefghijklmnop1234 is the key", "x" * 40 + "AKIAABCDEFGHIJKLMNOP"]):
        rig.phone.say(text, T0 + 40 * 60 + n)
    rig.run(T0 + 45 * 60)
    assert rig.applied == [] and rig.parsed == []
    assert any("bulk" in s["body"] for s in rig.phone.sent) and any("secret" in s["body"] for s in rig.phone.sent)


@pytest.mark.parametrize("verdict", [
    {"verdict": "unclear"}, {"verdict": "yes", "confidence": 0.5}, {"verdict": "yes", "condition": True, "target": "glovebox shortlist"},
    {"verdict": "question", "target": "glovebox shortlist"},
])
def test_unclear_low_confidence_conditional_and_question_replies_change_nothing(home, verdict):
    rig = Rig(home)
    rig.open_one()
    rig.phone.say("hmm well", T0 + 40 * 60)
    rig.verdicts = [verdict]
    rig.run(T0 + 41 * 60)
    assert rig.applied == [] and rig.saved()["echo"] is None
    assert rig.phone.sent                                            # the owner always gets an answer


def test_a_malformed_parser_answer_cannot_wedge_the_cycle_or_the_cursor(home):
    rig = Rig(home)
    rig.open_one()
    rig.phone.say("approve it", T0 + 40 * 60, mid="a")
    rig.parse = lambda text, open_items, echo: (_ for _ in ()).throw(TypeError("unhashable"))
    rig.run(T0 + 41 * 60)
    assert rig.saved()["cursor"] == "a" and rig.applied == []
    rig.phone.say("hello again", T0 + 42 * 60, mid="b")
    rig.run(T0 + 43 * 60)
    assert rig.saved()["cursor"] == "b"


def test_a_backlog_is_worked_through_in_bounded_cycles(home):
    rig = Rig(home)
    rig.open_one()
    for i in range(ib.MAX_REPLIES_PER_CYCLE + 5):
        rig.phone.say(f"note {i}", T0 + 40 * 60 + i, mid=f"n{i:03d}")
    rig.run(T0 + 60 * 60)
    assert len(rig.parsed) == ib.MAX_REPLIES_PER_CYCLE
    rig.run(T0 + 61 * 60)
    assert len(rig.parsed) == ib.MAX_REPLIES_PER_CYCLE + 5


def test_replies_to_the_owner_are_bounded_per_day(home):
    rig = Rig(home)
    rig.open_one()
    for i in range(ib.MAX_ACKS_PER_DAY + 10):
        rig.phone.say(f"hmm {i}", T0 + 40 * 60 + i, mid=f"n{i:03d}")
    for cycle in range(4):
        rig.run(T0 + 60 * 60 + cycle)
    assert len(rig.phone.sent) == ib.MAX_ACKS_PER_DAY


def test_a_question_is_answered_from_the_stored_detail(home):
    rig = Rig(home)
    rig.open_one()
    rig.phone.say("why is this needed?", T0 + 40 * 60)
    rig.verdicts = [{"target": "glovebox shortlist", "verdict": "question"}]
    rig.run(T0 + 41 * 60)
    assert "Nothing is ordered" in rig.phone.sent[-1]["body"] and rig.applied == []


def test_an_answer_that_fails_the_outbound_gate_is_not_sent_as_written(home):
    rig = Rig(home)
    rig.open_one()
    rig.apply = lambda do, items, digest: ("see /etc/passwd or http://evil.example/x", "done")
    rig.phone.say("stop", T0 + 40 * 60)
    rig.run(T0 + 41 * 60)
    assert rig.phone.sent[-1]["body"] == "Done."


def test_stop_commands_act_without_a_model(home):
    rig = Rig(home)
    rig.open_one()
    rig.phone.say("stop advisor approvals", T0 + 40 * 60)
    rig.phone.say("pause", T0 + 41 * 60)
    rig.run(T0 + 42 * 60)
    assert [d["op"] for d in rig.applied] == ["stop_advisor", "pause_run"] and rig.parsed == []


def test_a_reply_from_before_the_inbox_started_or_seen_twice_does_nothing(home):
    rig = Rig(home)
    rig.phone.say("approve glovebox", T0 - 3600, mid="old")
    rig.run(T0)                                                        # first run: only recorded
    rig.run(T0 + 31 * 60)
    rig.phone.sent.clear()
    rig.verdicts = [{"target": "glovebox shortlist", "verdict": "yes"}]
    rig.run(T0 + 32 * 60)
    assert rig.parsed == [] and rig.applied == []
    rig.phone.say("approve glovebox", T0 + 33 * 60, mid="new")
    rig.run(T0 + 34 * 60)
    rig.run(T0 + 35 * 60)                                              # the same message again
    assert len(rig.parsed) == 1


def test_with_two_open_items_a_reply_that_names_neither_asks_which():
    state = {"items": {"a": {"id": "a", "name": "glovebox", "state": "open", "ask": "x", "detail": "d"},
                       "b": {"id": "b", "name": "ethics dossier", "state": "open", "ask": "y", "detail": "d"}}, "echo": None}
    out = ib.interpret("yes please", state, NOON, lambda t, o, e: {"target": None, "verdict": "yes", "condition": False, "confidence": 0.95})
    assert out["do"] is None and "Which one: ethics dossier, glovebox? Reply like 'approve P1'." == out["say"]


def test_a_parser_naming_an_item_that_is_not_open_is_ignored():
    parsed = ib.parse_reply(json.dumps({"target": "something else", "verdict": "yes", "condition": False, "confidence": 0.9}), {"glovebox"})
    assert parsed["target"] is None
    assert ib.parse_reply(json.dumps({"target": ["glovebox"], "verdict": "yes", "condition": False, "confidence": 0.9}), {"glovebox"})["target"] is None
    assert ib.parse_reply(json.dumps({"target": None, "verdict": ["yes"], "condition": False, "confidence": 0.9}), set()) is None
    assert ib.parse_reply("{}", {"x"}) is None
    assert ib.parse_reply(json.dumps({"target": None, "verdict": "approve", "condition": False, "confidence": 1}), set()) is None
    assert ib.parse_reply(json.dumps({"target": None, "verdict": "yes", "condition": False, "confidence": True}), set()) is None


# ---- state, channel, transport

def test_the_reply_topic_is_mandatory_and_must_differ_from_the_publish_topic(home):
    rig = Rig(home)
    write_channel(home, reply_topic="")
    assert rig.run(T0) == "no_reply_topic"
    write_channel(home, reply_topic="alerts-topic-1234")
    assert rig.run(T0) == "reply_topic_equals_publish_topic"
    write_channel(home)
    assert ib.cycle("someone-else", gather=lambda: [], author=None, parse=None, apply=None, digest_facts=dict,
                    state_path=rig.state, channel_path=rig.channel, clock=lambda: T0) == "owner_changed"


def test_state_is_private_and_a_corrupt_file_repairs_itself(home):
    rig = Rig(home)
    rig.run(T0)
    assert stat.S_IMODE(os.stat(rig.state).st_mode) == 0o600
    rig.state.write_text("{not json")
    assert rig.run(T0 + 60) == "first_run"


def test_poisoned_state_entries_are_dropped_and_cannot_arm_an_approval(home):
    rig = Rig(home)
    rig.open_one()
    state = rig.saved()
    state["items"]["badbadbadbad"] = {"id": "badbadbadbad", "kind": "approval", "state": "open", "seen_at": 0, "task_ref": "odysseus:x",
                                      "task_id": "t", "scope": "not-a-digest"}
    state["items"]["feedfeedfeed"] = {"id": "other-id", "kind": "approval", "state": "open", "seen_at": 0}
    state["echo"] = {"item": "nonexistent", "name": "x", "op": "approve", "expires": T0 + 99999, "armed_at": 1}
    rig.state.write_text(json.dumps(state))
    loaded = ib._read_state(rig.state)
    assert set(loaded["items"]) == {i for i in state["items"] if i not in ("badbadbadbad", "feedfeedfeed")} and loaded["echo"] is None
    rig.phone.say("yes", T0 + 50 * 60)
    rig.run(T0 + 51 * 60)
    assert rig.applied == []


def test_a_state_file_from_another_owner_or_channel_does_not_carry_over(home):
    rig = Rig(home)
    rig.open_one()
    rig.echo()
    state = rig.saved()
    state["owner"] = "someone-else"
    rig.state.write_text(json.dumps(state))
    rig.phone.say("yes", T0 + 50 * 60)
    out = rig.run(T0 + 51 * 60)
    assert rig.applied == [] and out == "first_run"


def test_send_and_fetch_use_the_pinned_address_with_basic_auth(monkeypatch):
    seen = {}

    class Response:
        status = 200

        def __init__(self, data=b""):
            self.data = data

        def read(self, n=-1):
            return self.data

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    class Opener:
        def open(self, request, timeout=None):
            seen["url"], seen["headers"], seen["timeout"] = request.full_url, {k.lower(): v for k, v in request.header_items()}, timeout
            lines = [{"event": "open", "id": "x"}, {"event": "message", "id": "m2", "time": 200, "message": "later"},
                     {"event": "message", "id": "m1", "time": 100, "message": "hello"},
                     {"event": "message", "id": 5, "time": 100, "message": "bad"}, "garbage"]
            return Response("\n".join(json.dumps(x) if not isinstance(x, str) else x for x in lines).encode())

    monkeypatch.setattr(ib, "_opener", lambda: Opener())
    channel = {"url": "http://100.75.149.126:8091/alerts-topic-1234", "reply_url": "http://100.75.149.126:8091/reply-topic-1234",
               "user": "odysseus", "password": "pw", "owner": "operator"}
    assert ib.send(channel, "Approve: caf\u00e9 thing", "body", 4)
    assert seen["url"] == channel["url"] and seen["headers"]["priority"] == "4" and "click" not in seen["headers"] and seen["headers"]["tags"] == "robot"
    assert seen["headers"]["title"] == "Approve: caf thing" and seen["headers"]["authorization"].startswith("Basic ")
    assert [m["id"] for m in ib.fetch_replies(channel, "all")] == ["m1", "m2"]              # oldest first
    assert seen["url"].startswith("http://100.75.149.126:8091/reply-topic-1234/json?") and "since=all" in seen["url"]


def test_a_timeout_after_the_post_keeps_the_reservation_so_it_is_not_sent_twice_within_fifteen_minutes(home):
    rig = Rig(home)
    rig.run(T0)
    rig.phone.fail_sends = 1                                # the broker may have accepted it
    assert "interrupt_unconfirmed" in rig.run(T0 + 31 * 60)
    state = rig.saved()
    assert len(state["interrupts"]) == 1 and [i["state"] for i in state["items"].values()] == ["open"]
    assert rig.run(T0 + 31 * 60 + 10 * 60) == "idle" and rig.phone.sent == []          # never twice inside the window
    rig.run(T0 + 31 * 60 + ib.UNCONFIRMED_RESEND_SECONDS + 60)                          # then, if nothing came of it, once more
    rig.run(T0 + 31 * 60 + ib.UNCONFIRMED_RESEND_SECONDS + 180)
    assert len(rig.phone.sent) == 1


def test_a_digest_whose_post_timed_out_is_not_repeated(home):
    rig = Rig(home, digest=True)
    rig.candidates = []
    rig.run(datetime(2026, 11, 26, 8, 0, tzinfo=timezone.utc).timestamp())
    rig.phone.fail_sends = 1
    rig.run(datetime(2026, 11, 26, 9, 0, tzinfo=timezone.utc).timestamp())
    assert rig.run(datetime(2026, 11, 26, 10, 0, tzinfo=timezone.utc).timestamp()) == "idle" and rig.phone.sent == []


def test_a_yes_stamped_in_the_same_second_as_the_echo_does_not_confirm(home):
    rig = Rig(home)
    rig.open_one()
    rig.phone.say("approve the glovebox one", T0 + 40 * 60)
    rig.verdicts = [{"target": "glovebox shortlist", "verdict": "yes"}]
    rig.phone.say("yes", int(T0 + 41 * 60))                        # the same whole second as the echo is delivered below
    rig.run(T0 + 41 * 60 + 0.5)
    assert rig.applied == []
    assert rig.saved()["echo"] is None                              # the premature yes ended the confirmation window: the
    rig.phone.say("yes", int(T0 + 41 * 60) + 1)                    # confirming yes must be the very next message after it
    rig.verdicts = [{"target": None, "verdict": "yes"}]
    rig.run(T0 + 41 * 60 + 5)
    assert rig.applied == []                                        # a later yes only starts a NEW echo
    assert rig.phone.sent[-1]["body"].startswith("Understood: approve glovebox shortlist")


def test_a_long_reply_that_starts_with_yes_is_not_a_bare_yes(home):
    assert ib._YES.match(ib.clean_reply("yes"))
    cleaned = ib.clean_reply("yes " + "x" * 600 + " but only if it is free")
    assert len(cleaned) == ib.MAX_REPLY_CHARS and not ib._YES.match(cleaned)
    assert not ib._YES.match(ib.clean_reply("yes" + " " * 500 + "but not the second one"))


def test_a_confirmation_is_judged_against_its_own_time_not_the_cycles(home):
    rig = Rig(home)
    rig.open_one()
    rig.echo()
    late = T0 + 41 * 60 + ib.ECHO_TTL_SECONDS + 5
    rig.phone.say("yes", late)                                      # stamped after the echo expired ...
    rig.run(late - ib.ECHO_TTL_SECONDS)                             # ... but the cycle's own clock is still early
    assert rig.applied == []


def test_a_cycle_whose_feed_cannot_be_read_is_not_healthy(home):
    rig = Rig(home)
    rig.run(T0)
    assert ib.healthy(T0 + 60, rig.state)
    rig.state.unlink()
    broken = Rig(home)
    broken.phone.fetch = lambda channel, since: (_ for _ in ()).throw(OSError("feed down"))
    broken.run(T0)
    assert not ib.healthy(T0 + 60, broken.state)


def test_health_is_bound_to_the_channel_it_was_earned_on(home):
    rig = Rig(home)
    rig.run(T0)
    fingerprint = ib.load_channel(rig.channel)[1]["fingerprint"]
    assert ib.healthy(T0 + 60, rig.state, fingerprint) and not ib.healthy(T0 + 60, rig.state, "0" * 16)


def test_state_with_a_list_for_the_echo_item_or_an_open_item_without_a_send_time_cannot_wedge_a_cycle(home):
    rig = Rig(home)
    rig.open_one()
    state = rig.saved()
    state["echo"] = {"item": ["x"], "name": "n", "op": "approve", "expires": T0 + 99999, "armed_at": 1}
    first = next(iter(state["items"]))
    state["items"][first]["sent_at"] = None
    rig.state.write_text(json.dumps(state))
    loaded = ib._read_state(rig.state)
    assert loaded["echo"] is None and first not in loaded["items"]
    rig.run(T0 + 50 * 60)                                            # and the next cycle simply carries on


@pytest.mark.parametrize("between", [
    ("why do you need this?", {"target": "glovebox shortlist", "verdict": "question"}),         # a question
    ("sounds good but only the cheap option", {"target": "glovebox shortlist", "verdict": "yes", "condition": True}),   # a condition
    ("hmm", {"verdict": "unclear"}),                                                              # not understood
    ("approve everything", None),                                                                 # blanket consent
    ("sk-abcdefghijklmnop1234", None),                                                            # a secret
])
def test_anything_else_the_owner_says_ends_the_pending_confirmation(home, between):
    text, verdict = between
    rig = Rig(home)
    rig.open_one()
    rig.echo()
    rig.phone.say(text, T0 + 42 * 60)
    rig.verdicts = [verdict] if verdict else []
    rig.run(T0 + 43 * 60)
    assert rig.saved()["echo"] is None
    rig.phone.say("yes", T0 + 44 * 60)
    rig.verdicts = [{"target": None, "verdict": "yes"}]
    rig.run(T0 + 45 * 60)
    assert rig.applied == []                                         # that yes only creates a NEW echo; it approves nothing


@pytest.mark.parametrize("word", ["ok", "okay", "sure", "correct", "that's right", "fine", "cool"])
def test_acknowledgements_are_not_consent(home, word):
    rig = Rig(home)
    rig.open_one()
    rig.echo()
    rig.phone.say(word, T0 + 42 * 60)
    rig.verdicts = [{"target": None, "verdict": "unclear"}]
    rig.run(T0 + 43 * 60)
    assert rig.applied == []


@pytest.mark.parametrize("word", ["yes", "Yes!", "yep", "yeah please", "go ahead", "do it", "approved", "confirm"])
def test_the_plain_words_that_do_confirm(home, word):
    rig = Rig(home)
    rig.open_one()
    rig.echo()
    rig.phone.say(word, T0 + 42 * 60)
    rig.run(T0 + 43 * 60)
    assert [d["op"] for d in rig.applied] == ["approve"]


def test_a_card_title_containing_sha256_does_not_break_the_package():
    assert "sha256" not in ib.plain("Harden the SHA256 digest handling", 80).lower()
    assert ib.fifteen_second_ok("Approve: digest", ib.assemble(fields(), ib.plain("Harden the SHA256 digest handling, high risk", 60))[1])


def test_an_item_that_cannot_be_worded_does_not_starve_the_ones_behind_it(home, monkeypatch):
    rig = Rig(home)
    rig.candidates = [cand(task_ref="odysseus:ready/bad.md", task_id="bad", scope="b" * 64, title="Bad one", priority="critical"),
                      cand()]
    real = ib._package

    def package(c, item, author, state):
        return None if c["task_id"] == "bad" else real(c, item, author, state)
    monkeypatch.setattr(ib, "_package", package)
    rig.run(T0)
    rig.run(T0 + 31 * 60)
    assert len(rig.phone.sent) == 1 and "Glovebox" in rig.phone.sent[0]["body"]
    bad = next(i for i in rig.saved()["items"].values() if i["task_id"] == "bad")
    assert bad["state"] == "queued" and bad["retry_at"] > T0 + 31 * 60              # retried later, not on every tick


def test_an_echo_whose_text_was_replaced_by_the_outbound_gate_is_never_armed(home, monkeypatch):
    rig = Rig(home)
    rig.open_one()
    real = ib.outbound_ok
    monkeypatch.setattr(ib, "outbound_ok", lambda text: False if str(text).startswith("Understood") else real(text))
    rig.phone.say("approve glovebox", T0 + 40 * 60)
    rig.verdicts = [{"target": "glovebox shortlist", "verdict": "yes"}]
    rig.run(T0 + 41 * 60)
    assert rig.phone.sent[-1]["body"] == "Done." and rig.saved()["echo"] is None
    rig.phone.say("yes", T0 + 42 * 60)
    rig.verdicts = [{"target": None, "verdict": "yes"}]
    rig.run(T0 + 43 * 60)
    assert rig.applied == []


def test_a_cycle_whose_posts_were_refused_is_not_healthy(home):
    rig = Rig(home)
    rig.run(T0)
    rig.phone.refuse_sends = 1
    rig.run(T0 + 31 * 60)                                            # the interrupt is refused by the server
    state = rig.saved()
    assert state["last_ok"] == T0                                    # only the first, clean cycle counts


# ---- per-repository approval topics (outgoing packages only; replies stay on the one reply topic)

BASE = "http://100.75.149.126:8091"


def write_routes(home, data):
    (home / "ntfy_approval_topics.json").write_text(json.dumps(data))
    state = home / "inbox.json"
    if state.exists():                           # keep a rig's seeded state valid for the (possibly two-way) fingerprint
        saved = json.loads(state.read_text())
        saved["channel"] = ib.load_channel(home / "ntfy_channel.json")[1]["fingerprint"]
        state.write_text(json.dumps(saved))


def first_package(rig):
    rig.run(T0)
    rig.run(T0 + 31 * 60)
    return rig.phone.sent[0]


@pytest.mark.parametrize("task_ref,topic", [("odysseus:ready/glove.md", "odysseus-approvals"),
                                            ("obsidian-phd:ready/x.md", "phd-approvals"),
                                            ("misumi:ready/m.md", "misumi-approvals")])
def test_a_package_goes_to_its_repositorys_approval_topic(home, task_ref, topic):
    rig = Rig(home)
    write_routes(home, {"odysseus": "odysseus-approvals", "obsidian-phd": "phd-approvals", "misumi": "misumi-approvals"})
    rig.candidates = [cand(task_ref=task_ref)]
    assert first_package(rig)["url"] == f"{BASE}/{topic}"


def test_a_repository_without_a_route_uses_the_shared_channel(home):
    rig = Rig(home)
    write_routes(home, {"odysseus": "odysseus-approvals"})
    rig.candidates = [cand(task_ref="misumi:ready/m.md", task_id="m", scope="d" * 64, title="Misumi thing")]
    assert first_package(rig)["url"] == f"{BASE}/alerts-topic-1234"


@pytest.mark.parametrize("content", ["not json", "[1, 2]", "{\"odysseus\": 7}", "{\"odysseus\": \"../x\"}", "{\"odysseus\": \"ab\"}",
                                     "{\"Odysseus\": \"odysseus-approvals\"}", "{\"odysseus\": \"reply-topic-1234\"}"])
def test_a_missing_malformed_or_unsafe_route_file_changes_nothing(home, content):
    rig = Rig(home)
    (home / "ntfy_approval_topics.json").write_text(content)
    assert first_package(rig)["url"] == f"{BASE}/alerts-topic-1234"


def test_a_route_can_never_be_the_reply_topic(home):
    write_channel(home)
    write_routes(home, {"odysseus": "reply-topic-1234", "misumi": "misumi-approvals"})
    status, channel = ib.load_channel(home / "ntfy_channel.json")
    assert status == "ok" and channel["routes"] == {"misumi": f"{BASE}/misumi-approvals"}
    assert channel["reply_url"] == f"{BASE}/reply-topic-1234"


def test_routes_do_not_change_the_channel_fingerprint(home):
    write_channel(home)
    before = ib.load_channel(home / "ntfy_channel.json")[1]["fingerprint"]
    write_routes(home, {"odysseus": "odysseus-approvals"})
    assert ib.load_channel(home / "ntfy_channel.json")[1]["fingerprint"] == before


def test_the_delegation_package_keeps_the_shared_channel(home):
    rig = Rig(home)
    write_routes(home, {"odysseus": "odysseus-approvals"})
    rig.candidates = [cand(kind="delegation", task_ref="policy:advisor-approvals", task_id=ib.DELEGATION_TASK_ID, scope=ib.DELEGATION_SCOPE, title="advisor approvals", priority="critical")]
    assert first_package(rig)["url"] == f"{BASE}/alerts-topic-1234"


def test_replies_are_still_read_from_the_one_reply_topic(home):
    rig = Rig(home)
    write_routes(home, {"odysseus": "odysseus-approvals"})
    seen = []
    real = rig.phone.fetch
    rig.phone.fetch = lambda channel, since: (seen.append(channel["reply_url"]), real(channel, since))[1]
    first_package(rig)
    assert seen and set(seen) == {f"{BASE}/reply-topic-1234"}


@pytest.mark.parametrize("content", ['{"odysseus": "reply-topic-1234\\n"}', '{"odysseus": "odysseus-approvals\\n"}',
                                     '{"odysseus": "random-topic"}', '{"odysseus": "odysseus-approvals-extra"}',
                                     '{"odysseus": "Odysseus-approvals"}', '{"odysseus\\n": "odysseus-approvals"}'])
def test_the_names_are_an_allowlist_and_a_trailing_newline_is_not_a_name(home, content):
    rig = Rig(home)
    (home / "ntfy_approval_topics.json").write_text(content)
    assert first_package(rig)["url"] == f"{BASE}/alerts-topic-1234"


def test_a_route_file_that_is_a_link_a_pipe_or_a_directory_is_ignored(home):
    write_channel(home)
    real = home / "real.json"
    real.write_text(json.dumps({"odysseus": "odysseus-approvals"}))
    link = home / "ntfy_approval_topics.json"
    link.symlink_to(real)
    assert ib.load_channel(home / "ntfy_channel.json")[1]["routes"] == {}
    link.unlink()
    os.mkfifo(link)
    assert ib.load_channel(home / "ntfy_channel.json")[1]["routes"] == {}     # returns at once: a pipe is never read
    link.unlink()
    link.mkdir()
    assert ib.load_channel(home / "ntfy_channel.json")[1]["routes"] == {}


def test_at_most_eight_routes_are_used(home):
    write_channel(home)
    write_routes(home, {f"repo{i}": f"repo{i}-approvals" for i in range(12)})
    assert len(ib.load_channel(home / "ntfy_channel.json")[1]["routes"]) == 8


def test_the_route_is_chosen_before_the_slot_is_spent(home):
    """A package that cannot be addressed must not burn the day's interrupt: the lookup happens before the reservation."""
    rig = Rig(home)
    write_routes(home, {"odysseus": "odysseus-approvals"})
    rig.run(T0)
    rig.run(T0 + 31 * 60)
    saved = rig.saved()
    assert len(saved["interrupts"]) == 1 and rig.phone.sent[0]["url"] == f"{BASE}/odysseus-approvals"


def test_a_refused_route_falls_back_to_the_shared_topic_so_nothing_is_blocked(home):
    rig = Rig(home)
    write_routes(home, {"odysseus": "odysseus-approvals"})
    rig.phone.refuse_sends = 1                  # the broker answered 403 for the routed topic (no ACL grant)
    rig.run(T0)
    rig.run(T0 + 31 * 60)
    assert [s["url"] for s in rig.phone.sent] == [f"{BASE}/alerts-topic-1234"] and len(rig.saved()["interrupts"]) == 1


def test_if_the_shared_topic_refuses_too_the_slot_is_returned(home):
    rig = Rig(home)
    write_routes(home, {"odysseus": "odysseus-approvals"})
    rig.phone.refuse_sends = 2
    rig.run(T0)
    rig.run(T0 + 31 * 60)
    assert rig.phone.sent == [] and rig.saved()["interrupts"] == []


@pytest.mark.parametrize("task_ref", ["", ":", "a:b:c", "ODYSSEUS:x", "odysseus", ":odysseus", "odysseus\n:x"])
def test_odd_task_ref_shapes_use_the_shared_channel(home, task_ref):
    rig = Rig(home)
    write_routes(home, {"odysseus": "odysseus-approvals"})
    rig.candidates = [cand(task_ref=task_ref)]
    try:
        assert first_package(rig)["url"] == f"{BASE}/alerts-topic-1234"
    except IndexError:
        pass                                    # a candidate without a usable task_ref may be withdrawn, never misrouted


@pytest.mark.parametrize("name,ok", [("a" * 53 + "-approvals", True), ("a" * 55 + "-approvals", False)])
def test_a_topic_longer_than_ntfy_allows_is_ignored(home, name, ok):
    write_channel(home)
    write_routes(home, {"odysseus": name})
    routes = ib.load_channel(home / "ntfy_channel.json")[1]["routes"]
    assert routes == ({"odysseus": f"{BASE}/{name}"} if ok else {})


def test_a_route_file_over_the_size_limit_is_ignored(home):
    write_channel(home)
    (home / "ntfy_approval_topics.json").write_text(json.dumps({"odysseus": "odysseus-approvals"}) + " " * 5000)
    assert ib.load_channel(home / "ntfy_channel.json")[1]["routes"] == {}


def test_a_reply_topic_named_like_a_route_makes_the_channel_unusable(home):
    write_channel(home, reply_topic="owner-approvals")
    write_routes(home, {"odysseus": "odysseus-approvals"})
    assert ib.load_channel(home / "ntfy_channel.json") == ("reply_topic_reserved_for_approvals", None)


def test_load_channel_with_no_path_reads_the_default_channel_directory(home, monkeypatch):
    path = write_channel(home)
    write_routes(home, {"odysseus": "odysseus-approvals"})
    monkeypatch.setattr(ib.oa, "CHANNEL_PATH", path)
    assert ib.load_channel()[1]["routes"] == {"odysseus": f"{BASE}/odysseus-approvals"}


def test_a_routed_send_posts_to_the_route_tagged_as_the_agent_and_records_its_id(home, monkeypatch):
    status, channel = ib.load_channel(write_channel(home))
    seen = {}

    class Reply:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self, n=-1):
            return b'{"id": "abc123", "event": "message"}'

    class Opener:
        def open(self, request, timeout=None):
            seen["url"], seen["tags"], seen["click"] = request.full_url, request.get_header("Tags"), request.get_header("Click")
            return Reply()

    monkeypatch.setattr(ib, "_opener", lambda: Opener())
    ids = []
    assert ib.send({**channel, "url": f"{BASE}/odysseus-approvals", "_published": ids}, "Approve: x", "body", 4)
    assert seen == {"url": f"{BASE}/odysseus-approvals", "tags": "robot", "click": None} and ids == ["abc123"]


NIGHT = datetime(2026, 11, 26, 21, 0, 2, tzinfo=timezone.utc).timestamp()          # London == UTC in November


def test_a_server_error_on_the_routed_topic_never_posts_a_second_copy(home):
    rig = Rig(home)
    write_routes(home, {"odysseus": "odysseus-approvals"})
    rig.phone.refuse_sends, rig.phone.refuse_code = 1, 500       # not an access refusal: the message may have been stored
    rig.run(T0)
    rig.run(T0 + 31 * 60)
    assert rig.phone.sent == [] and rig.saved()["interrupts"] == []


def test_a_refused_route_never_falls_back_into_quiet_hours(home):
    rig = Rig(home)
    write_routes(home, {"odysseus": "odysseus-approvals"})
    rig.run(T0)
    real = rig.phone.send

    def refused_at_night(channel, title, body, priority, *a, **k):
        rig.now = NIGHT                                           # the attempt started before 21:00 and failed after it
        return real(channel, title, body, priority, *a, **k)

    rig.phone.refuse_sends, rig.phone.send = 1, refused_at_night
    rig.run(T0 + 31 * 60)
    assert rig.phone.sent == [] and rig.saved()["interrupts"] == []       # the slot is returned; the package waits for the morning


def test_only_approval_cards_are_routed_so_a_policy_route_cannot_capture_the_delegation_package(home):
    rig = Rig(home)
    write_routes(home, {"policy": "misumi-approvals"})
    rig.candidates = [cand(kind="delegation", task_ref="policy:advisor-approvals", task_id=ib.DELEGATION_TASK_ID,
                           scope=ib.DELEGATION_SCOPE, title="advisor approvals", priority="critical")]
    assert first_package(rig)["url"] == f"{BASE}/alerts-topic-1234"


def test_a_route_file_that_others_can_write_or_that_nests_deeply_is_ignored_without_a_crash(home):
    write_channel(home)
    path = home / "ntfy_approval_topics.json"
    path.write_text(json.dumps({"odysseus": "odysseus-approvals"}))
    path.chmod(0o666)
    assert ib.load_channel(home / "ntfy_channel.json")[1]["routes"] == {}
    path.chmod(0o600)
    assert ib.load_channel(home / "ntfy_channel.json")[1]["routes"] == {"odysseus": f"{BASE}/odysseus-approvals"}
    path.write_text("[" * 1100 + "]" * 1100)
    assert ib.load_channel(home / "ntfy_channel.json")[1]["routes"] == {}


def test_the_fallback_works_through_the_real_send_when_the_broker_answers_403(home, monkeypatch):
    """The refusal code must travel through the real `send` (not only the fake) for the fallback to fire."""
    import urllib.error
    rig = Rig(home)
    write_routes(home, {"odysseus": "odysseus-approvals"})
    posted = []

    class Ok:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    class Opener:
        def open(self, request, timeout=None):
            posted.append(request.full_url)
            if request.full_url.endswith("/odysseus-approvals"):
                raise urllib.error.HTTPError(request.full_url, 403, "forbidden", {}, None)
            return Ok()

    monkeypatch.setattr(ib, "_opener", lambda: Opener())
    rig.phone.send = ib.send
    rig.run(T0)
    rig.run(T0 + 31 * 60)
    assert posted == [f"{BASE}/odysseus-approvals", f"{BASE}/alerts-topic-1234"] and len(rig.saved()["interrupts"]) == 1


def test_a_server_error_through_the_real_send_never_falls_back(home, monkeypatch):
    import urllib.error
    rig = Rig(home)
    write_routes(home, {"odysseus": "odysseus-approvals"})
    posted = []

    class Opener:
        def open(self, request, timeout=None):
            posted.append(request.full_url)
            raise urllib.error.HTTPError(request.full_url, 500, "error", {}, None)

    monkeypatch.setattr(ib, "_opener", lambda: Opener())
    rig.phone.send = ib.send
    rig.run(T0)
    rig.run(T0 + 31 * 60)
    assert posted == [f"{BASE}/odysseus-approvals"] and rig.saved()["interrupts"] == []


# ---- two-way approval topics: the owner's reply is typed where the request was posted

def two_way_rig(home):
    rig = Rig(home)
    write_routes(home, {"odysseus": "odysseus-approvals", "obsidian-phd": "phd-approvals", "misumi": "misumi-approvals"})
    return rig


def test_the_backends_own_post_is_never_read_as_the_owners_voice(home):
    rig = two_way_rig(home)
    rig.run(T0)
    rig.run(T0 + 31 * 60)
    assert rig.phone.sent and "pub0" in rig.saved()["published"]
    package = rig.phone.sent[0]
    rig.phone.say(package["body"], T0 + 32 * 60, mid="pub0", topic=package["url"], tags=[])       # no tag: only the id gives it away
    rig.phone.sent.clear()
    rig.run(T0 + 41 * 60)
    assert rig.parsed == [] and rig.phone.sent == []


def test_a_message_carrying_the_agent_tag_is_never_a_reply(home):
    rig = two_way_rig(home)
    rig.run(T0)
    rig.phone.say("go ahead", T0 + 60, mid="t1", topic=f"{BASE}/odysseus-approvals", tags=["robot"])
    rig.run(T0 + 31 * 60)
    assert rig.parsed == []


def test_the_owner_types_where_the_request_is_and_the_answer_comes_back_to_that_topic(home):
    rig = two_way_rig(home)
    rig.candidates = [cand(task_ref="obsidian-phd:ready/x.md", task_id="x", scope="c" * 64, title="Glovebox shortlist")]
    rig.open_one()
    assert rig.saved()["items"]
    rig.phone.say("go ahead with the glovebox one", T0 + 41 * 60 - 30, mid="o1", topic=f"{BASE}/phd-approvals", tags=[])
    rig.verdicts = [{"target": "glovebox shortlist", "verdict": "yes"}]
    rig.run(T0 + 41 * 60)
    assert rig.phone.sent[-1]["body"].startswith("Understood: approve glovebox shortlist")
    assert rig.phone.sent[-1]["url"] == f"{BASE}/phd-approvals"


def test_switching_to_two_way_resets_the_replay_position_but_keeps_the_queue(home):
    rig = Rig(home)
    rig.open_one()                                                  # one-way: a package is open on the shared topic
    before = rig.saved()
    assert any(i["state"] == "open" for i in before["items"].values()) and before["interrupts"]
    rig.phone.say("go ahead", T0 + 31 * 60 + 30, mid="fresh", topic=f"{BASE}/odysseus-approvals", tags=[])   # untagged, seconds old
    write_routes(home, {"odysseus": "odysseus-approvals"})
    rig.run(T0 + 32 * 60)
    after = rig.saved()
    assert rig.parsed == [] and after["mode"] == "two-way" and after["echo"] is None
    assert all(i["state"] != "open" for i in after["items"].values())          # re-queued to be re-sent to its own topic
    assert after["interrupts"] == before["interrupts"] and set(after["items"]) == set(before["items"])


def test_a_first_cycle_whose_fetch_failed_is_still_the_first(home):
    rig = Rig(home)
    write_routes(home, {"odysseus": "odysseus-approvals"})
    rig.phone.say("go ahead", T0 - 10, mid="seconds-old", topic=f"{BASE}/odysseus-approvals", tags=[])

    def broken(channel, since):
        raise OSError("down")

    real, rig.phone.fetch = rig.phone.fetch, broken
    rig.run(T0)
    assert rig.saved()["started"] is None
    rig.phone.fetch = real
    rig.run(T0 + 60)
    assert rig.parsed == []                                         # recorded without acting, because it is still the first


def test_the_published_ids_are_persisted_bounded_and_validated(home):
    state = home / "inbox.json"
    ids = [f"id{i}" for i in range(ib.MAX_PUBLISHED + 50)] + [7, "x" * 200]
    state.write_text(json.dumps({"owner": "operator", "channel": "c", "published": ids}))
    got = ib._read_state(state)["published"]
    assert len(got) == ib.MAX_PUBLISHED and got[-1] == f"id{ib.MAX_PUBLISHED + 49}" and all(isinstance(x, str) and len(x) <= 80 for x in got)


def test_fetch_two_way_reads_every_topic_and_drops_the_backends_tagged_posts(home, monkeypatch):
    status, channel = ib.load_channel(write_channel(home))
    write_routes(home, {"odysseus": "odysseus-approvals", "misumi": "misumi-approvals"})
    channel = ib.load_channel(home / "ntfy_channel.json")[1]
    lines = {"odysseus-approvals": ['{"event":"message","id":"a1","time":100,"message":"mine","tags":["robot"]}',
                                    '{"event":"message","id":"a2","time":300,"message":"owner one"}'],
             "misumi-approvals": ['{"event":"message","id":"m1","time":200,"message":"owner two","tags":[]}', '{"event":"open"}'],
             "alerts-topic-1234": []}                                                       # the home topic is read too

    class Reply:
        def __init__(self, text):
            self.text = text

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self, n=-1):
            return self.text.encode()

    class Opener:
        def open(self, request, timeout=None):
            return Reply("\n".join(lines[request.full_url.split("/json")[0].rsplit("/", 1)[1]]))

    monkeypatch.setattr(ib, "_opener", lambda: Opener())
    got = ib.fetch_two_way(channel, "all")
    assert [(m["id"], m["topic"].rsplit("/", 1)[1]) for m in got] == [("m1", "misumi-approvals"), ("a2", "odysseus-approvals")]


def test_a_reply_must_come_from_the_topic_its_request_is_waiting_on(home):
    rig = two_way_rig(home)
    rig.candidates = [cand(task_ref="obsidian-phd:ready/x.md", task_id="x", scope="c" * 64, title="Glovebox shortlist")]
    rig.open_one()
    assert [i["topic"] for i in rig.saved()["items"].values() if i["state"] == "open"] == [f"{BASE}/phd-approvals"]
    rig.phone.say("go ahead with the glovebox one", T0 + 41 * 60 - 30, mid="w1", topic=f"{BASE}/misumi-approvals", tags=[])
    rig.verdicts = [{"target": "glovebox shortlist", "verdict": "yes"}]
    rig.run(T0 + 41 * 60)
    assert rig.parsed == [] and rig.phone.sent[-1]["url"] == f"{BASE}/misumi-approvals"
    assert "own topic" in rig.phone.sent[-1]["body"] and rig.saved()["echo"] is None
    rig.phone.say("go ahead with the glovebox one", T0 + 42 * 60, mid="w2", topic=f"{BASE}/phd-approvals", tags=[])
    rig.run(T0 + 43 * 60)
    assert rig.phone.sent[-1]["body"].startswith("Understood: approve glovebox shortlist") and rig.phone.sent[-1]["url"] == f"{BASE}/phd-approvals"


def test_a_stop_command_works_from_any_topic_even_while_a_request_waits_elsewhere(home):
    rig = two_way_rig(home)
    rig.candidates = [cand(task_ref="obsidian-phd:ready/x.md", task_id="x", scope="c" * 64, title="Glovebox shortlist")]
    rig.open_one()
    rig.phone.say("stop advisor approvals", T0 + 40 * 60, mid="s1", topic=f"{BASE}/misumi-approvals", tags=[])
    rig.phone.say("pause", T0 + 41 * 60, mid="s2", topic=f"{BASE}/odysseus-approvals", tags=[])
    rig.run(T0 + 42 * 60)
    assert [d["op"] for d in rig.applied] == ["stop_advisor", "pause_run"] and rig.parsed == []


def test_a_yes_typed_on_another_topic_never_confirms_and_clears_the_pending_echo(home):
    rig = two_way_rig(home)
    rig.candidates = [cand(task_ref="obsidian-phd:ready/x.md", task_id="x", scope="c" * 64, title="Glovebox shortlist")]
    rig.open_one()
    rig.phone.say("go ahead with the glovebox one", T0 + 41 * 60 - 30, mid="a1", topic=f"{BASE}/phd-approvals", tags=[])
    rig.verdicts = [{"target": "glovebox shortlist", "verdict": "yes"}]
    rig.run(T0 + 41 * 60)
    assert rig.saved()["echo"] is not None and rig.saved()["echo"]["armed_at"] is not None          # armed on the phd topic
    rig.phone.say("yes", T0 + 43 * 60, mid="a2", topic=f"{BASE}/misumi-approvals", tags=[])           # the wrong topic
    rig.run(T0 + 44 * 60)
    assert rig.applied == [] and rig.saved()["echo"] is None
    rig.phone.say("yes", T0 + 46 * 60, mid="a3", topic=f"{BASE}/phd-approvals", tags=[])              # now the echo is gone
    rig.run(T0 + 47 * 60)
    assert rig.applied == []


def test_an_open_request_whose_topic_is_no_longer_polled_is_queued_again(home):
    rig = two_way_rig(home)
    rig.candidates = [cand(task_ref="obsidian-phd:ready/x.md", task_id="x", scope="c" * 64, title="Glovebox shortlist")]
    rig.open_one()
    assert [i["topic"] for i in rig.saved()["items"].values() if i["state"] == "open"] == [f"{BASE}/phd-approvals"]
    write_routes(home, {"odysseus": "odysseus-approvals", "misumi": "misumi-approvals"})              # the phd route is gone
    rig.run(T0 + 50 * 60)
    states = [(i["state"], i.get("topic")) for i in rig.saved()["items"].values()]
    assert states == [("queued", None)]


@pytest.mark.parametrize("raw_tags,is_agent", [(None, False), ([], False), (["x"], False), (["robot"], True), (["Robot"], True), ("robot", True),
                                              (["a"] * 33, True), ([1, "x"], True), ({"robot": 1}, True), (["ROBOT", "x"], True)])
def test_tags_fail_closed(home, monkeypatch, raw_tags, is_agent):
    status, channel = ib.load_channel(write_channel(home))
    line = {"event": "message", "id": "m1", "time": 100, "message": "hello"}
    if raw_tags is not None:
        line["tags"] = raw_tags

    class Reply:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self, n=-1):
            return json.dumps(line).encode()

    class Opener:
        def open(self, request, timeout=None):
            return Reply()

    monkeypatch.setattr(ib, "_opener", lambda: Opener())
    got = ib._fetch_topic(channel, f"{BASE}/odysseus-approvals", "all", 5)
    assert (ib.AGENT_TAG in got[0]["tags"]) is is_agent


def test_fetch_two_way_also_reads_the_home_topic_and_asks_only_for_what_is_new(home, monkeypatch):
    write_channel(home, topic="odysseus-approvals")
    write_routes(home, {"misumi": "misumi-approvals"})
    channel = ib.load_channel(home / "ntfy_channel.json")[1]
    asked = []

    class Reply:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self, n=-1):
            return b""

    class Opener:
        def open(self, request, timeout=None):
            asked.append(request.full_url)
            return Reply()

    monkeypatch.setattr(ib, "_opener", lambda: Opener())
    ib.fetch_two_way(channel, "1764147600")
    assert sorted(u.split("/json")[0].rsplit("/", 1)[1] for u in asked) == ["misumi-approvals", "odysseus-approvals"]
    assert all("since=1764147600" in u for u in asked)


def test_the_cycle_asks_the_broker_only_for_messages_since_two_way_mode_started(home, monkeypatch):
    rig = two_way_rig(home)
    seen = []
    monkeypatch.setattr(ib, "fetch_two_way", lambda channel, since: (seen.append(since), [])[1])
    for at in (T0, T0 + 600):
        ib.cycle("operator", gather=lambda: list(rig.candidates), author=lambda c: fields(), parse=rig.parse, apply=rig.apply,
                 digest_facts=lambda: rig.facts, state_path=rig.state, channel_path=rig.channel, clock=lambda at=at: at,
                 transport={"send": rig.phone.send})
    assert seen == [str(int(T0)), str(int(T0))]


# ---- every waiting approval is shown at once; the approval topics carry approvals and nothing else

NEXT_MORNING = datetime(2026, 11, 27, 8, 31, tzinfo=timezone.utc).timestamp()
NIGHT_TIME = datetime(2026, 11, 26, 21, 30, tzinfo=timezone.utc).timestamp()


def many(n):
    return [cand(task_ref=f"odysseus:ready/t{i}.md", task_id=f"t{i}", scope=f"{i}" * 64, title=f"Thing {i}") for i in range(n)]


def test_the_first_cycle_only_records_and_a_waiting_approval_goes_out_the_next_minute(home):
    rig = Rig(home)
    assert rig.run(T0) == "first_run" and rig.phone.sent == []
    assert rig.run(T0 + 2 * 60) == "interrupt"
    sent = rig.phone.sent[0]
    assert sent["priority"] == 4 and sent["title"] == "Approve O1: glovebox shortlist" and ib.fifteen_second_ok(sent["title"], sent["body"])
    assert "CARD: Glovebox shortlist, medium risk" in sent["body"]


def test_every_waiting_approval_is_shown_at_once_and_none_is_held_back_by_an_open_one(home):
    rig = Rig(home)
    rig.candidates = many(4)
    rig.run(T0)
    rig.run(T0 + 2 * 60)
    assert len(rig.phone.sent) == 4 and len({s["title"] for s in rig.phone.sent}) == 4
    assert sorted(i["state"] for i in rig.saved()["items"].values()) == ["open"] * 4


def test_a_long_queue_goes_out_over_a_few_cycles_not_one_at_a_time(home):
    rig = Rig(home)
    rig.candidates = many(8)
    rig.run(T0)
    rig.run(T0 + 2 * 60)
    assert len(rig.phone.sent) == ib.MAX_PACKAGES_PER_CYCLE
    rig.run(T0 + 3 * 60)
    assert len(rig.phone.sent) == 8


def test_there_is_no_daily_cap_and_no_gap_and_a_new_approval_goes_out_straight_away(home):
    rig = Rig(home)
    rig.candidates = many(3)
    rig.run(T0)
    rig.run(T0 + 2 * 60)
    rig.candidates = many(5)                         # two more arrive minutes later
    rig.run(T0 + 5 * 60)
    rig.run(T0 + 7 * 60)
    assert len(rig.phone.sent) == 5


def test_quiet_hours_hold_the_approvals_until_morning_and_then_all_go_out(home):
    rig = Rig(home)
    rig.candidates = many(3)
    rig.run(T0)
    assert rig.run(NIGHT_TIME) == "idle" and rig.phone.sent == []
    rig.run(NEXT_MORNING)
    assert len(rig.phone.sent) == 3


def test_no_digest_and_no_status_message_is_ever_posted(home):
    rig = Rig(home, digest=True)
    rig.candidates = []
    for at in (T0, T0 + 3600, NEXT_MORNING, NEXT_MORNING + 86400):
        rig.run(at)
    assert rig.phone.sent == []
    rig.candidates = many(1)
    rig.run(NEXT_MORNING + 86400 + 3600)
    rig.run(NEXT_MORNING + 86400 + 3700)
    assert [s["title"].startswith("Approve ") for s in rig.phone.sent] == [True]


def test_a_refused_package_is_retried_later_and_does_not_block_the_others(home):
    rig = Rig(home)
    rig.candidates = many(3)
    rig.phone.refuse_sends = 1
    rig.run(T0)
    rig.run(T0 + 2 * 60)
    assert len(rig.phone.sent) == 2                  # one refused, two went out
    rig.run(T0 + 2 * 60 + ib.SEND_RETRY_SECONDS + 60)
    assert len(rig.phone.sent) == 3


def test_a_pending_confirmation_holds_new_packages_on_its_own_topic_only(home):
    rig = two_way_rig(home)
    rig.candidates = [cand(task_ref="obsidian-phd:ready/x.md", task_id="x", scope="c" * 64, title="Glovebox shortlist")]
    rig.open_one()
    rig.phone.say("go ahead with the glovebox one", T0 + 41 * 60 - 30, mid="e1", topic=f"{BASE}/phd-approvals", tags=[])
    rig.verdicts = [{"target": "glovebox shortlist", "verdict": "yes"}]
    rig.run(T0 + 41 * 60)
    assert rig.saved()["echo"] and rig.saved()["echo"]["armed_at"] is not None
    rig.phone.sent.clear()
    rig.candidates += [cand(task_ref="obsidian-phd:ready/y.md", task_id="y", scope="d" * 64, title="Second phd thing"),
                       cand(task_ref="misumi:ready/m.md", task_id="m", scope="e" * 64, title="Misumi thing")]
    rig.run(T0 + 42 * 60)
    rig.run(T0 + 43 * 60)
    assert [s["url"] for s in rig.phone.sent] == [f"{BASE}/misumi-approvals"]               # the phd topic waits, misumi does not
    rig.run(T0 + 41 * 60 + ib.ECHO_TTL_SECONDS + 120)
    assert sorted(s["url"] for s in rig.phone.sent) == [f"{BASE}/misumi-approvals", f"{BASE}/phd-approvals"]


def test_a_package_whose_post_timed_out_is_offered_once_more_if_nothing_came_of_it(home):
    rig = Rig(home)
    rig.phone.fail_sends = 1                                     # the post times out: the outcome is unknown
    rig.run(T0)
    assert "interrupt_unconfirmed" in rig.run(T0 + 2 * 60)
    item = next(iter(rig.saved()["items"].values()))
    assert item["state"] == "open" and item["unconfirmed_at"]
    rig.run(T0 + 2 * 60 + ib.UNCONFIRMED_RESEND_SECONDS + 60)    # still unanswered: back to the queue
    assert next(iter(rig.saved()["items"].values()))["state"] in ("queued", "open")
    rig.run(T0 + 2 * 60 + ib.UNCONFIRMED_RESEND_SECONDS + 180)
    assert len(rig.phone.sent) == 1 and next(iter(rig.saved()["items"].values()))["state"] == "open"
    assert "unconfirmed_at" not in next(iter(rig.saved()["items"].values())) or not next(iter(rig.saved()["items"].values()))["unconfirmed_at"]


def test_authoring_attempts_are_bounded_per_cycle(home):
    rig = Rig(home)
    rig.candidates = many(13)
    authored = []

    def author(candidate):
        authored.append(candidate["task_id"])
        return fields()

    for at in (T0, T0 + 2 * 60):
        ib.cycle("operator", gather=lambda: list(rig.candidates), author=author, parse=rig.parse, apply=rig.apply,
                 digest_facts=lambda: rig.facts, state_path=rig.state, channel_path=rig.channel, clock=lambda at=at: at,
                 transport={"send": rig.phone.send, "fetch": rig.phone.fetch})
    assert len(authored) == ib.MAX_PACKAGES_PER_CYCLE and len(rig.phone.sent) == ib.MAX_PACKAGES_PER_CYCLE


def test_a_broker_that_keeps_timing_out_cannot_make_a_package_repeat_forever(home):
    rig = Rig(home)
    rig.phone.fail_sends = 50                                    # every post times out
    at = T0
    rig.run(at)
    for _ in range(8):
        at += ib.UNCONFIRMED_RESEND_SECONDS + 120
        rig.run(at)
        rig.run(at + 60)
    posts_attempted = 50 - rig.phone.fail_sends
    assert posts_attempted == 2                                  # the first post and exactly one resend
    assert next(iter(rig.saved()["items"].values()))["state"] in ("open", "parked")


def test_the_fallback_never_posts_into_the_topic_a_pending_confirmation_owns(home):
    rig = two_way_rig(home)
    write_channel(home, topic="odysseus-approvals")                  # as in production: the home topic IS the odysseus approvals topic
    write_routes(home, {"odysseus": "odysseus-approvals", "obsidian-phd": "phd-approvals", "misumi": "misumi-approvals"})
    rig.candidates = [cand(task_ref="odysseus:ready/x.md", task_id="x", scope="c" * 64, title="Deploy it")]
    rig.open_one()
    rig.phone.say("go ahead with deploy", T0 + 41 * 60 - 30, mid="h1", topic=f"{BASE}/odysseus-approvals", tags=[])
    rig.verdicts = [{"target": "deploy it", "verdict": "yes"}]
    rig.run(T0 + 41 * 60)
    assert rig.saved()["echo"]["armed_at"] is not None
    rig.phone.sent.clear()
    rig.candidates += [cand(task_ref="obsidian-phd:ready/y.md", task_id="y", scope="d" * 64, title="Phd thing")]
    rig.phone.refuse_sends = 1                                    # the routed phd post is refused: the fallback target is the held home topic
    rig.run(T0 + 42 * 60)
    rig.run(T0 + 43 * 60)
    assert all(s["url"] != f"{BASE}/odysseus-approvals" for s in rig.phone.sent) and rig.phone.sent == []     # refused, held, not posted


def test_thirteen_open_requests_with_the_same_title_still_get_distinct_names(home):
    rig = Rig(home)
    rig.candidates = [cand(task_ref=f"odysseus:ready/t{i}.md", task_id=f"t{i}", scope=f"{i:x}" * 64, title="Same title") for i in range(13)]
    for at in (T0, T0 + 2 * 60, T0 + 3 * 60, T0 + 4 * 60):
        rig.run(at)
    names = [i["name"] for i in rig.saved()["items"].values() if i["state"] == "open"]
    assert len(names) == 13 and len(set(names)) == 13


# ---- a request a person can understand in thirty seconds: what, consequences, scope, why you, advice

CTX = {"title": "Pay for the supplier trial", "what": "Order trial gloves", "kind": "implementation", "priority": "high", "risk": "high",
       "owner_gate_class": "financial", "write_paths": ["docs/**", "tests/**", "src/**"], "denied_count": 9, "scope_changed": False,
       "goal": "Order a trial batch of gloves from the shortlisted supplier.", "done": ["A trial batch is ordered"], "risks_text": ["Money is spent"]}


def test_the_message_has_a_fixed_readable_layout_that_fits_one_screen():
    title, body = ib.assemble(fields(), "Glovebox shortlist, medium risk", ib.card_brief(cand(context=CTX)))
    labels = [line.split(":", 1)[0] for line in body.splitlines()]
    assert labels[:3] == ["WHAT", "IF YES", "IF NO"] and "SCOPE" in labels and labels.index("WHY YOU") < labels.index("ADVICE") < labels.index("CARD")
    assert body.splitlines()[-1] == "Reply yes, no, later, or ask a question."
    assert len(body) <= ib.MAX_BODY and body.count("\n") + 1 <= ib.MAX_LINES and ib.fifteen_second_ok(title, body)


def test_where_agents_may_write_is_built_from_the_card_not_from_the_model():
    assert ib.scope_line(CTX, "Odysseus") == "agents may change documents, tests and code in the Odysseus repository; 9 protected areas stay off limits."
    assert ib.scope_line({"write_paths": []}, "PhD") == "the card does not list where agents may write."
    assert ib.scope_line({"write_paths": ["zzz/**"]}, None) == "agents may change files in zzz."
    assert ib.scope_line({"write_paths": ["../../etc/passwd", "src/x.py"]}, "Odysseus") == "agents may change anything in the Odysseus repository."


def test_why_it_reached_the_owner_names_the_rule_that_triggered_it():
    assert ib.why_you(CTX) == ("Only you can decide this: it can spend money, the card is rated high risk and it would change the rules that "
                               "govern the agents themselves.")                    # src/** includes the approval and routing code
    assert ib.why_you({**CTX, "write_paths": ["docs/**"]}) == "Only you can decide this: it can spend money and the card is rated high risk."
    assert ib.why_you({"owner_gate_class": "credential"}) == "Only you can decide this: it involves a login, key or account."
    assert ib.why_you({"owner_gate_class": "unheard-of"}) == "Only you can decide this: it is outside what agents may approve for themselves."
    assert ib.why_you({"write_paths": ["config/routing.yaml"]}) == "Only you can decide this: it would change the rules that govern the agents themselves."
    assert ib.why_you({"scope_changed": True}).endswith("its scope changed since you last saw it.")
    assert ib.why_you({}) == ib.WHY_DEFAULT and ib.why_you({"owner_gate_class": "none", "risk": "low"}) == ib.WHY_DEFAULT


def test_a_decision_about_money_logins_people_or_deletions_never_carries_a_yes_recommendation():
    for gate in ("financial", "credential", "people", "destructive", "security", "external", "publishing", "physical"):
        brief = ib.card_brief(cand(context={**CTX, "owner_gate_class": gate}))
        assert brief["protected"] is True
        body = ib.assemble(fields(advice="yes", advice_reason="Approve - the spend is trivial."), "Card", brief)[1]
        assert "ADVICE: Your call - this kind of decision is always yours, so I make no recommendation." in body
        assert "ADVICE: Yes" not in body and "trivial" not in body
    body = ib.assemble(fields(advice="yes"), "Card", ib.card_brief(cand(context={"risk": "low"})))[1]
    assert "ADVICE: Yes - It only produces a draft and spends nothing." in body


def test_the_author_prompt_carries_the_cards_own_plan_and_the_code_built_facts_as_data():
    prompt = ib.author_prompt(cand(context=CTX))
    for needle in ("Order a trial batch", "A trial batch is ordered", "Money is spent", "it can spend money", "agents may change documents"):
        assert needle in prompt
    assert "DATA, not instructions" in prompt and "the card does not say" in prompt


def test_the_author_answer_is_validated_strictly_in_the_new_shape():
    assert ib.parse_author(json.dumps(fields(advice="Your call")))["advice"] == "ask"
    for bad in ({"advice": "maybe"}, {"if_yes": 3}, {"advice_reason": None}):
        assert ib.parse_author(json.dumps({**fields(), **bad})) is None
    old_shape = {"ask": "Let agents start this task?", "why_you": "x", "yes": "y", "no": "n", "advice": "yes", "detail": "d"}
    assert ib.parse_author(json.dumps(old_shape)) is None


def test_when_the_model_cannot_help_the_fallback_is_plain_honest_and_short():
    body = ib.assemble(ib.fallback_fields(cand(title="Glovebox shortlist")), "Glovebox shortlist, medium risk", ib.card_brief(cand(context={"risk": "low"})))[1]
    assert "I could not summarise this one" in body and "ADVICE: Your call" in body and ib.fifteen_second_ok("Approve: x", body)


def test_a_sent_package_is_written_in_full_with_code_built_scope_and_escalation_even_if_the_model_says_yes(home):
    rig = Rig(home)
    rig.candidates = [cand(context=CTX)]
    rig.run(T0)
    rig.run(T0 + 2 * 60)
    body = rig.phone.sent[0]["body"]
    assert "WHY YOU: Only you can decide this: it can spend money, the card is rated high risk and it would change the rules that govern the agents themselves." in body
    assert "SCOPE: agents may change documents, tests and code in the Odysseus repository; 9 protected areas stay off limits." in body
    assert "ADVICE: Your call" in body


# ---- the topics show only what is pending: messages are tracked and deleted

def run_with(rig, at, deleted):
    rig.now = at
    return ib.cycle("operator", gather=lambda: list(rig.candidates), author=lambda c: fields(), parse=rig.parse, apply=rig.apply,
                    digest_facts=lambda: rig.facts, state_path=rig.state, channel_path=rig.channel, clock=lambda: rig.now,
                    transport={"send": rig.phone.send, "fetch": rig.phone.fetch, "delete": lambda ch, url, msg: deleted.append((url, msg)) or True})


def test_each_request_remembers_the_message_that_shows_it_and_its_layout(home):
    rig = Rig(home)
    rig.run(T0)
    rig.run(T0 + 2 * 60)
    item = next(iter(rig.saved()["items"].values()))
    assert item["msg"] == "pub0" and item["fmt"] == ib.PACKAGE_FORMAT and item["state"] == "open"


def test_an_answered_request_has_its_message_deleted(home):
    rig = Rig(home)
    deleted = []
    run_with(rig, T0, deleted)
    run_with(rig, T0 + 2 * 60, deleted)
    assert deleted == []
    rig.phone.say("no thanks", T0 + 5 * 60)
    rig.verdicts = [{"target": "glovebox shortlist", "verdict": "no"}]
    run_with(rig, T0 + 6 * 60, deleted)
    assert deleted == []                                          # the owner sees the confirmation first
    run_with(rig, T0 + 6 * 60 + ib.RESOLVED_PURGE_DELAY + 60, deleted)
    assert sorted(m for _, m in deleted) == ["pub0", "pub1"] and rig.saved()["retire"] == []      # the package and the acknowledgement


def test_a_withdrawn_request_has_its_message_deleted_too(home):
    rig = Rig(home)
    deleted = []
    run_with(rig, T0, deleted)
    run_with(rig, T0 + 2 * 60, deleted)
    rig.candidates = []                                   # resolved elsewhere
    run_with(rig, T0 + 4 * 60, deleted)
    assert [m for _, m in deleted] == ["pub0"]


def test_a_failed_delete_is_retried_a_few_times_then_dropped(home):
    rig = Rig(home)
    calls = []

    def run(at):
        rig.now = at
        return ib.cycle("operator", gather=lambda: list(rig.candidates), author=lambda c: fields(), parse=rig.parse, apply=rig.apply,
                        digest_facts=lambda: rig.facts, state_path=rig.state, channel_path=rig.channel, clock=lambda: rig.now,
                        transport={"send": rig.phone.send, "fetch": rig.phone.fetch, "delete": lambda ch, url, msg: calls.append(msg) and False})

    run(T0)
    run(T0 + 2 * 60)
    rig.candidates = []
    for n in range(10):
        run(T0 + (4 + n) * 60)
    assert len(calls) == 5 and rig.saved()["retire"] == []


def test_a_request_shown_in_an_older_layout_is_shown_again_in_the_current_one(home):
    rig = Rig(home)
    rig.run(T0)
    rig.run(T0 + 2 * 60)
    state = rig.saved()
    for item in state["items"].values():
        item.pop("fmt", None)                            # as sent by the previous version
        item["msg"] = None
    rig.state.write_text(json.dumps(state))
    rig.phone.sent.clear()
    rig.run(T0 + 4 * 60)
    rig.run(T0 + 6 * 60)
    assert len(rig.phone.sent) == 1 and "WHAT:" in rig.phone.sent[0]["body"]
    assert next(iter(rig.saved()["items"].values()))["fmt"] == ib.PACKAGE_FORMAT


def test_delete_message_only_touches_the_brokers_own_topics_and_valid_ids(monkeypatch):
    import urllib.error
    channel = {"user": "u", "password": "p", "base": BASE}
    seen = []

    class Reply:
        def __init__(self, status):
            self.status = status

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    outcome = {"status": 200}

    class Opener:
        def open(self, request, timeout=None):
            seen.append((request.get_method(), request.full_url))
            if outcome["status"] >= 400:
                raise urllib.error.HTTPError(request.full_url, outcome["status"], "x", {}, None)
            return Reply(outcome["status"])

    monkeypatch.setattr(ib, "_opener", lambda: Opener())
    assert ib.delete_message(channel, f"{BASE}/odysseus-approvals", "abc123") is True
    assert seen == [("DELETE", f"{BASE}/odysseus-approvals/abc123")]
    outcome["status"] = 404
    assert ib.delete_message(channel, f"{BASE}/odysseus-approvals", "abc123") is True            # already gone
    outcome["status"] = 500
    assert ib.delete_message(channel, f"{BASE}/odysseus-approvals", "abc123") is False
    before = len(seen)
    for url, msg in ((f"{BASE}/x", "../etc"), (f"{BASE}/x", "a/b"), (f"{BASE}/x", ""), ("http://evil.example/x", "abc"), (f"{BASE}/x", None)):
        assert ib.delete_message(channel, url, msg) is False
    assert len(seen) == before


def test_the_retire_list_is_validated_when_read(home):
    state = home / "inbox.json"
    state.write_text(json.dumps({"owner": "operator", "channel": "c", "retire": [
        {"url": f"{BASE}/t", "msg": "ok1", "tries": 2}, {"url": f"{BASE}/t", "msg": "bad/id"}, {"url": 5, "msg": "x"}, "junk",
        {"url": "u" * 300, "msg": "ok2"}]}))
    got = ib._read_state(state)["retire"]
    assert got == [{"url": f"{BASE}/t", "msg": "ok1", "tries": 2, "due": 0.0}]


def test_text_is_cut_at_a_sentence_or_a_word_never_in_the_middle_of_one():
    assert ib._clip("Short.", 50) == "Short."
    assert ib._clip("First sentence is here. Second sentence runs on and on.", 40) == "First sentence is here."
    clipped = ib._clip("This keeps going without any full stop at all so it must be cut at a word", 40)
    assert clipped.endswith("...") and " " + clipped[:-3].rsplit(" ", 1)[-1] in " " + "This keeps going without any full stop at all so it must be cut at a word"
    assert not ib._clip("Harden cross-device delegation and the lifecycle of the long running thing", 41).rstrip(".").endswith((" and", " the", " of"))
    assert len(ib._clip("word " * 100, 60)) <= 63


def test_a_long_but_good_model_answer_is_trimmed_to_fit_one_screen_not_rejected():
    long = {"what": "A sentence that is long. " * 20, "if_yes": "It changes a great many things in many places. " * 10,
            "if_no": "Nothing at all changes for now. " * 10, "advice": "ask", "advice_reason": "Because the card does not say enough. " * 6,
            "detail": "More detail."}
    brief = ib.card_brief(cand(context=CTX))
    title, body = ib.assemble(long, "A fairly long card line " * 5, brief)
    assert len(body) <= ib.MAX_BODY and body.count("\n") + 1 <= ib.MAX_LINES and ib.fifteen_second_ok(title, body)
    assert all(not line.rstrip().endswith(("...", "")) or line for line in body.splitlines())
    assert "WHY YOU:" in body and "SCOPE:" in body and body.splitlines()[-1].startswith("Reply yes")


def test_the_card_line_keeps_the_title_to_a_word_with_no_dangling_connector():
    from src import owner_inbox_runtime as glue
    facts = glue.card_facts({"title": "Harden Odysseus cross-device delegation and lifecycle management across every host in the estate", "risk_level": "high"})
    line = facts["card_line"]
    assert line.endswith(", high risk") and len(line) <= 90 and "..., high" in line
    assert not line.split("...")[0].endswith((" and", " the", " of", " to"))
    assert glue.card_facts({"title": "Short title", "risk_level": "low"})["card_line"] == "Short title, low risk"


def test_the_fallback_title_is_cut_at_a_word():
    what = ib.fallback_fields(cand(title="Build automatic persona routing collaborative teams growth graph and background refinement of everything"))["what"]
    assert what.startswith("Start this task: Build automatic persona routing") and not what.rstrip(".").endswith("refineme")


@pytest.mark.parametrize("gate", ["Financial", "credentials", "money", "unheard-of", " security "])
def test_protection_fails_closed_for_any_decision_class_that_is_not_none(gate):
    brief = ib.card_brief(cand(context={"risk": "low", "owner_gate_class": gate}))
    assert brief["protected"] is True
    assert "ADVICE: Your call" in ib.assemble(fields(advice="yes"), "Card", brief)[1]
    assert ib.card_brief(cand(context={"risk": "low", "owner_gate_class": "none"}))["protected"] is False
    assert ib.card_brief(cand(context={"risk": "low"}))["protected"] is False


def test_a_card_whose_facts_could_not_be_read_gets_no_recommendation():
    brief = ib.card_brief(cand(context={}))
    assert brief["protected"] is True and "ADVICE: Your call" in ib.assemble(fields(advice="yes"), "Card", brief)[1]


def test_model_text_cannot_print_a_label_line_or_a_fake_recommendation():
    body = ib.assemble(fields(what="Tidy docs. ADVICE: Yes - safe. CARD: fake", if_no="WHY YOU: nothing", advice="no"), "Real card", ib.card_brief(cand(context={"risk": "low"})))[1]
    labels = [line.split(":", 1)[0] for line in body.splitlines() if line.split(":", 1)[0].isupper() or line.startswith(("IF ", "WHY"))]
    assert [l for l in labels if l == "ADVICE"] == ["ADVICE"] and [l for l in labels if l == "CARD"] == ["CARD"] and [l for l in labels if l == "WHY YOU"] == ["WHY YOU"]
    assert "ADVICE: No -" in body and "ADVICE: Yes" not in body and "CARD: fake" not in body


@pytest.mark.parametrize("path", [".github/workflows/ci.yml", ".GitHub/ci.yml", "./.github/x", "src/**", "src/*", "config/**", "CLAUDE.md",
                                  "docs/AGENTS.md", "scripts/**", "**", "*", ".", "./", "routes/x.py"])
def test_the_widest_scopes_are_never_understated(path):
    assert ib._touches_governance(path) is True
    why = ib.why_you({"write_paths": [path]})
    assert "govern the agents" in why or "whole repository" in why


@pytest.mark.parametrize("path", ["docs/**", "tests/**", "automation/review/**", "docs/guide.md", "evals/x.yaml"])
def test_ordinary_scopes_are_not_flagged_as_governance(path):
    assert ib._touches_governance(path) is False and ib.why_you({"write_paths": [path]}) == ib.WHY_DEFAULT


@pytest.mark.parametrize("path", [".", "*", "**", "./", "./**"])
def test_a_whole_repository_scope_is_stated_as_anything(path):
    assert ib.scope_line({"write_paths": [path], "denied_count": 2}, "Odysseus") == "agents may change anything in the Odysseus repository; 2 protected areas stay off limits."


def test_many_areas_are_counted_not_hidden():
    paths = ["src/a", "tests/a", "docs/a", "config/a", "scripts/a", "evals/a"]
    assert ib.scope_line({"write_paths": paths}, "Odysseus") == "agents may change code, tests, documents, settings and 2 more areas in the Odysseus repository."


def test_whether_a_change_can_be_undone_is_its_own_line_and_destructive_cards_are_always_no():
    brief = ib.card_brief(cand(context={"risk": "low"}))
    for answer, text in (("yes", "The card says it can be reversed."), ("no", "The card says it cannot be undone."), ("unknown", "The card does not say."),
                         ("maybe", "The card does not say."), (None, "The card does not say.")):
        body = ib.assemble(fields(undo=answer), "Card", brief)[1]
        assert f"UNDO: {text}" in body
    body = ib.assemble(fields(undo="yes"), "Card", ib.card_brief(cand(context={"risk": "low", "owner_gate_class": "destructive"})))[1]
    assert "UNDO: No, treat it as permanent." in body
    long = {"what": "A long first sentence. " * 15, "if_yes": "Merges to main. This cannot be undone. " * 8, "if_no": "Nothing. " * 20, "advice": "ask",
            "advice_reason": "x " * 80, "undo": "no", "detail": "d"}
    assert "UNDO: The card says it cannot be undone." in ib.assemble(long, "Card", brief)[1]        # shrinking can never drop it


def test_the_author_may_leave_undo_out():
    parsed = ib.parse_author(json.dumps(fields()))
    assert parsed is not None and parsed["undo"] == "unknown"
    assert ib.parse_author(json.dumps(fields(undo="YES")))["undo"] == "yes"


def test_deletions_are_bounded_per_cycle_and_an_unpolled_topics_message_is_retired(home):
    rig = Rig(home)
    deleted = []
    run_with(rig, T0, deleted)
    run_with(rig, T0 + 2 * 60, deleted)
    state = rig.saved()
    state["retire"] = [{"url": f"{BASE}/t", "msg": f"m{i}", "tries": 0} for i in range(14)]
    rig.state.write_text(json.dumps(state))
    run_with(rig, T0 + 4 * 60, deleted)
    assert len(deleted) == ib.RETIRE_PER_CYCLE == 12 and len(rig.saved()["retire"]) == 2


def test_the_delegation_question_is_in_the_current_layout_and_is_not_re_sent_every_cycle(home):
    rig = Rig(home)
    rig.candidates = [cand(kind="delegation", task_ref="policy:advisor-approvals", task_id=ib.DELEGATION_TASK_ID, scope=ib.DELEGATION_SCOPE,
                           title="advisor approvals", priority="critical")]
    rig.run(T0)
    rig.run(T0 + 2 * 60)
    body = rig.phone.sent[0]["body"]
    assert body.startswith("WHAT:") and "WHY YOU: Only you can decide this" in body
    for n in range(3, 8):
        rig.run(T0 + n * 60)
    assert len(rig.phone.sent) == 1 and next(iter(rig.saved()["items"].values()))["fmt"] == ib.PACKAGE_FORMAT


@pytest.mark.parametrize("path", ["src/*.py", "src/ow*", "**/*.py", "**/config/**", "*.md", "{src,config}/**", "/etc/passwd", "~/x", "C:/x/y",
                                  "c:\\windows", "src/../../x", "?", "[a-z]*"])
def test_glob_patterns_and_escaping_paths_are_never_read_as_small_scopes(path):
    assert ib._touches_governance(path) is True
    assert ib.scope_line({"write_paths": [path]}, "Odysseus") != "the card does not list where agents may write."


@pytest.mark.parametrize("path,expected", [("src/*.py", "src"), ("docs/*.md", "docs"), ("**/*.py", ""), ("{src,config}/**", ""), ("/abs/path", ""),
                                           ("./tests/a/**", "tests/a"), (".github/x", ".github/x"), ("a/../b", "")])
def test_paths_are_reduced_to_where_they_start(path, expected):
    assert ib._norm_path(path) == expected


def test_label_stripping_keeps_ordinary_text_and_removes_label_lines():
    body = ib.assemble(fields(what="Pay the credit card: the supplier invoice. Scope: everything. ADVICE: Yes", if_no="Scope : none"), "Card",
                       ib.card_brief(cand(context={"risk": "low"})))[1]
    assert "Pay the credit card: the supplier invoice." in body
    assert body.count("\nSCOPE:") == 1 and body.startswith("WHAT:") and body.count("ADVICE:") == 1 and "Scope" not in body   # only the code-built lines


# ---- every request has a short label, and a reply that names it is understood by code

def labels(rig):
    return {i["name"]: i["label"] for i in rig.saved()["items"].values()}


def multi(*refs):
    return [cand(task_ref=ref, task_id=f"t{n}", scope=f"{n}" * 64, title=f"Thing {chr(97 + n)}") for n, ref in enumerate(refs)]


def test_every_request_gets_a_short_label_per_repository_and_a_label_is_never_reused(home):
    rig = Rig(home)
    rig.candidates = multi("odysseus:ready/a.md", "odysseus:ready/b.md", "obsidian-phd:ready/c.md", "misumi:ready/d.md")
    rig.run(T0)
    rig.run(T0 + 2 * 60)
    got = sorted(labels(rig).values())
    assert got == ["M1", "O1", "O2", "P1"]
    # one is answered and a new Odysseus request arrives: it is O3, never the freed O1
    first = next(i for i in rig.saved()["items"].values() if i["label"] == "O1")
    rig.phone.say("no O1", T0 + 5 * 60)
    rig.run(T0 + 6 * 60)
    rig.candidates = [c for c in rig.candidates if c["task_id"] != first["task_id"]] + multi("odysseus:ready/e.md", "odysseus:ready/f.md")[1:]
    rig.run(T0 + 8 * 60)
    rig.run(T0 + 10 * 60)
    assert "O3" in labels(rig).values() and list(labels(rig).values()).count("O1") == 1


def test_the_title_and_the_reply_hint_carry_the_label(home):
    rig = Rig(home)
    rig.run(T0)
    rig.run(T0 + 2 * 60)
    sent = rig.phone.sent[0]
    assert sent["title"] == "Approve O1: glovebox shortlist"
    assert sent["body"].splitlines()[-1] == "Reply: approve O1, no O1, later O1, or O1? to ask."


def test_the_advisor_delegation_question_is_labelled_too(home):
    rig = Rig(home)
    rig.candidates = [cand(kind="delegation", task_ref="policy:advisor-approvals", task_id=ib.DELEGATION_TASK_ID, scope=ib.DELEGATION_SCOPE,
                           title="advisor approvals", priority="critical")]
    rig.run(T0)
    rig.run(T0 + 2 * 60)
    sent = rig.phone.sent[0]
    assert sent["title"] == "Decide S1: advisor approvals" and sent["body"].splitlines()[-1] == "Reply: approve S1, no S1, later S1, or S1? to ask."
    assert ib.fifteen_second_ok(sent["title"], sent["body"])


@pytest.mark.parametrize("text", ["approve O1", "Approve o1.", "yes O1", "O1 yes", "#O1 approve", "go ahead O1", "approve O1 please",
                                  "please approve O1", "confirm for O1", "O1: yes", "approve #O1!"])
def test_a_reply_naming_the_label_approves_at_once_with_no_further_confirmation(home, text):
    rig = Rig(home)
    rig.open_one()
    rig.phone.say(text, T0 + 41 * 60 - 30)
    rig.run(T0 + 41 * 60)
    assert [d["op"] for d in rig.applied] == ["approve"] and rig.applied[0]["confirmed"] is True
    assert rig.parsed == [] and rig.saved()["echo"] is None                        # read by code, not by a model, and nothing left to confirm


@pytest.mark.parametrize("text,op", [("no O1", "decline"), ("decline O1", "decline"), ("O1 no", "decline"), ("reject O1", "decline"),
                                     ("later O1", "defer"), ("O1 later", "defer"), ("not yet O1", "defer"), ("snooze O1", "defer")])
def test_declining_or_postponing_by_label_applies_at_once(home, text, op):
    rig = Rig(home)
    rig.open_one()
    rig.phone.say(text, T0 + 41 * 60 - 30)
    rig.run(T0 + 41 * 60)
    assert [d["op"] for d in rig.applied] == [op] and rig.parsed == []


@pytest.mark.parametrize("text", ["O1?", "o1 ?", "what is O1", "explain O1", "why O1?", "details on O1"])
def test_asking_about_a_label_answers_from_the_stored_detail_and_changes_nothing(home, text):
    rig = Rig(home)
    rig.open_one()
    rig.phone.say(text, T0 + 41 * 60 - 30)
    rig.run(T0 + 41 * 60)
    assert rig.applied == [] and rig.phone.sent[-1]["body"].startswith("Agents compare glovebox options")


def test_a_label_that_is_not_open_here_changes_nothing_and_says_what_is(home):
    rig = Rig(home)
    rig.open_one()
    rig.phone.say("approve O9", T0 + 41 * 60 - 30)
    rig.run(T0 + 41 * 60)
    assert rig.applied == [] and rig.phone.sent[-1]["body"] == "I do not see O9 open here. Open here: O1."


def test_a_label_picks_exactly_that_request_among_several(home):
    rig = Rig(home)
    rig.candidates = multi("odysseus:ready/a.md", "odysseus:ready/b.md", "odysseus:ready/c.md")
    rig.run(T0)
    rig.run(T0 + 2 * 60)
    target = next(i for i in rig.saved()["items"].values() if i["label"] == "O2")
    rig.phone.say("approve O2", T0 + 5 * 60)
    rig.run(T0 + 6 * 60)
    assert rig.applied == [{"op": "approve", "item": target["id"], "confirmed": True}]


def test_free_text_around_a_label_is_not_read_by_code_but_a_list_of_decisions_is(home):
    rig = Rig(home)
    rig.candidates = multi("odysseus:ready/a.md", "odysseus:ready/b.md")
    rig.run(T0)
    rig.run(T0 + 2 * 60)
    rig.phone.say("yes O1 but only the docs part", T0 + 5 * 60 + 5)
    rig.run(T0 + 6 * 60)
    assert rig.applied == [] and len(rig.parsed) == 1                                # free text went to the model path, which asks, never approves
    rig.phone.say("approve O1 and O2", T0 + 7 * 60)                                  # a plain list of labelled decisions is read by code
    rig.run(T0 + 8 * 60)
    assert [d["op"] for d in rig.applied] == ["approve", "approve"] and len(rig.parsed) == 1


def test_a_bare_yes_still_needs_the_confirmed_flow_even_when_one_request_is_open(home):
    rig = Rig(home)
    rig.open_one()
    rig.phone.say("yes", T0 + 41 * 60 - 30)
    rig.run(T0 + 41 * 60)
    assert rig.applied == [] and rig.parsed == ["yes"]


def test_the_confirmation_echo_names_the_label_for_free_text_approvals(home):
    rig = Rig(home)
    rig.open_one()
    rig.phone.say("go ahead with the glovebox one", T0 + 41 * 60 - 30)
    rig.verdicts = [{"target": "glovebox shortlist", "verdict": "yes"}]
    rig.run(T0 + 41 * 60)
    assert rig.phone.sent[-1]["body"].startswith("Understood: approve glovebox shortlist [O1] (")


def test_the_model_may_name_the_request_by_its_label(home):
    rig = Rig(home)
    rig.open_one()
    rig.phone.say("go ahead with that first one please", T0 + 41 * 60 - 30)
    rig.verdicts = [{"target": "o1", "verdict": "yes"}]
    rig.run(T0 + 41 * 60)
    assert rig.phone.sent[-1]["body"].startswith("Understood: approve glovebox shortlist [O1]")


def test_the_reply_prompt_shows_the_labels():
    item = {"id": "a" * 12, "name": "glovebox shortlist", "label": "O1", "ask": "Let agents start?"}
    prompt = ib.reply_prompt("approve it", [item], None)
    assert '"label": "O1"' in prompt and "label (for example P2) or name" in prompt
    assert ib.parse_reply(json.dumps({"target": "o1", "verdict": "yes", "condition": False, "confidence": 0.9}), {"glovebox shortlist", "o1"})["target"] == "o1"


def test_a_label_on_another_topic_is_not_visible_here(home):
    rig = two_way_rig(home)
    rig.candidates = multi("odysseus:ready/a.md", "obsidian-phd:ready/b.md")
    rig.run(T0)
    rig.run(T0 + 2 * 60)
    rig.phone.say("approve P1", T0 + 5 * 60, topic=f"{BASE}/odysseus-approvals", tags=[])           # P1 lives on the phd topic
    rig.run(T0 + 6 * 60)
    assert rig.applied == [] and rig.phone.sent[-1]["body"] == "I do not see P1 open here. Open here: O1."
    rig.phone.say("approve P1", T0 + 7 * 60, topic=f"{BASE}/phd-approvals", tags=[])
    rig.run(T0 + 8 * 60)
    assert [d["op"] for d in rig.applied] == ["approve"]


def test_a_request_keeps_its_label_when_it_is_shown_again(home):
    rig = Rig(home)
    rig.open_one()
    before = labels(rig)
    state = rig.saved()
    for item in state["items"].values():
        item["fmt"] = ib.PACKAGE_FORMAT - 1                  # shown in an older layout
    rig.state.write_text(json.dumps(state))
    rig.run(T0 + 50 * 60)
    rig.run(T0 + 52 * 60)
    assert labels(rig) == before == {"glovebox shortlist": "O1"} and "O1" in rig.phone.sent[-1]["title"]


def test_the_label_counters_are_validated_when_read(home):
    state = home / "inbox.json"
    state.write_text(json.dumps({"owner": "operator", "channel": "c", "labels": {"O": 3, "p": 2, "PP": 1, "M": -1, "S": True, "X": 99999999, "Q": "5", "D": 7}}))
    assert ib._read_state(state)["labels"] == {"O": 3, "D": 7}


@pytest.mark.parametrize("text", ["approve 1", "do it 2", "1 yes", "no 1", "later #3", "approve \uff11"])
def test_a_bare_number_never_applies_and_gets_a_hint(home, text):
    rig = Rig(home)
    rig.open_one()
    rig.phone.say(text, T0 + 41 * 60 - 30)
    rig.run(T0 + 41 * 60)
    assert rig.applied == [] and rig.saved()["items"]
    last = rig.phone.sent[-1]["body"]
    expected = "Use the full label" if text != "approve \uff11" else None
    assert rig.parsed == [] or text == "approve \uff11"
    if expected:
        assert last.startswith(expected)


def test_a_number_on_one_topic_can_never_approve_another_repositorys_request(home):
    rig = two_way_rig(home)
    rig.candidates = multi("odysseus:ready/a.md", "obsidian-phd:ready/b.md")
    rig.run(T0)
    rig.run(T0 + 2 * 60)
    for item in rig.saved()["items"].values():
        pass
    rig.phone.say("approve 1", T0 + 5 * 60, topic=f"{BASE}/odysseus-approvals", tags=[])
    rig.run(T0 + 6 * 60)
    assert rig.applied == []


def test_a_decision_typed_before_the_current_version_was_sent_is_refused(home):
    rig = Rig(home)
    rig.open_one()
    sent_at = next(iter(rig.saved()["items"].values()))["sent_at"]
    rig.phone.say("approve O1", sent_at - 20)
    rig.run(T0 + 41 * 60)
    assert rig.applied == [] and "was sent again after your message" in rig.phone.sent[-1]["body"]


def test_a_changed_card_is_a_new_request_with_a_new_label(home):
    rig = Rig(home)
    rig.open_one()
    assert labels(rig) == {"glovebox shortlist": "O1"}
    rig.candidates = [cand(fp="e" * 64)]                              # the card changed
    rig.run(T0 + 45 * 60)
    rig.run(T0 + 47 * 60)
    assert labels(rig) == {"glovebox shortlist": "O2"} and "O2" in rig.phone.sent[-1]["title"]
    rig.phone.say("approve O1", T0 + 50 * 60)
    rig.run(T0 + 51 * 60)
    assert rig.applied == [] and rig.phone.sent[-1]["body"] == "I do not see O1 open here. Open here: O2."


@pytest.mark.parametrize("flag", ["gate", "unreadable"])
def test_a_protected_request_keeps_one_restatement_even_when_named_by_label(home, flag):
    rig = Rig(home)
    rig.candidates = [cand(context=({**CTX} if flag == "gate" else {}))]
    rig.open_one()
    rig.phone.say("approve O1", T0 + 41 * 60 - 30)
    rig.run(T0 + 41 * 60)
    assert rig.applied == [] and rig.phone.sent[-1]["body"].startswith("Understood: approve glovebox shortlist [O1] (")
    rig.phone.say("yes", T0 + 43 * 60)
    rig.run(T0 + 44 * 60)
    assert [d["op"] for d in rig.applied] == ["approve"] and rig.parsed == []


def test_the_delegation_question_keeps_the_restatement_too(home):
    rig = Rig(home)
    rig.candidates = [cand(kind="delegation", task_ref="policy:advisor-approvals", task_id=ib.DELEGATION_TASK_ID, scope=ib.DELEGATION_SCOPE,
                           title="advisor approvals", priority="critical")]
    rig.open_one()
    rig.phone.say("approve S1", T0 + 41 * 60 - 30)
    rig.run(T0 + 41 * 60)
    assert rig.applied == [] and rig.phone.sent[-1]["body"].startswith("Understood: approve advisor approvals [S1]")


def test_a_labelled_decline_or_postponement_is_never_held_back_by_the_protection(home):
    rig = Rig(home)
    rig.candidates = [cand(context={**CTX})]
    rig.open_one()
    rig.phone.say("no O1", T0 + 41 * 60 - 30)
    rig.run(T0 + 41 * 60)
    assert [d["op"] for d in rig.applied] == ["decline"]


def test_a_labelled_yes_for_another_request_is_not_swallowed_by_a_pending_confirmation(home):
    rig = Rig(home)
    rig.candidates = multi("odysseus:ready/a.md", "odysseus:ready/b.md")
    rig.run(T0)
    rig.run(T0 + 2 * 60)
    o2 = next(i for i in rig.saved()["items"].values() if i["label"] == "O2")
    rig.phone.say("go ahead with thing a", T0 + 5 * 60)
    rig.verdicts = [{"target": "o1", "verdict": "yes"}]
    rig.run(T0 + 6 * 60)
    assert rig.saved()["echo"]["armed_at"] is not None
    rig.phone.say("yes O2", T0 + 8 * 60)
    rig.run(T0 + 9 * 60)
    assert rig.applied == [{"op": "approve", "item": o2["id"], "confirmed": True}] and rig.saved()["echo"] is None


def test_the_model_may_answer_with_the_label_in_any_case():
    parsed = ib.parse_reply(json.dumps({"target": "P2", "verdict": "yes", "condition": False, "confidence": 0.9}), {"draft ethics", "p2"})
    assert parsed["target"] == "p2"


def test_the_label_counter_never_falls_behind_the_labels_already_issued(home):
    rig = Rig(home)
    rig.candidates = multi("odysseus:ready/a.md", "odysseus:ready/b.md")
    rig.run(T0)
    rig.run(T0 + 2 * 60)
    state = rig.saved()
    state["labels"] = {}                                              # the counters were lost
    rig.state.write_text(json.dumps(state))
    rig.candidates += multi("odysseus:ready/a.md", "odysseus:ready/b.md", "odysseus:ready/c.md")[2:]
    rig.run(T0 + 5 * 60)
    rig.run(T0 + 7 * 60)
    got = list(labels(rig).values())
    assert len(got) == len(set(got)) == 3 and "O3" in got


def test_a_labelled_yes_for_the_request_awaiting_its_restatement_confirms_it(home):
    rig = Rig(home)
    rig.candidates = [cand(context={**CTX})]                         # a protected request
    rig.open_one()
    rig.phone.say("approve O1", T0 + 41 * 60 - 30)
    rig.run(T0 + 41 * 60)
    assert rig.applied == [] and rig.saved()["echo"]["armed_at"] is not None
    rig.phone.say("yes O1", T0 + 43 * 60)
    rig.run(T0 + 44 * 60)
    assert [d["op"] for d in rig.applied] == ["approve"] and rig.applied[0]["confirmed"] is True and rig.saved()["echo"] is None


def test_a_labelled_yes_for_a_different_request_does_not_confirm_a_pending_restatement(home):
    rig = Rig(home)
    rig.candidates = [cand(context={**CTX}), cand(task_ref="odysseus:ready/o.md", task_id="o", scope="b" * 64, title="Other thing", context={**CTX})]
    rig.run(T0)
    rig.run(T0 + 2 * 60)
    rig.phone.say("approve O1", T0 + 5 * 60)
    rig.run(T0 + 6 * 60)
    rig.phone.say("yes O2", T0 + 8 * 60)
    rig.run(T0 + 9 * 60)
    assert rig.applied == []                                         # O2 is protected too: it gets its own restatement, O1 stays unapproved


def test_an_item_without_the_protection_flag_is_treated_as_protected(home):
    rig = Rig(home)
    rig.open_one()
    state = rig.saved()
    for item in state["items"].values():
        item.pop("protected", None)
    rig.state.write_text(json.dumps(state))
    rig.phone.say("approve O1", T0 + 41 * 60 - 30)
    rig.run(T0 + 41 * 60)
    assert rig.applied == [] and rig.phone.sent[-1]["body"].startswith("Understood: approve")


def test_the_bare_number_patterns_really_match():
    for text in ("approve 2", "Approve #2.", "2 yes", "no 12", "later #3 please", "do it 2"):
        assert ib._NUM_VERB.match(text) or ib._NUM_FIRST.match(text), text
    for text in ("approve O2", "approve", "2", "approve two"):
        assert not (ib._NUM_VERB.match(text) or ib._NUM_FIRST.match(text)), text


# ---- a resolved request's whole thread is purged; what was not understood stays until reviewed

def thread_rig(home):
    rig = two_way_rig(home)
    rig.candidates = [cand(task_ref="obsidian-phd:ready/x.md", task_id="x", scope="c" * 64, title="Glovebox shortlist")]
    rig.open_one()
    return rig


def say_in(rig, text, at, mid):
    rig.phone.say(text, at, mid=mid, topic=f"{BASE}/phd-approvals", tags=[])


def test_the_whole_thread_of_a_resolved_request_is_deleted_five_minutes_later(home):
    rig = thread_rig(home)
    deleted = []
    say_in(rig, "go ahead with the glovebox one", T0 + 41 * 60 - 30, "u1")
    rig.verdicts = [{"target": "glovebox shortlist", "verdict": "yes"}]
    run_with(rig, T0 + 41 * 60, deleted)
    say_in(rig, "yes", T0 + 43 * 60, "u2")
    run_with(rig, T0 + 44 * 60, deleted)
    assert [d["op"] for d in rig.applied] == ["approve"] and deleted == []
    run_with(rig, T0 + 46 * 60, deleted)
    assert deleted == []                                           # still inside the five minutes
    run_with(rig, T0 + 44 * 60 + ib.RESOLVED_PURGE_DELAY + 60, deleted)
    ids = {m for _, m in deleted}
    assert {"u1", "u2", "pub0"} <= ids and len(ids) == 5          # the package, both of the owner's messages and both acknowledgements
    assert all(u.startswith(BASE) for u, _ in deleted)


def test_a_labelled_reply_and_its_acknowledgement_are_purged_with_the_package(home):
    rig = thread_rig(home)
    deleted = []
    say_in(rig, "no P1", T0 + 41 * 60 - 30, "n1")
    run_with(rig, T0 + 41 * 60, deleted)
    run_with(rig, T0 + 41 * 60 + ib.RESOLVED_PURGE_DELAY + 60, deleted)
    assert {"n1", "pub0"} <= {m for _, m in deleted} and len(deleted) == 3


def test_a_question_about_a_request_is_purged_with_its_thread_not_before(home):
    rig = thread_rig(home)
    deleted = []
    say_in(rig, "P1?", T0 + 41 * 60 - 30, "q1")
    run_with(rig, T0 + 41 * 60, deleted)
    run_with(rig, T0 + 3 * 3600, deleted)
    assert deleted == []                                           # the request is still open, so its thread stays
    say_in(rig, "later P1", T0 + 3 * 3600 + 60, "l1")
    run_with(rig, T0 + 3 * 3600 + 120, deleted)
    run_with(rig, T0 + 3 * 3600 + 120 + ib.RESOLVED_PURGE_DELAY + 60, deleted)
    assert {"q1", "l1", "pub0"} <= {m for _, m in deleted}


def test_an_exchange_that_was_not_understood_stays_until_it_is_old_a_routine_one_goes_after_an_hour(home):
    rig = Rig(home)
    deleted = []
    run_with(rig, T0, deleted)
    rig.phone.say("blah blah something odd", T0 + 5 * 60, mid="x1", topic=f"{BASE}/alerts-topic-1234", tags=[])
    rig.phone.say("pause", T0 + 6 * 60, mid="p1", topic=f"{BASE}/alerts-topic-1234", tags=[])
    run_with(rig, T0 + 7 * 60, deleted)
    kinds = {e["msg"]: e["kind"] for e in rig.saved()["loose"]}
    assert sorted(kinds.values()) == ["done", "done", "open", "open"]
    run_with(rig, T0 + 7 * 60 + ib.LOOSE_DONE_AFTER + 60, deleted)
    gone = {m for _, m in deleted}
    assert "p1" in gone and "x1" not in gone                      # the command exchange went; the one nobody understood stays
    run_with(rig, T0 + 3 * 86400, deleted)
    run_with(rig, T0 + 60 * 86400, deleted)
    assert "x1" not in {m for _, m in deleted}                    # never timed out: it stays until a reviewer has handled it


def test_every_owner_message_is_logged_with_what_became_of_it(home):
    rig = thread_rig(home)
    say_in(rig, "blah blah something odd", T0 + 41 * 60 - 40, "a1")
    say_in(rig, "P1?", T0 + 41 * 60 - 30, "a2")
    say_in(rig, "approve P9", T0 + 41 * 60 - 20, "a3")
    say_in(rig, "approve P1", T0 + 41 * 60 - 10, "a4")
    rig.run(T0 + 41 * 60)
    got = {e["id"]: e["out"] for e in rig.saved()["log"]}
    assert got == {"a1": "unclear", "a2": "asked", "a3": "not_open", "a4": "applied:approve"}
    assert all(e["reviewed"] is False and e["text"] for e in rig.saved()["log"])


def test_the_loose_and_log_lists_are_validated_when_read(home):
    state = home / "inbox.json"
    state.write_text(json.dumps({"owner": "operator", "channel": "c",
                                 "loose": [{"url": f"{BASE}/t", "msg": "ok1", "t": 5, "kind": "open"}, {"url": f"{BASE}/t", "msg": "bad/id", "t": 5, "kind": "open"},
                                           {"url": f"{BASE}/t", "msg": "ok2", "t": "x", "kind": "open"}, {"url": f"{BASE}/t", "msg": "ok3", "t": 5, "kind": "weird"}],
                                 "log": [{"id": "m1", "t": 3, "text": "hello", "out": "unclear"}, {"id": 5, "t": 3, "text": "x", "out": "y"}, "junk",
                                         {"id": "m2", "t": 4, "text": "x" * 500, "out": "o" * 90, "reviewed": 1}]}))
    got = ib._read_state(state)
    assert [e["msg"] for e in got["loose"]] == ["ok1"] and [e["id"] for e in got["log"]] == ["m1", "m2"]
    assert len(got["log"][1]["text"]) == 200 and len(got["log"][1]["out"]) == 40 and got["log"][1]["reviewed"] is True


def test_a_legacy_owner_message_without_a_topic_is_never_scheduled_for_deletion(home):
    rig = Rig(home)
    rig.open_one()
    rig.phone.say("no O1", T0 + 41 * 60 - 30, mid="legacy1")        # one-way: the owner's message lives on a topic the backend cannot write
    rig.run(T0 + 41 * 60)
    assert "legacy1" not in {e["msg"] for e in rig.saved()["retire"]}


def test_the_log_tells_the_truth_when_an_action_did_not_go_through(home):
    rig = Rig(home)
    rig.open_one()
    rig.apply = lambda do, items, digest: (None, "error")
    rig.phone.say("no O1", T0 + 41 * 60 - 30, mid="f1")
    rig.run(T0 + 41 * 60)
    assert [e["out"] for e in rig.saved()["log"]] == ["failed"]


def test_a_reply_that_raised_is_still_logged_and_its_full_text_kept_in_an_append_only_file(home):
    rig = Rig(home)
    rig.open_one()
    rig.parse = lambda text, open_items, echo: (_ for _ in ()).throw(RuntimeError("boom"))       # free text goes to the model, which fails
    long = "no O1 " + "because " * 60
    rig.phone.say(long, T0 + 41 * 60 - 30, mid="e1")
    rig.run(T0 + 41 * 60)
    assert [e["out"] for e in rig.saved()["log"]] == ["error"]
    lines = [json.loads(l) for l in (home / "owner_messages.jsonl").read_text().splitlines()]
    assert lines[-1]["id"] == "e1" and lines[-1]["out"] == "error" and lines[-1]["text"].startswith("no O1 because")
    assert (home / "owner_messages.jsonl").stat().st_mode & 0o077 == 0


def test_a_pending_confirmation_does_not_capture_an_unrelated_later_reply(home):
    rig = Rig(home)
    rig.open_one()
    rig.phone.say("go ahead with the glovebox one", T0 + 41 * 60 - 30, mid="g1")
    rig.verdicts = [{"target": "glovebox shortlist", "verdict": "yes"}]
    rig.run(T0 + 41 * 60)
    assert rig.saved()["echo"]
    rig.phone.say("pause", T0 + 43 * 60, mid="g2", topic=f"{BASE}/alerts-topic-1234", tags=[])
    rig.run(T0 + 44 * 60)
    item = next(iter(rig.saved()["items"].values()))
    assert not any(e["msg"] == "g2" for e in item.get("thread", [])) and any(e["msg"] == "g2" for e in rig.saved()["loose"])


# ---- several labelled decisions in one message, and the periodic review

def two_open(rig, contexts=({"risk": "medium"}, {"risk": "medium"})):
    rig.candidates = [cand(task_ref=f"odysseus:ready/{n}.md", task_id=f"t{n}", scope=f"{n}" * 64, title=f"Thing {chr(97 + n)}", context=c) for n, c in enumerate(contexts)]
    rig.run(T0)
    rig.run(T0 + 2 * 60)
    rig.phone.sent.clear()


def test_two_labelled_decisions_in_one_message_both_apply(home):
    rig = Rig(home)
    two_open(rig)
    rig.phone.say("approve O1. no O2", T0 + 5 * 60)
    rig.run(T0 + 6 * 60)
    assert [(d["op"], rig.saved()["items"][d["item"]]["label"]) for d in rig.applied] == [("approve", "O1"), ("decline", "O2")]
    assert rig.parsed == [] and rig.phone.sent[-1]["body"].startswith("O1: Approved. O2: Declined.")
    assert {i["state"] for i in rig.saved()["items"].values()} == {"answered"}


def test_the_second_label_inherits_the_verb(home):
    rig = Rig(home)
    two_open(rig)
    rig.phone.say("approve O1 and O2", T0 + 5 * 60)
    rig.run(T0 + 6 * 60)
    assert [d["op"] for d in rig.applied] == ["approve", "approve"]


def test_multiple_decisions_are_all_or_nothing(home):
    rig = Rig(home)
    two_open(rig)
    for n, text in enumerate(["approve O1. approve O9", "approve O1. approve O1", "approve O1 and no O1"]):
        rig.phone.say(text, T0 + (5 + n) * 60, mid=f"z{n}")
    rig.run(T0 + 10 * 60)
    assert rig.applied == [] and rig.parsed == []
    assert all(s["body"].startswith("I read 2 decisions but ") and "I applied none" in s["body"] for s in rig.phone.sent[-3:])


def test_an_approval_of_a_protected_request_is_never_part_of_a_multi_decision(home):
    rig = Rig(home)
    two_open(rig, ({"risk": "medium"}, {}))                     # the second carries no decision-class facts: protected
    rig.phone.say("approve O1. approve O2", T0 + 5 * 60)
    rig.run(T0 + 6 * 60)
    assert rig.applied == [] and "approving O2 needs its own confirmation" in rig.phone.sent[-1]["body"]
    rig.phone.say("no O2. approve O1", T0 + 7 * 60, mid="z9")                   # a refusal is never protected
    rig.run(T0 + 8 * 60)
    assert [d["op"] for d in rig.applied] == ["decline", "approve"]


def test_a_single_sentence_that_is_not_a_list_of_decisions_is_read_as_before(home):
    rig = Rig(home)
    two_open(rig)
    rig.phone.say("approve O1 because it looks right. thanks", T0 + 5 * 60)
    rig.run(T0 + 6 * 60)
    assert rig.applied == [] and len(rig.parsed) == 1             # not a multi-decision: the model reads it, as before


def reviewer(rig, answer, home):
    from src import owner_topic_review as tr
    calls = []

    def ask(prompt):
        calls.append(prompt)
        return answer(prompt) if callable(answer) else answer
    rig.review = lambda state, channel, send_fn, now: tr.review_cycle(state, channel, send_fn, now, ask, home / "owner_requests.jsonl")
    return calls


def say_unclear(rig, text, at, mid):
    rig.phone.say(text, at - 30, mid=mid, topic=f"{BASE}/alerts-topic-1234", tags=[])
    rig.run(at)


def test_the_review_asks_back_with_the_exact_reply_and_applies_nothing(home):
    rig = Rig(home)
    rig.open_one()
    calls = reviewer(rig, lambda p: json.dumps([{"id": "u1", "intent": "decision", "summary": "approve the glovebox request", "decisions": [{"label": "O1", "verb": "approve"}]}]), home)
    say_unclear(rig, "approve the glovebox one please", T0 + 41 * 60, "u1")
    assert rig.saved()["log"][0]["out"] == "unclear" and calls == []                    # five minutes of grace before anything is second-guessed
    rig.run(T0 + 60 * 60)
    assert len(calls) == 1 and rig.applied == []
    assert "Did you mean: approve O1?" in rig.phone.sent[-1]["body"] and "Reply 'approve O1'" in rig.phone.sent[-1]["body"]
    saved = rig.saved()
    assert saved["log"][0]["reviewed"] is True and saved["review_at"] == T0 + 60 * 60
    assert {"u1", saved["log"][0]["ack"]} <= {m for _, m in rig.deleted}                # the handled exchange (message and reply) is deleted
    assert any(e["msg"] == "pub" + str(rig.phone.posted - 1) and e["kind"] == "review" for e in saved["loose"])      # the review's own answer stays a day


def test_the_review_offers_two_decisions_as_one_reply_unless_one_is_protected(home):
    rig = Rig(home)
    two_open(rig)
    both = json.dumps([{"id": "u2", "intent": "decision", "summary": "two approvals", "decisions": [{"label": "O1", "verb": "approve"}, {"label": "O2", "verb": "approve"}]}])
    reviewer(rig, both, home)
    say_unclear(rig, "approve thing a and the other one thing b", T0 + 41 * 60, "u2")
    rig.run(T0 + 60 * 60)
    assert "Did you mean: approve O1 and approve O2?" in rig.phone.sent[-1]["body"] and "Reply 'approve O1. approve O2'" in rig.phone.sent[-1]["body"]


def test_a_change_request_is_recorded_as_a_numbered_owner_request(home):
    rig = Rig(home)
    rig.open_one()
    reviewer(rig, lambda p: json.dumps([{"id": "u3", "intent": "change_request", "summary": "Check first whether the corpus task is already done", "decisions": []}]), home)
    say_unclear(rig, "this may already be done, investigate first", T0 + 41 * 60, "u3")
    rig.run(T0 + 60 * 60)
    row = json.loads((home / "owner_requests.jsonl").read_text().splitlines()[-1])
    assert row["id"] == "R1" and row["status"] == "open" and row["text"].startswith("this may already be done")
    assert "Logged as R1: you wrote 'this may already be done, investigate first'" in rig.phone.sent[-1]["body"] and rig.applied == []
    assert (home / "owner_requests.jsonl").stat().st_mode & 0o077 == 0


def test_the_review_cannot_approve_and_ignores_labels_that_are_not_open(home):
    from src import owner_topic_review as tr
    state = {"items": {"a": {"state": "open", "label": "O1", "name": "x"}}, "log": []}
    entries = [{"id": "m1", "text": "t", "out": "unclear", "t": 0}]
    raw = 'sure: [{"id": "m1", "intent": "decision", "summary": "s", "decisions": [{"label": "O9", "verb": "approve"}, {"label": "o1", "verb": "delete"}, {"label": "o1", "verb": "approve"}, {"label": "O1", "verb": "no"}]}, {"id": "zz", "intent": "decision", "summary": "x"}]'
    assert tr.parse_review(raw, entries, state) == {"m1": {"intent": "decision", "summary": "s", "decisions": [{"label": "O1", "verb": "approve"}]}}
    assert tr.parse_review("not json", entries, state) is None


def test_the_review_runs_only_when_something_needs_it_and_not_more_than_every_three_hours(home):
    rig = Rig(home)
    rig.open_one()
    calls = reviewer(rig, lambda p: json.dumps([{"id": "u4", "intent": "note", "summary": "fyi", "decisions": []}]), home)
    rig.run(T0 + 50 * 60)
    assert calls == [] and rig.saved()["review_at"] == 0.0                              # nothing to review: no model call
    say_unclear(rig, "just so you know, I am away tomorrow", T0 + 51 * 60, "u4")
    rig.run(T0 + 60 * 60)
    assert len(calls) == 1 and rig.saved()["log"][0]["reviewed"] is True
    say_unclear(rig, "another thing nobody understands", T0 + 61 * 60, "u5")
    rig.run(T0 + 90 * 60)
    assert len(calls) == 1                                                                # less than three hours since the last pass
    rig.run(T0 + 60 * 60 + 3 * 3600 + 60)
    assert len(calls) == 2


def test_unreadable_model_output_leaves_the_messages_unreviewed_and_untouched(home):
    rig = Rig(home)
    rig.open_one()
    reviewer(rig, "I am sorry, I cannot do that", home)
    say_unclear(rig, "something unclear here", T0 + 41 * 60, "u6")
    rig.run(T0 + 60 * 60)
    saved = rig.saved()
    assert saved["log"][0]["reviewed"] is False and saved["retire"] == [] and rig.applied == []


def test_the_review_can_be_switched_off(home, monkeypatch):
    monkeypatch.setenv("ODYSSEUS_OWNER_REVIEW", "0")
    rig = Rig(home)
    rig.open_one()
    calls = reviewer(rig, "[]", home)
    say_unclear(rig, "something unclear here", T0 + 41 * 60, "u7")
    rig.run(T0 + 60 * 60)
    assert calls == []


def test_a_multi_decision_ends_a_pending_confirmation_even_when_another_topic_has_open_requests(home):
    rig = Rig(home)
    write_routes(home, {"odysseus": "odysseus-approvals", "obsidian-phd": "phd-approvals"})
    rig.candidates = [cand(task_ref=f"odysseus:ready/{n}.md", task_id=f"t{n}", scope=f"{n}" * 64, title=f"Thing {chr(97 + n)}") for n in range(3)] + \
                     [cand(task_ref="obsidian-phd:ready/p.md", task_id="tp", scope="4" * 64, title="Thing p")]
    rig.run(T0)
    rig.run(T0 + 2 * 60)
    odys = f"{BASE}/odysseus-approvals"
    name = {i["label"]: i["name"] for i in rig.saved()["items"].values()}
    rig.phone.say("go ahead with the first one", T0 + 5 * 60, mid="e1", topic=odys, tags=[])
    rig.verdicts = [{"target": name["O1"], "verdict": "yes"}]
    rig.run(T0 + 6 * 60)
    assert rig.saved()["echo"]
    rig.phone.say("approve O2 and O3", T0 + 8 * 60, mid="e2", topic=odys, tags=[])
    rig.run(T0 + 9 * 60)
    assert rig.saved()["echo"] is None
    rig.phone.say("yes", T0 + 10 * 60, mid="e3", topic=odys, tags=[])
    rig.run(T0 + 11 * 60)
    assert len(rig.applied) == 2 and all(rig.saved()["items"][d["item"]]["label"] != "O1" for d in rig.applied)


def test_a_multi_decision_with_a_failing_part_is_logged_failed_and_keeps_its_thread(home):
    rig = Rig(home)
    two_open(rig)
    rig.apply = lambda do, items, digest: ("Approved.", "done") if do["op"] == "approve" else ("Could not save.", "error")
    rig.phone.say("approve O1. no O2", T0 + 5 * 60, mid="mf")
    rig.run(T0 + 6 * 60)
    assert rig.saved()["log"][-1]["out"] == "failed"
    rig.run(T0 + 20 * 60)
    assert "mf" not in {m for _, m in rig.deleted}                   # one request is still open: the exchange stays


def test_a_message_the_model_skipped_is_never_treated_as_handled(home):
    rig = Rig(home)
    rig.open_one()
    reviewer(rig, "[]", home)
    say_unclear(rig, "something unclear here", T0 + 41 * 60, "k1")
    rig.run(T0 + 60 * 60)
    entry = rig.saved()["log"][0]
    assert entry["reviewed"] is False and entry["tries"] == 1 and rig.deleted == []
    sent = len(rig.phone.sent)
    rig.run(T0 + 5 * 3600)
    rig.run(T0 + 9 * 3600)
    rig.run(T0 + 13 * 3600)
    assert rig.saved()["log"][0]["tries"] == 3 and len(rig.phone.sent) == sent and rig.deleted == []      # given up after three tries, never silently deleted


def test_a_clarification_that_could_not_be_delivered_keeps_the_owners_message(home):
    rig = Rig(home)
    rig.open_one()
    reviewer(rig, lambda p: json.dumps([{"id": "k2", "intent": "decision", "summary": "approve", "decisions": [{"label": "O1", "verb": "approve"}]}]), home)
    say_unclear(rig, "approve the glovebox one please", T0 + 41 * 60, "k2")
    rig.phone.refuse_sends = 1
    rig.run(T0 + 60 * 60)
    entry = rig.saved()["log"][0]
    assert entry["reviewed"] is False and entry["tries"] == 1 and "k2" not in {m for _, m in rig.deleted}


def test_an_unplaceable_message_is_asked_about_not_silently_dropped(home):
    rig = Rig(home)
    rig.open_one()
    reviewer(rig, lambda p: json.dumps([{"id": "k3", "intent": "other", "summary": "unclear", "decisions": []}]), home)
    say_unclear(rig, "hmm maybe the other thing", T0 + 41 * 60, "k3")
    rig.run(T0 + 60 * 60)
    assert "I could not tell what you meant by 'hmm maybe the other thing'" in rig.phone.sent[-1]["body"]


def test_an_entry_the_owner_has_since_settled_is_tidied_without_a_question(home):
    rig = Rig(home)
    rig.open_one()
    calls = reviewer(rig, "[]", home)
    say_unclear(rig, "approve the glovebox one please", T0 + 41 * 60, "k4")
    rig.phone.say("approve O1", T0 + 45 * 60, mid="k5", topic=f"{BASE}/alerts-topic-1234", tags=[])
    rig.run(T0 + 46 * 60)
    rig.run(T0 + 60 * 60)
    assert calls == [] and rig.saved()["log"][0]["reviewed"] is True and "k4" in {m for _, m in rig.deleted}


def test_a_later_decision_on_another_request_does_not_settle_an_earlier_unhandled_message(home):
    rig = Rig(home)
    two_open(rig)
    calls = reviewer(rig, lambda p: json.dumps([{"id": "k7", "intent": "decision", "summary": "approve", "decisions": [{"label": "O1", "verb": "approve"}]}]), home)
    say_unclear(rig, "approve the docs one", T0 + 41 * 60, "k7")
    rig.phone.say("approve O2", T0 + 42 * 60, mid="k8", topic=f"{BASE}/alerts-topic-1234", tags=[])
    rig.run(T0 + 43 * 60)
    rig.run(T0 + 60 * 60)
    assert len(calls) == 1 and "Did you mean: approve O1?" in rig.phone.sent[-1]["body"]


def test_the_reviews_own_answer_stays_a_day_and_a_far_future_review_time_cannot_disable_it(home):
    rig = Rig(home)
    rig.open_one()
    reviewer(rig, lambda p: json.dumps([{"id": "k6", "intent": "decision", "summary": "approve", "decisions": [{"label": "O1", "verb": "approve"}]}]), home)
    say_unclear(rig, "approve the glovebox one please", T0 + 41 * 60, "k6")
    data = rig.saved()
    data["review_at"] = T0 + 10 ** 9
    rig.state.write_text(json.dumps(data))
    rig.run(T0 + 60 * 60)
    pub_id = "pub" + str(rig.phone.posted - 1)
    assert "Did you mean" in rig.phone.sent[-1]["body"]
    rig.run(T0 + 4 * 3600)
    assert pub_id not in {m for _, m in rig.deleted}
    rig.run(T0 + 60 * 60 + 25 * 3600)
    assert pub_id in {m for _, m in rig.deleted}


def test_a_leading_zero_is_read_as_the_letter_o_on_a_phone_keyboard(home):
    rig = Rig(home)
    two_open(rig)
    rig.phone.say("approve 01", T0 + 5 * 60, mid="z1")
    rig.phone.say("no 02", T0 + 5 * 60 + 5, mid="z2")
    rig.run(T0 + 6 * 60)
    assert [d["op"] for d in rig.applied] == ["approve", "decline"]
    assert ib.zero_as_o("approve 01 and #02, 10, 0, 007 and 5") == "approve O1 and #O2, 10, 0, O07 and 5"
    assert ib.zero_as_o("approve 01, 02.") == "approve O1, O2."
    assert ib.zero_as_o("after 0800 or call 07700 900123, 007") == "after 0800 or call 07700 900123, O07"
    assert ib.zero_as_o("on 2026-01-05 at 09:05, 1-08 and 05/01 and v1.01") == "on 2026-01-05 at 09:05, 1-08 and 05/01 and v1.01"


def test_up_to_eight_labelled_decisions_in_one_message(home):
    rig = Rig(home)
    rig.candidates = [cand(task_ref=f"odysseus:ready/{n}.md", task_id=f"t{n}", scope=f"{n}" * 64, title=f"Thing {chr(97 + n)}") for n in range(9)]
    rig.run(T0)
    rig.run(T0 + 2 * 60)
    rig.run(T0 + 3 * 60)                                                  # five requests are authored per cycle
    rig.phone.say("approve O1, O2, O3, O4, O5, O6, O7, O8", T0 + 5 * 60, mid="z3")
    rig.phone.say("approve O1, O2, O3, O4, O5, O6, O7, O8, O9", T0 + 5 * 60 + 5, mid="z4")
    rig.run(T0 + 6 * 60)
    assert len(rig.applied) == 8 and len(rig.parsed) == 1                 # nine parts is not read by code (and is never approved in bulk)
    assert all(f"O{n}: Approved." in rig.phone.sent[-2]["body"] or f"O{n}: Approved." in rig.phone.sent[-1]["body"] for n in range(1, 9))


def test_the_ledger_digest_and_the_log_use_what_the_owner_typed_not_the_rewritten_text(home):
    import hashlib
    rig = Rig(home)
    two_open(rig)
    digests = []
    rig.apply = lambda do, items, digest: digests.append(digest) or ("Approved.", "done")
    rig.phone.say("approve 01", T0 + 5 * 60, mid="z5")
    rig.run(T0 + 6 * 60)
    assert digests == [hashlib.sha256(b"approve 01").hexdigest()[:16]] and rig.saved()["log"][-1]["text"] == "approve 01"
