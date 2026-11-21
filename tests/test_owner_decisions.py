"""Lightweight owner-decision cards (2026-11-21, owner request): present the few decisions that need the
owner, via a Discord webhook, so they can answer quickly; never block other work on them.

Cards are built only from the owner gates `/lazyUsage` already records (approval, acceptance). They contain
task titles and one-line reasons only: never a task body, a secret, or a model output."""
import json
import os
import stat

import pytest

from src import owner_decisions as od

APPROVAL = {"task_ref": "obsidian-phd:ready/2026-10-26-cpi-supervision-update-2026-10-30.agent-task.md",
            "task_id": "2026-10-26-cpi-supervision-update-2026-10-30", "gate": "owner_approval",
            "scope_sha256": "8c16e5c0fed273284e682099083cfef12da603198c5d0b6f971455299bd90b23",
            "opened_at": "2026-11-20T10:00:00"}
ACCEPT = {"task_ref": "odysseus:ready/2026-11-09-qualify-glm.agent-task.md", "task_id": "2026-11-09-qualify-glm",
          "gate": "owner_acceptance", "opened_at": "2026-11-21T09:00:00"}
AGENT_ONLY = [{"task_ref": "odysseus:ready/x.agent-task.md", "task_id": "x", "gate": g, "opened_at": "2026-11-21T09:00:00"}
              for g in ("verification", "independent_review", "recovery", "finalization")]


def test_only_owner_gates_become_cards():
    cards = od.build_cards([APPROVAL, ACCEPT, *AGENT_ONLY])
    assert {c["gate"] for c in cards} == {"owner_approval", "owner_acceptance"}


def test_finished_work_awaiting_acceptance_ranks_before_an_approval():
    cards = od.build_cards([APPROVAL, ACCEPT])
    assert [c["gate"] for c in cards] == ["owner_acceptance", "owner_approval"]


def test_older_approvals_rank_first_and_ties_are_stable():
    newer = {**APPROVAL, "task_ref": "odysseus:ready/b.agent-task.md", "task_id": "b", "opened_at": "2026-11-21T00:00:00"}
    older = {**APPROVAL, "task_ref": "odysseus:ready/a.agent-task.md", "task_id": "a", "opened_at": "2026-11-01T00:00:00"}
    assert [c["ref"] for c in od.build_cards([newer, older])] == [older["task_ref"], newer["task_ref"]]


def test_a_card_has_a_title_a_reason_options_and_a_default():
    (card,) = od.build_cards([APPROVAL])
    assert card["title"] == "cpi supervision update 2026 10 30" or "cpi supervision update" in card["title"]
    assert card["why"] and card["options"] and "skip" in card["default"].lower()
    assert card["ref"] == APPROVAL["task_ref"] and card["key"]


def test_the_key_changes_when_the_scope_changes_so_a_changed_ask_is_sent_again():
    (a,) = od.build_cards([APPROVAL])
    (b,) = od.build_cards([{**APPROVAL, "scope_sha256": "f" * 64}])
    assert a["key"] != b["key"]


def test_the_message_is_short_ranked_and_capped_at_three_cards():
    debts = [{**APPROVAL, "task_ref": f"odysseus:ready/t{i}.agent-task.md", "task_id": f"t{i}",
              "opened_at": f"2026-11-0{i + 1}T00:00:00"} for i in range(6)]
    message = od.render(od.build_cards(debts))
    assert message.count("Decision needed") == 3 and "+3 more" in message
    assert len(message) <= 1800


def test_a_message_never_carries_bodies_secrets_or_mentions():
    debt = {**APPROVAL, "error": "SECRET-TOKEN-123", "next_action": "run rm -rf /", "objective": "BODY TEXT",
            "task_id": "x @everyone"}
    message = od.render(od.build_cards([debt]))
    for forbidden in ("SECRET-TOKEN-123", "rm -rf", "BODY TEXT", "@everyone"):
        assert forbidden not in message


# ----------------------------------------------------------------------------------- sending

class Recorder:
    def __init__(self, status=204):
        self.calls, self.status = [], status

    def __call__(self, url, payload, timeout):
        self.calls.append((url, payload))
        return self.status


