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

    def send(self, channel, title, body, priority, *a, **k):
        if self.refuse_sends:
            self.refuse_sends -= 1
            return False                      # the server answered and refused
        if self.fail_sends:
            self.fail_sends -= 1
            raise OSError("timed out")        # outcome unknown
        self.sent.append({"title": title, "body": body, "priority": priority})
        return True

    def fetch(self, channel, since):
        if since == "all":
            return list(self.inbox)
        ids = [m["id"] for m in self.inbox]
        return list(self.inbox[ids.index(since) + 1:]) if since in ids else list(self.inbox)

    def say(self, text, at, mid=None):
        self.inbox.append({"id": mid or f"m{len(self.inbox)}", "time": at, "text": text})


def cand(**over):
    base = {"kind": "approval", "task_ref": "odysseus:ready/glove.md", "task_id": "glove", "scope": "a" * 64, "fp": FP,
            "priority": "high", "opened_at": "2026-11-20", "title": "Glovebox shortlist", "card_line": "Glovebox shortlist, medium risk",
            "context": {}}
    return {**base, **over}


def fields(**over):
    return {"ask": "Let agents draft a glovebox supplier shortlist?", "why_you": "it may lead to spending", "yes": "draft only",
            "no": "stays parked", "advice": "yes", "detail": "Agents compare glovebox options and write a draft. Nothing is ordered.", **over}


class Rig:
    def __init__(self, home, now=T0, digest=False):
        self.home, self.phone, self.now = home, Phone(), now
        self.channel = write_channel(home)
        self.state = home / "inbox.json"
        self.candidates, self.applied, self.parsed, self.verdicts = [cand()], [], [], []
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
                        transport={"send": self.phone.send, "fetch": self.phone.fetch})

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
    ("", "x"), ("T" * 41, "x"), ("Approve: x", "y" * 301), ("Approve: x", "\n".join(["line"] * 7)),
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
    assert "Card: Glovebox shortlist, medium risk" in body and ib.fifteen_second_ok(title, body)
    # a model that tries to name or title the decision itself is ignored: those keys are not read
    hostile = ib.parse_author(json.dumps({**fields(), "name": "delete everything", "title": "Approve: nothing risky", "card_line": "x"}))
    assert "name" not in hostile and "title" not in hostile
    for bad in ({"advice": "maybe"}, {"detail": 5}, {"ask": None}):
        assert ib.parse_author(json.dumps({**fields(), **bad})) is None
    dirty = ib.parse_author(json.dumps(fields(ask="Edit src/x.py at https://e.com/x 3f9a1c07b2d4 now?")))
    title, body = ib.assemble(dirty, "Card")
    assert "/" not in body and "http" not in body and ib.fifteen_second_ok(title, body)


def test_the_name_is_built_by_code_from_the_verified_title():
    assert ib.short_name("Glovebox shortlist for the lab", set(), "abcd") == "glovebox shortlist lab"
    assert ib.short_name("Glovebox shortlist", {"glovebox shortlist"}, "abcd") == "glovebox"
    assert ib.short_name("The build", set(), "ab12cd") == "task ab12"


# ---- rationing

def test_first_run_sends_nothing_and_an_item_must_wait_before_it_interrupts(home):
    rig = Rig(home)
    assert rig.run(T0) == "first_run"
    assert rig.run(T0 + 10 * 60) == "idle" and not rig.phone.sent
    assert rig.run(T0 + 31 * 60) == "interrupt"
    sent = rig.phone.sent[0]
    assert sent["priority"] == 4 and sent["title"] == "Approve: glovebox shortlist" and ib.fifteen_second_ok(sent["title"], sent["body"])
    assert "Card: Glovebox shortlist, medium risk" in sent["body"]


def test_only_one_package_is_open_at_a_time(home):
    rig = Rig(home)
    rig.candidates = [cand(), cand(task_ref="odysseus:ready/other.md", task_id="other", scope="b" * 64, title="Other thing")]
    rig.open_one()
    rig.run(T0 + 5 * 3600)                       # the gap has passed but the first is still unanswered
    assert rig.phone.sent == []


