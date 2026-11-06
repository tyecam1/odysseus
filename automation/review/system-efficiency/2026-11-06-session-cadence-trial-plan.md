# Session cadence trial plan (proposed, unratified)

Status: **outline only, not executable yet, not run, not approved.** An earlier independent Sol review (of the first draft, which was a fuller design) found that the design could not yet be run without further choices; those are listed under "Prerequisites before any trial" and must be settled first. It specifies the controlled comparison that `2026-11-06-usage-attribution-diagnosis.md` leaves open for hypothesis 1: whether coordination work costs fewer tokens when each work item (or PR) gets a fresh, scoped session resumed from a checkpoint, compared with the current long-running sessions. The diagnosis shows concentration (seven sessions of 500+ calls carry 47% of calls and 61% of cache-read tokens in the two dominant directories) but explicitly does **not** show that shorter sessions cost less: a fresh session may incur additional cache writes to re-prime its context (depending on prefix reuse, cache lifetime and timing), and long sessions may reflect harder work. Produced by Claude Sonnet 5.5; this revised outline has had one further Sol review round, recorded in the pull request.

## Question and outcome measures

Primary: total counted tokens (cache-read + cache-write + input + output) per **assigned work item**, reported for every assigned item including abandoned, timed-out or cancelled ones, with completion reported alongside (analysing only completed items would favour an arm that finishes only easier work). Items must be defined as non-overlapping units with acceptance criteria before assignment; a task that yields several PRs is one item or is split in advance. Secondary, from the same transcripts: calls per work item, cache-write per work item (setup cost), cache-read per call, and elapsed wall time. Quality guard (must not regress): the work item's review outcome, namely Sol or CI verdicts on the first review round (APPROVE vs CHANGES, number of P1 findings) and rework count after merge. Token counts are a volume measure, **not** allowance consumption; allowance is not observable locally, so no claim about allowance is made.

## Design

- **Unit of assignment:** the work item. Eligible items are those of the usual size that can be resumed from the existing checkpoint file (`queue_checkpoint_*.md`-style) without loss.
- **Arms:** (A) current practice: continue in the running session; (B) fresh session per item: start a new session, load only the checkpoint and the item's brief, work the item to merge, end the session.
- **Allocation:** randomise within pre-specified blocks, after eligibility and difficulty proxies (type, expected size, number of files) are recorded and before the arm is revealed to the person ordering the work; alternation or type-stratified ordering alone is predictable and does not balance difficulty. Record any deviation and its reason. Standardise the prompt, assistance and execution settings across arms.
- **Size:** at least 12 items per arm (24 total) before any conclusion; with fewer, the result is "inconclusive". Expect several weeks at the recent rate, so it runs alongside normal work and adds no tasks.
- **Fixed during the trial:** model per role (no mid-trial model change except forced by availability, then flagged), the same checkpoint format, the same review lane.

## Data (candidate sources; the attribution pilot decides whether they suffice)