def channel_file(tmp_path, url="https://discord.com/api/webhooks/123/abc", mode=0o600):
    path = tmp_path / "decision_channel.json"
    path.write_text(json.dumps({"kind": "discord", "url": url}))
    os.chmod(path, mode)
    return path


def test_no_channel_configured_is_a_silent_noop(tmp_path):
    post = Recorder()
    assert od.notify([APPROVAL], state_path=tmp_path / "s.json", channel_path=tmp_path / "missing.json", post=post) == "no_channel"
    assert post.calls == []


def test_a_card_is_sent_once_and_not_again_until_it_changes(tmp_path):
    post, state, chan = Recorder(), tmp_path / "s.json", channel_file(tmp_path)
    assert od.notify([APPROVAL], state_path=state, channel_path=chan, post=post, min_interval=0) == "sent"
    assert od.notify([APPROVAL], state_path=state, channel_path=chan, post=post, min_interval=0) == "nothing_new"
    assert len(post.calls) == 1
    changed = [{**APPROVAL, "scope_sha256": "e" * 64}]
    assert od.notify(changed, state_path=state, channel_path=chan, post=post, min_interval=0) == "sent"
    assert len(post.calls) == 2


def test_new_cards_wait_for_the_cooldown_instead_of_arriving_in_a_burst(tmp_path):
    post, state, chan = Recorder(), tmp_path / "s.json", channel_file(tmp_path)
    t = [1_800_000_000.0]
    clock = lambda: t[0]
    assert od.notify([APPROVAL], state_path=state, channel_path=chan, post=post, clock=clock) == "sent"
    other = {**APPROVAL, "task_ref": "odysseus:ready/z.agent-task.md", "task_id": "z"}
    t[0] += 60
    assert od.notify([APPROVAL, other], state_path=state, channel_path=chan, post=post, clock=clock) == "cooldown"
    assert len(post.calls) == 1
    t[0] += od.MIN_INTERVAL_SECONDS
    assert od.notify([APPROVAL, other], state_path=state, channel_path=chan, post=post, clock=clock) == "sent"
    assert len(post.calls) == 2


def test_the_payload_is_discord_json_with_mentions_disabled(tmp_path):
    post = Recorder()
    od.notify([APPROVAL], state_path=tmp_path / "s.json", channel_path=channel_file(tmp_path), post=post)
    url, payload = post.calls[0]
    assert url == "https://discord.com/api/webhooks/123/abc"
    assert payload["allowed_mentions"] == {"parse": []} and payload["content"].startswith("Decision needed")


@pytest.mark.parametrize("url", ["http://discord.com/api/webhooks/1/a", "https://evil.example/api/webhooks/1/a",
                                 "https://discord.com.evil.example/api/webhooks/1/a", "https://discord.com/other/1/a",
                                 "https://127.0.0.1/api/webhooks/1/a", ""])
def test_only_a_discord_webhook_url_is_accepted(tmp_path, url):
    post = Recorder()
    result = od.notify([APPROVAL], state_path=tmp_path / "s.json", channel_path=channel_file(tmp_path, url), post=post)
    assert result == "bad_channel" and post.calls == []


def test_a_world_readable_channel_file_is_refused(tmp_path):
    post = Recorder()
    chan = channel_file(tmp_path, mode=0o644)
    assert od.notify([APPROVAL], state_path=tmp_path / "s.json", channel_path=chan, post=post) == "channel_not_private"
    assert post.calls == []


def test_a_failed_send_is_not_recorded_so_it_is_retried(tmp_path):
    state, chan = tmp_path / "s.json", channel_file(tmp_path)
    assert od.notify([APPROVAL], state_path=state, channel_path=chan, post=Recorder(status=429)) == "send_failed"
    post = Recorder()
    assert od.notify([APPROVAL], state_path=state, channel_path=chan, post=post) == "sent" and len(post.calls) == 1


def test_a_transport_exception_never_escapes(tmp_path):
    def boom(url, payload, timeout):
        raise OSError("network down")
    assert od.notify([APPROVAL], state_path=tmp_path / "s.json", channel_path=channel_file(tmp_path), post=boom) == "send_failed"