def test_two_interrupts_a_day_three_hours_apart(home):
    rig = Rig(home)
    rig.candidates = [cand(task_ref=f"odysseus:ready/t{i}.md", task_id=f"t{i}", scope=f"{i}" * 64, title=f"Thing {i}") for i in range(4)]
    rig.run(T0)
    rig.run(T0 + 31 * 60)
    assert len(rig.phone.sent) == 1

    def answer_open():
        state = rig.saved()
        for item in state["items"].values():
            if item["state"] == "open":
                item["state"], item["done_at"] = "answered", T0
        rig.state.write_text(json.dumps(state))
    answer_open()
    assert rig.run(T0 + 2 * 3600) == "idle"                    # inside the three-hour gap
    assert rig.run(T0 + 31 * 60 + 3 * 3600 + 5) == "interrupt"
    answer_open()
    assert rig.run(T0 + 31 * 60 + 7 * 3600) == "idle"          # a third in the same day is never sent
    assert len(rig.phone.sent) == 2


def test_a_clock_that_goes_backwards_does_not_free_the_daily_cap(home):
    state = ib._empty_state()
    state["interrupts"] = [T0 + 600, T0 + 1200]               # stamps from the "future"
    assert ib.interrupt_allowed(state, T0) == "daily_cap"


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


def test_the_digest_goes_once_a_day_after_0845_silently(home):
    rig = Rig(home, digest=True)
    rig.candidates = []
    rig.run(datetime(2026, 11, 26, 8, 0, tzinfo=timezone.utc).timestamp())
    assert rig.run(datetime(2026, 11, 26, 8, 40, tzinfo=timezone.utc).timestamp()) == "idle"
    assert rig.run(datetime(2026, 11, 26, 8, 50, tzinfo=timezone.utc).timestamp()) == "digest"
    assert rig.phone.sent[0]["priority"] == 2 and rig.phone.sent[0]["body"] == "Last run stopped."
    assert rig.run(datetime(2026, 11, 26, 12, 0, tzinfo=timezone.utc).timestamp()) == "idle"
    assert rig.run(datetime(2026, 11, 27, 9, 0, tzinfo=timezone.utc).timestamp()) == "digest"


def test_a_quiet_day_is_one_line(home):
    rig = Rig(home, digest=True)
    rig.candidates, rig.facts = [], {}
    rig.run(datetime(2026, 11, 26, 8, 0, tzinfo=timezone.utc).timestamp())
    rig.run(datetime(2026, 11, 26, 9, 0, tzinfo=timezone.utc).timestamp())
    assert rig.phone.sent[0]["body"] == "All quiet. Nothing needs you."


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
    assert out["do"] is None and "Which one: ethics dossier or glovebox?" == out["say"]


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
    assert seen["url"] == channel["url"] and seen["headers"]["priority"] == "4" and seen["headers"]["click"] == channel["reply_url"]
    assert seen["headers"]["title"] == "Approve: caf thing" and seen["headers"]["authorization"].startswith("Basic ")
    assert [m["id"] for m in ib.fetch_replies(channel, "all")] == ["m1", "m2"]              # oldest first
    assert seen["url"].startswith("http://100.75.149.126:8091/reply-topic-1234/json?") and "since=all" in seen["url"]


def test_a_timeout_after_the_post_keeps_the_reservation_so_it_is_never_sent_twice(home):
    rig = Rig(home)
    rig.run(T0)
    rig.phone.fail_sends = 1                                # the broker may have accepted it
    assert "interrupt_unconfirmed" in rig.run(T0 + 31 * 60)
    state = rig.saved()
    assert len(state["interrupts"]) == 1 and [i["state"] for i in state["items"].values()] == ["open"]
    assert rig.run(T0 + 5 * 3600) == "idle" and rig.phone.sent == []


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