From the local transcripts, numeric fields only: per session, calls, cache-read, cache-write, input and output tokens, timestamps; the join from session to work item was proposed as the PR number or task id the operator records at session start in the checkpoint (one line: `trial: item=<id> arm=<A|B>`); the pilot below suggests (without proving) that a start-of-session marker alone may not be enough because sessions appear to mix items. Quality guard from GitHub PR and review records. Long-running sessions naturally mix items, so excluding mixed sessions would remove the practice under test; item boundaries inside a session, and the allocation of shared overhead, checkpoint preparation, worker and review sessions and rework, must be defined and piloted first (see prerequisites). Until then, mixed sessions are reported separately, not silently dropped. The per-call `subject` and `function` tags (#225, #226, #235) may give a more exact join once the lab runs them and their attribution coverage is validated, but the trial is not assumed to depend on them; whether any extra boundary records or instrumentation are needed is a question for the pilot.

## Analysis (fixed in advance)

Compare per-item totals between arms with a paired-by-stratum difference in medians and a bootstrap 90% interval; report effect sizes, not only direction. Decision rule: adopt fresh-session-per-item as the default only if the median tokens per **assigned** item (over a pre-specified observation window) in arm B is at least 20% lower than in arm A with the interval excluding zero **and** the completion and acceptance guard shows no lower completion rate and the quality guard shows no worse first-round verdicts or rework; an arm must not look cheaper by abandoning difficult work. If B is cheaper but quality is worse, or the interval includes zero, keep current practice. Report setup cost separately so a reader can see where any saving or loss comes from.

## Risks

Confounding by item difficulty (mitigated by blocked randomisation using recorded difficulty proxies; residual imbalance remains possible); learning effects as the checkpoint format improves; the operator's own behaviour changing when watched; token counts not equalling allowance; small sample. Any of these can make the result inconclusive, which is an acceptable outcome.

## Pilot, first step (2026-11-06 12:54Z): can sessions be joined to work items?

A numeric-only feasibility check of prerequisite 1 on the two dominant directories (main transcripts; calls counted once per message and request id, but every record's tool-call blocks read; only candidate PR or issue numbers matched in `gh pr <verb> <n>` and `repos/.../pulls|issues/<n>` commands were kept, and no transcript prose was stored; the regex can also capture an arbitrary two-to-four-digit number in such a command and misses single-digit and five-digit identifiers, so these are candidate matches, not verified PR identities). Script below.

| Measure | Value |
|---|---:|
| Main sessions | 69 |
| Sessions with no PR reference | 30 |
| Sessions with exactly 1 distinct candidate PR number | 8 |
| Sessions referencing 2-5 PRs | 17 |
| Sessions referencing 6 or more PRs | 14 |
| Median distinct PRs per session that references any (39 sessions) | 3 (maximum 43) |
| Raw reference transitions within a session (adjacent matches that differ; denominator: the 39 sessions with any match): median / maximum | 5 / 62 |
| Share of calls in sessions that reference at least one PR | 91% (14,352 of 15,686) |

Finding: **this heuristic has not demonstrated reliable session-level attribution; prerequisite 1 remains open.** Only 8 of 69 sessions contain exactly one detected number, and that does not establish their work-item scope (reading or checking references, other repositories, issue numbers and missed references all intervene). Most sessions with any match contain several distinct numbers and many raw transitions (the transition count includes repeated and within-command matches, so it overstates real subject changes); this is consistent with sessions mixing items, but is not proof, so assigning a whole session's tokens to one item is **unvalidated and probably misattributes them**. Call-level attribution by segmenting a session at PR-reference boundaries looks plausible but is noisy and unvalidated: the regex also catches references to PRs that are only being read or checked, may match other repositories' numbers, and 30 sessions have no reference at all (they may be short, or work that does not involve PRs; not examined). The pilot therefore leaves prerequisite 1 **open, not passed**: a validated attribution method is still needed, for example explicit item boundaries recorded in the session (a marker per item start and end, not only at session start) or the per-call `subject` tag extended beyond the estate's paid launches. It does not test the cost of checkpoint preparation or review sessions. Not independently reviewed.

```python
import glob, json, os, re, collections, statistics
root = os.path.expanduser("~/.claude/projects")
PR = re.compile(r"gh\s+pr\s+(?:view|create|merge|checks|ready|edit|diff|close|comment)\b[^\n|;&]*?\b(\d{2,4})\b|repos/[\w.-]+/[\w.-]+/(?:pulls|issues)/(\d{2,4})\b")
sessions = []
seen = set()
for d in ["<home-directory-name>", "<phd-notes-directory-name>"]:   # the two local transcript directory names; substitute your own
    for p in sorted(glob.glob(os.path.join(root, d, "*.jsonl"))):
        calls = 0; prs_by_call = []
        for line in open(p, encoding="utf-8", errors="replace"):
            try: e = json.loads(line)
            except ValueError: continue
            m = e.get("message") or {}
            if e.get("type") == "assistant" and m.get("usage"):
                key = (m.get("id"), e.get("requestId"))
                if key not in seen:      # count each call once, but still read every record's content blocks below
                    seen.add(key); calls += 1
            if e.get("type") != "assistant": continue
            for c in (m.get("content") or []):
                if isinstance(c, dict) and c.get("type") == "tool_use":
                    cmd = ((c.get("input") or {}).get("command")) or ""
                    for g in PR.findall(cmd):
                        n = g[0] or g[1]
                        if n: prs_by_call.append((calls, n))
        sessions.append((d, p, calls, prs_by_call))
tot = len(sessions)
dist = collections.Counter()
for _, _, calls, pb in sessions:
    k = len({n for _, n in pb})
    dist["0" if k == 0 else "1" if k == 1 else "2-5" if k <= 5 else "6+"] += 1
print("main sessions", tot, "| distinct PR numbers touched per session:", dict(dist))
pc = [len({n for _, n in pb}) for _, _, _, pb in sessions if pb]
if pc: print("sessions touching any PR:", len(pc), "| median distinct PRs", statistics.median(pc), "max", max(pc))
# switching: within a session, how many times does the 'most recent PR touched' change
sw = [sum(1 for a, b in zip(pb, pb[1:]) if a[1] != b[1]) for _, _, _, pb in sessions if pb]
if sw: print("PR switches within sessions: median", statistics.median(sw), "max", max(sw))
calls_all = sum(c for _, _, c, _ in sessions)
calls_pr = sum(c for _, _, c, pb in sessions if pb)
print("calls in sessions that touch any PR:", calls_pr, "of", calls_all, f"({100*calls_pr/calls_all:.0f}%)")
```

## Pilot, second step (2026-11-06 12:59Z): segmenting one session by the merge times of the PRs it delivered

A numeric-only demonstration of one candidate attribution method on a single long session (the Claude Code session that produced most of the PRs referenced in these reports): each call is assigned to the segment that **ends** at the next merge of a PR in the Odysseus repository, using the PR merge times from GitHub and the call timestamps from the transcript. Calls counted once per message and request id. Script below (the transcript path is that session's file).

The session has 1,090 calls between 2026-11-02 10:17 and 2026-11-06 12:59 UTC and 26 PRs merged inside that span, giving 27 segments. Median segment: 13 calls. Two segments are far larger: the one ending at the merge of #211 (355 calls, 207 M cache-read tokens, 1.69 M cache-write, 509 k output) and the one ending at #219 (230 calls, 40.5 M, 0.52 M, 116 k). Together these are 585 of 1,090 calls (54%). The documentation-only PRs each close a segment of roughly 13 to 40 calls.

What this shows: the method is mechanically workable and gives a per-delivered-item cost profile for a mixed session, and it is consistent with the owner's observation that repeated review rounds on one design cost far more than small, centralised changes (the #219 segment contains the abandoned larger #216 design and its redesign). What it does **not** show or validate:

- A segment contains everything between two merges, including idle waiting, side work, coordination, memory notes, compaction and the start of the next item, so the figures are upper bounds on the item's own cost and the first segment also absorbs everything before the first merge in the window.
- Items overlap in time (several branches and reviews in flight), so assigning by the next merge time can misplace calls.
- It is one session, one repository and one day-range; it says nothing about the arms of the proposed trial, and the earlier first-step finding (sessions mix items) means this method needs a second independent measure to validate it, for example item-boundary markers recorded in the session or per-call `subject` tags, against which these segment totals could be compared.
- Only calls that end in a merge can be attributed; work that never merged (abandoned or open) falls into the following segment or into none.

Prerequisite 1 therefore stays **open**: this is a candidate method with a worked example, not a validated one. Not independently reviewed.

```python
import json, os, subprocess, datetime, bisect, collections, sys
sess = os.path.expanduser("~/.claude/projects/<project-directory>/<session-id>.jsonl")
prs = json.loads(subprocess.run(["gh", "pr", "list", "-R", "tyecam1/odysseus", "--state", "merged", "--limit", "60", "--json", "number,mergedAt,title"],
                                capture_output=True, text=True, encoding="utf-8").stdout)
t0 = None; calls = {}
for line in open(sess, encoding="utf-8", errors="replace"):
    try: e = json.loads(line)
    except ValueError: continue
    m = e.get("message") or {}; u = m.get("usage")
    if e.get("type") != "assistant" or not u: continue
    ts = e.get("timestamp") or ""
    key = (m.get("id"), e.get("requestId"))
    if key in calls: continue
    calls[key] = (ts, u.get("cache_read_input_tokens", 0), u.get("cache_creation_input_tokens", 0), u.get("output_tokens", 0))
rows = sorted(calls.values())
first, last = rows[0][0], rows[-1][0]
merged = sorted((p["mergedAt"], p["number"]) for p in prs if first <= p["mergedAt"] <= last)
print("session calls", len(rows), "| span", first[:16], "->", last[:16], "| PRs merged inside the span:", len(merged))
bounds = [m[0] for m in merged]
seg = collections.defaultdict(lambda: [0, 0, 0, 0])
for ts, cr, cw, out in rows:
    i = bisect.bisect_left(bounds, ts)           # the call belongs to the segment that ENDS with the next merge
    label = merged[i][1] if i < len(merged) else "after-last-merge"
    s = seg[label]; s[0] += 1; s[1] += cr; s[2] += cw; s[3] += out
print("segment (ends at merge of PR) | calls | cache-read M | cache-write M | output k")
for label, (c, cr, cw, out) in sorted(seg.items(), key=lambda kv: -kv[1][0])[:14]:
    print(f"#{label} | {c} | {cr/1e6:.1f} | {cw/1e6:.2f} | {out/1e3:.0f}")
cs = sorted(v[0] for v in seg.values())
print("segments", len(seg), "| calls per segment median", cs[len(cs)//2], "max", cs[-1])
```

## Prerequisites before any trial

1. **Attribution pilot:** produce and validate an attribution method (item-boundary markers, per-call tags, or another) that gives an item-level token join, including item boundaries inside long sessions and the treatment of shared overhead, checkpoint preparation, worker and review sessions and rework. If it cannot be done, the trial cannot start.
2. **Item and completion definitions:** non-overlapping items with acceptance criteria; rules for abandonment, timeouts and multi-PR tasks; all assigned items reported.
3. **Allocation:** blocks, difficulty proxies and the randomisation procedure fixed in advance; standardised prompts, assistance and settings.
4. **Intervention fidelity and carry-over:** session lineage (which session resumes for arm A after arm B), cross-item dependencies, checkpoint content rules and their preparation cost, and a record of arrival gaps and cache conditions with a decision on whether they are controlled or part of the intended operational effect.
5. **Analysis fixed in advance:** how pairs are formed, stratum weights, absolute versus relative effect, the resampling unit and bootstrap method, how shared-session dependence is handled, a stopping rule, and a precision justification for the sample size. The decision rule (median at least 20% lower with an interval excluding zero) is coherent but does **not** establish that the true saving reaches 20%.
6. **Quality endpoints:** comparable measures (CI results and model review verdicts differ), review coverage for items without PRs, regression margins, missing-data rules and equal follow-up for rework (recent merges have had less time); with about twelve items per arm only large harms can be excluded.
7. **Consent:** the owner's consent to run the trial and to the allocation, since arm B changes working practice.

Only after prerequisites 1 to 7 are satisfied (1 to 6 written down and the pilot passed, 7 consent given) and any applicable execution authority is in place is the trial ready; consent alone is necessary but not sufficient; no new infrastructure, table or scheduler is expected to be needed, but that is a conclusion of the pilot, not an assumption. Existing execution authority and review gates are unchanged.