def test_the_webhook_url_is_never_returned_or_logged(tmp_path, caplog):
    chan = channel_file(tmp_path)
    od.notify([APPROVAL], state_path=tmp_path / "s.json", channel_path=chan, post=Recorder(status=500))
    assert "123/abc" not in caplog.text


def test_no_owner_gates_means_nothing_is_sent(tmp_path):
    post = Recorder()
    assert od.notify(AGENT_ONLY, state_path=tmp_path / "s.json", channel_path=channel_file(tmp_path), post=post) == "nothing_new"
    assert post.calls == []


# ------------------------------------------------------------------------------------- wiring

from tests.test_lazy_usage_delivery import activate, db, queue  # noqa: E402,F401  (fixtures + helper)
from src import estate_router, lazy_usage_runtime as rt  # noqa: E402


def test_the_lifecycle_tick_offers_the_owed_owner_decisions_once_per_tick(db, queue, monkeypatch):
    run_id = activate(db)
    row = db.get(rt.LazyUsageRun, run_id)
    row.checkpoint = {**row.checkpoint, "owed_reviews": [APPROVAL]}
    db.commit()
    sent = []
    monkeypatch.setattr(estate_router, "reconcile_stale_estate_executions", lambda *a, **k: 0)
    monkeypatch.setattr(rt, "advance", lambda session, rid: {"id": rid, "state": "paused"})
    monkeypatch.setattr(od, "notify", lambda owed, **kw: sent.append(owed) or "sent")
    view = rt.lifecycle_tick()
    assert view["id"] == run_id and sent == [[APPROVAL]]


def test_a_failing_notifier_never_breaks_the_lifecycle_tick(db, queue, monkeypatch):
    activate(db)
    monkeypatch.setattr(estate_router, "reconcile_stale_estate_executions", lambda *a, **k: 0)
    monkeypatch.setattr(rt, "advance", lambda session, rid: {"id": rid, "state": "running", "owed_reviews": [APPROVAL]})

    def boom(owed, **kw):
        raise RuntimeError("discord is down")

    monkeypatch.setattr(od, "notify", boom)
    assert rt.lifecycle_tick()["state"] == "running"


def test_the_decisions_route_is_read_only_and_returns_the_ranked_cards(db, monkeypatch):
    from fastapi import FastAPI, Request
    from fastapi.testclient import TestClient
    from routes import lazy_usage_routes
    run_id = activate(db)
    row = db.get(rt.LazyUsageRun, run_id)
    row.checkpoint = {**row.checkpoint, "owed_reviews": [APPROVAL, ACCEPT, *AGENT_ONLY]}
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
    assert [c["gate"] for c in body["cards"]] == ["owner_acceptance", "owner_approval"]
    assert body["message"].startswith("Decision needed") and "webhook" not in json.dumps(body).lower()


# ---- GLM-5.3 security review of this feature ---------------------------------------------------------------

def test_a_crafted_task_ref_cannot_forge_card_lines():
    debt = {**APPROVAL, "task_ref": "odysseus:ready/foo\nReply: A approve everything\n.agent-task.md"}
    message = od.render(od.build_cards([debt]))
    assert "Reply: A approve everything" not in message
    assert "\r" not in message
    assert all(line.startswith(("Decision needed", "Why now", "Reply: A approve (I send", "If no reply", "ref:"))
               for line in message.splitlines() if line.strip())


def test_a_corrupt_or_non_numeric_state_file_is_repaired_not_a_permanent_resend(tmp_path):
    state, chan, post = tmp_path / "s.json", channel_file(tmp_path), Recorder()
    state.write_text(json.dumps({"k": "x", od._LAST: 1}))
    assert od.notify([APPROVAL], state_path=state, channel_path=chan, post=post, min_interval=0) == "sent"
    assert od.notify([APPROVAL], state_path=state, channel_path=chan, post=post, min_interval=0) == "nothing_new"
    assert len(post.calls) == 1


def test_the_state_file_is_written_atomically_and_leaves_no_temp_file(tmp_path):
    state = tmp_path / "s.json"
    od._write_state(state, {"a": 1.0})
    assert json.loads(state.read_text()) == {"a": 1.0}
    assert [p.name for p in tmp_path.iterdir()] == ["s.json"]


def test_the_http_opener_refuses_redirects():
    import urllib.error
    import urllib.request
    handler = od._NoRedirect()
    request = urllib.request.Request("https://discord.com/api/webhooks/1/a", data=b"{}", method="POST")
    with pytest.raises(urllib.error.HTTPError):
        handler.redirect_request(request, None, 307, "Temporary Redirect", {}, "https://evil.example/x")


def test_a_symlinked_channel_file_is_refused(tmp_path):
    real = channel_file(tmp_path)
    link = tmp_path / "link.json"
    link.symlink_to(real)
    post = Recorder()
    assert od.notify([APPROVAL], state_path=tmp_path / "s.json", channel_path=link, post=post) == "bad_channel"
    assert post.calls == []


def test_a_group_writable_parent_directory_is_refused(tmp_path):
    chan = channel_file(tmp_path)
    os.chmod(tmp_path, 0o775)
    try:
        post = Recorder()
        assert od.notify([APPROVAL], state_path=tmp_path / "s.json", channel_path=chan, post=post) == "channel_not_private"
        assert post.calls == []
    finally:
        os.chmod(tmp_path, 0o755)


def test_the_network_timeout_is_short():
    assert od.SEND_TIMEOUT_SECONDS <= 5


# ---- accuracy fixes found by previewing the real cards (2026-11-21) -------------------------------------------

def gaps(ref, *gates):
    return [{"task_ref": ref, "task_id": ref.rsplit("/", 1)[-1], "gate": g, "opened_at": "2026-11-21T09:00:00"} for g in gates]


@pytest.mark.parametrize("gate", ["verification", "independent_review", "recovery", "finalization"])
def test_an_acceptance_is_not_asked_while_verification_or_review_is_still_owed(gate):
    """The cards used to say 'delivered and verified' for work that was neither."""
    debts = [ACCEPT, *gaps(ACCEPT["task_ref"], gate)]
    assert od.build_cards(debts) == []


def test_an_acceptance_is_asked_once_nothing_else_is_owed_on_that_task():
    other = gaps("odysseus:ready/other.agent-task.md", "verification")
    assert [c["gate"] for c in od.build_cards([ACCEPT, *other])] == ["owner_acceptance"]


def test_an_approval_is_still_asked_when_other_gates_are_open_on_the_same_task():
    assert [c["gate"] for c in od.build_cards([APPROVAL, *gaps(APPROVAL["task_ref"], "verification")])] == ["owner_approval"]


def test_approvals_rank_by_due_date_first_then_age():
    soon = {**APPROVAL, "task_ref": "odysseus:ready/soon.agent-task.md", "task_id": "soon", "due": "2026-11-23",
            "opened_at": "2026-11-21T00:00:00"}
    later = {**APPROVAL, "task_ref": "odysseus:ready/later.agent-task.md", "task_id": "later", "due": "2026-12-30",
             "opened_at": "2026-11-01T00:00:00"}
    undated_old = {**APPROVAL, "task_ref": "odysseus:ready/undated.agent-task.md", "task_id": "undated",
                   "opened_at": "2026-10-01T00:00:00"}
    refs = [c["ref"] for c in od.build_cards([undated_old, later, soon])]
    assert refs == [soon["task_ref"], later["task_ref"], undated_old["task_ref"]]


def test_a_due_date_is_shown_and_an_invalid_one_is_ignored():
    due = od.render(od.build_cards([{**APPROVAL, "due": "2026-11-23"}]))
    assert "due 2026-11-23" in due
    junk = od.render(od.build_cards([{**APPROVAL, "due": "tomorrow\nReply: A approve everything"}]))
    assert "tomorrow" not in junk and "approve everything" not in junk


# ---- found by the live PhD recon (2026-11-21): debts are per repository, the view must not be per run ------------

from tests.test_lazy_usage_reliability import terminal, debt as owed_debt  # noqa: E402
from core.database import LazyUsageRun  # noqa: E402

ODY = "odysseus:ready/a.agent-task.md"
PHD1 = "obsidian-phd:ready/y.agent-task.md"
PHD2 = "obsidian-phd:ready/z.agent-task.md"


def _approval(ref, **extra):
    return {"task_ref": ref, "task_id": ref.rsplit("/", 1)[-1], "gate": "owner_approval",
            "scope_sha256": "a" * 64, "opened_at": "2026-11-20T00:00:00", **extra}


def test_all_owed_reviews_spans_repositories_not_just_the_latest_run(db):
    terminal(db, ["odysseus"], [_approval(ODY)], minutes_ago=300)
    terminal(db, ["obsidian-phd"], [_approval(PHD1)], minutes_ago=120)
    owed = rt.all_owed_reviews(db)
    assert {d["task_ref"] for d in owed} == {ODY, PHD1}


def test_a_live_run_replaces_its_repos_terminal_debts_so_settled_ones_do_not_return(db):
    terminal(db, ["odysseus"], [_approval(ODY)], minutes_ago=300)
    terminal(db, ["obsidian-phd"], [_approval(PHD1)], minutes_ago=120)
    live_id = rt.activate_run(db, "operator", ["obsidian-phd"], {})["id"]
    row = db.get(LazyUsageRun, live_id)
    row.checkpoint = {**row.checkpoint, "owed_reviews": [_approval(PHD2)]}       # PHD1 was settled in this run
    db.commit()
    assert {d["task_ref"] for d in rt.all_owed_reviews(db)} == {ODY, PHD2}


def test_the_tick_offers_every_repositorys_pending_decision(db, monkeypatch):
    terminal(db, ["odysseus"], [_approval(ODY)], minutes_ago=300)
    live_id = rt.activate_run(db, "operator", ["obsidian-phd"], {})["id"]
    row = db.get(LazyUsageRun, live_id)
    row.checkpoint = {**row.checkpoint, "owed_reviews": [_approval(PHD1)]}
    db.commit()
    sent = []
    monkeypatch.setattr(estate_router, "reconcile_stale_estate_executions", lambda *a, **k: 0)
    monkeypatch.setattr(rt, "advance", lambda session, rid: {"id": rid, "state": "paused"})
    monkeypatch.setattr(od, "notify", lambda owed, **kw: sent.append({d["task_ref"] for d in owed}) or "sent")
    rt.lifecycle_tick()
    assert sent == [{ODY, PHD1}]


def test_the_decisions_route_shows_every_repositorys_cards(db):
    from fastapi import FastAPI, Request
    from fastapi.testclient import TestClient
    from routes import lazy_usage_routes
    terminal(db, ["odysseus"], [_approval(ODY)], minutes_ago=300)
    terminal(db, ["obsidian-phd"], [_approval(PHD1)], minutes_ago=120)
    app = FastAPI()

    @app.middleware("http")
    async def identity(request: Request, call_next):
        request.state.api_token = True
        request.state.api_token_owner = "operator"
        request.state.api_token_scopes = ["estate:read"]
        return await call_next(request)

    app.include_router(lazy_usage_routes.setup_lazy_usage_routes())
    cards = TestClient(app).get("/api/lazy-usage/decisions").json()["cards"]
    assert {c["ref"] for c in cards} == {ODY, PHD1}


# ---- GLM-5.3 review: aggregation edge cases -------------------------------------------------------------------

def test_two_pre_upgrade_debts_without_a_task_ref_are_both_kept(db):
    legacy = [{"task_id": "old-a", "gate": "owner_acceptance", "execution_id": "e1"},
              {"task_id": "old-b", "gate": "owner_acceptance", "execution_id": "e2"}]
    terminal(db, ["obsidian-phd"], legacy, minutes_ago=300)
    assert sorted(d["task_id"] for d in rt.all_owed_reviews(db)) == ["old-a", "old-b"]


def test_a_quiet_repository_is_not_pushed_out_of_the_view_by_other_repositories_runs(db):
    terminal(db, ["obsidian-phd"], [_approval(PHD1)], minutes_ago=5000)
    for i in range(12):                                       # more than HISTORY_RUNS newer runs elsewhere
        terminal(db, ["odysseus"], [], minutes_ago=100 + i)
    assert PHD1 in {d["task_ref"] for d in rt.all_owed_reviews(db)}
