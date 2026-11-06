# Subscription usage attribution: ranked diagnosis (partial, project-level proxy)

Continues `2026-09-08-subscription-usage-attribution.md` (stage 1-2 baseline) and `2026-11-06-lab-codex-telemetry.md`. It adds a project-level attribution of the laptop's Claude and GLM usage, a ranked diagnosis with hypotheses to test, routing and cadence recommendations, and a minimal telemetry schema. It is **partial and unreviewed**: produced by Claude Sonnet 5.5 on 2026-11-06; the independent Sol review the task requires is **owed and not run**. Function-level attribution is approximated by the transcript's project directory, which is a proxy, not a function taxonomy.

## Method

Read-only, numeric fields only (`message.usage` token counts, model, request/message ids, project directory name, source file kind main/subagent, timestamp). No message content was read or is reproduced. Records were de-duplicated on message id plus request id across main and subagent transcripts; every record carried a message id, 6,843 lacked a request id (so those are keyed on message id alone), none collapsed onto an empty key, and the first occurrence of a duplicate key was kept without checking that later copies agreed. Counts were taken in one run at 09:06Z on 2026-11-06; the transcripts grow while work continues, so a rerun gives slightly larger numbers. The script is below. Scope is everything on this laptop (2026-06-03 to 2026-11-06), so counts are larger than the 2026-10-02..11-02 window of the baseline; the two have not been reconciled and should not be subtracted from each other. Native units are not comparable across providers and are not compared.

## Results

20,826 unique calls. By family: Sonnet 11,464 (55%), GLM 6,833 (33%), Opus 2,102 (10%), Haiku and other 427 (2%) (the four sum to the total).

| Project directory (proxy for function) | Calls (share) | main / subagent | Sonnet / Opus / GLM / other | Output M | Cache-write M | Cache-read M |
|---|---:|---:|---|---:|---:|---:|
| control-plane home (`C--Users-tyeca`) | 11,308 (54%) | 9,696 / 1,612 | 5,517 / 1,221 / 4,444 / 126 | 7.68 | 43.5 | 2,705 |
| PhD notes repository | 6,157 (30%) | 5,861 / 296 | 5,124 / 881 / 10 / 142 | 5.17 | 39.5 | 2,670 |
| PhD ROS2 measurement spine | 830 (4%) | 830 / 0 | 823 / 0 / 0 / 7 | 1.04 | 5.8 | 223 |
| PhD j2 work | 632 (3%) | 609 / 23 | 0 / 0 / 591 / 41 | 2.62 | 0.0 | 13 |
| aoteru controller | 547 (3%) | 547 / 0 | 0 / 0 / 547 / 0 | 0.19 | 0.0 | 53 |
| all others (scratchpads, worktrees, review trees) | 1,352 (6%) | | mostly GLM | | | |

Concentration: the first two directories hold 84% of calls (17,465), 93% of cache-write tokens (83.0 of 88.8 M), 94% of cache-read tokens (5,375 of 5,738 M) and 70% of output tokens (12.85 of 18.31 M). Opus is 10% of calls and all of it (1,221 + 881 = 2,102) is in those same two directories.

## Ranked diagnosis (hypotheses, each with the measurement that would confirm it)

1. **Two long-context coordination directories dominate consumption.** Evidence: the concentration above. Likely mechanism: very long sessions re-reading a large cached context on every call (cache-read is about 98% of the tokens counted). Not shown: session lengths, compaction behaviour, what the context consists of. Confirm by measuring calls and cache-read per session and per day in these two directories, and the share of calls whose cache-read exceeds a threshold.
2. **Opus may be disproportionately expensive per call (hypothesis).** Evidence is weak: all Opus calls sit in the two large-context directories, and the earlier baseline's unreconciled average was about 15.6 k cache-write tokens per Opus call. Directory membership does not give Opus-specific context sizes, and token volume is not allowance consumption (allowance is not observable here). Policy already restricts Opus to exceptions. Confirm with model-specific per-call context size (cache-write plus cache-read) in these directories, and by listing Opus calls by day against the exception reasons recorded in the work.
3. **GLM accounts for 33% of recorded calls; its share of cache-write and cache-read tokens has not been established here** (cache tokens are pooled by project, and the script does not aggregate them by model family). Whether those calls are delegated work is not established (model identity and transcript location do not prove delegation), and GLM allowance is unknown, so this is a call-volume observation only. The `j2 work` row is a project total (591 GLM and 41 other calls; 2.62 M output), not a GLM-only figure.
4. **Recorded Sol calls are predominantly review-class and templated** (see `2026-11-06-sol-call-classification.md`: 98% review-class, 708 of 714 calls under 7 templates, median prompt about 93 k characters). Consumption by class (tokens or allowance) has not been quantified, so this does not yet identify the dominant saving. The packet compiler (#214, wired inert in #220) is the planned remedy, gated on calibration and replay evidence.
5. **Lab Codex appears to be a separate account or plan anchor** (weekly window differs from the laptop's), so the laptop's Codex window is not the estate's whole Sol budget. Unconfirmed.

## Recommendations (to test, not to apply blindly)

- Measure first (hypotheses 1 and 2): per-session shape is now measured (addendum); the open step is comparing sessions that were restarted per work item against long-running ones on cache creation, cache reads and completion quality, and model-specific per-call context for Opus.
- Test, do not adopt, a cadence change: compare fresh scoped sessions per work item or PR against long-running sessions in the same directories on cache creation, cache reads, setup overhead and completion quality (fresh sessions can raise cache creation, and task complexity can explain long sessions' totals). Keep Opus for the recorded exception cases and record the exception reason in the work record.
- Keep delegating bounded review and implementation to GLM/Sol lanes (already policy); do not move coordination volume onto them without a measurement.
- Treat Sol call reduction as unmeasured until the replay and regression evidence exists; do not claim savings from #214/#220.
- Use the new call telemetry to close the attribution loop for Sol: `subject` and `head_sha` are now recorded for advisory and write-lane calls once the lab runs #225/#226/#227 and callers pass the flags.

## Minimal telemetry schema (proposed)

One row per paid call, joinable on existing ids: `provider`, `model` (resolved), `function` (task class or work-item kind), `subject` and `head_sha` (as in #225/#226), `input_tokens`, `cached_input_tokens`, `output_tokens`, and for Codex the provider `used_percent` for the 5-hour and weekly windows before and after the call. Today the estate records, in the `|call=` suffix of the routing decision, only `subject`, `head_sha`, `started_at`, `launched` (advisory) or `submitted` plus `execution_id` (write lane): execution-level events, not one record per provider inference call. Model, token and window fields are not recorded by the estate; adding them, and correlating execution-level records to provider-call rows, would need a separate, reviewed change.

## Not done

- Before/after attribution for a representative function, a true function taxonomy from repository activity, and a controlled comparison of session cadences. (Per-session shape is now measured in the addendum.)
- Claude allowance percent-remaining (no local source), and home-host usage.
- The independent Sol review of this report.

## Addendum: per-session shape in the two dominant directories (hypothesis 1, measured)

Same method and scope as above (numeric fields only, de-duplicated, taken in one run on 2026-11-06 at about 09:30Z), restricted to **main** transcripts in the control-plane home and PhD notes directories (subagent files excluded, so 15,571 of those directories' 17,465-plus calls; a call present in two files is owned by the first path in sorted order, every call had a message id, and all timestamps were in one fixed format, YYYY-MM-DDTHH:MM:SS.mmmZ, verified across all 33,200 assistant records before de-duplication, so lexical order is chronological, with ties kept in file order): 61 sessions.

| Session length (calls) | Sessions | Calls (share) | Cache-read M | Cache-write M | Output M | Mean cache-read per call |
|---|---:|---:|---:|---:|---:|---:|
| 1-20 | 13 | 59 (0%) | 2 | 0.6 | 0.08 | 31 k |
| 21-100 | 7 | 363 (2%) | 29 | 0.7 | 0.22 | 80 k |
| 101-500 | 34 | 7,848 (50%) | 1,966 | 27.9 | 5.96 | 251 k |
| 501 or more | 7 | 7,301 (47%) | 3,086 | 30.8 | 6.43 | 423 k |

Median session is 159 calls, p90 585, maximum 1,638. Mean cache-read per call by position within a session rises from 54 k (calls 1-10) to 152 k (11-100), 393 k (101-500) and 420 k (501+). A drop of more than half in cache-read between consecutive calls (only counted when the earlier call read more than 20,000 tokens), a heuristic for a compaction or context reset that was **not verified as one**, occurs in 221 of 15,510 consecutive-call steps (1.4%). Within the same seven sessions of 500+ calls, mean cache-read per call is 69 k over their first ten calls and 420 k from call 501 onward (about six-fold); the pooled position figures above mix different sets of sessions and are not themselves evidence of within-session growth.

What this shows: consumption in these directories is concentrated in a few long sessions (7 sessions of 500+ calls carry 47% of the calls and 61% of the cache-read tokens), and across those same seven sessions the pooled mean cache-read per call is 69 k early and 420 k late (individual session changes are not reported). This is consistent with hypothesis 1 and with the context simply accumulating as work proceeds.

What it does not show: that shorter or restarted sessions would cost less. A fresh session must re-prime its working context (cache-write), long sessions may reflect task complexity and duration, and cache-read tokens are a volume measure, not allowance consumption. The recommendation to test a cadence change therefore stands as a controlled comparison (cache creation, cache reads, setup overhead and completion quality per work item), not as an instruction. Still unmeasured: what the context consists of, quality per session, and whether the heuristic drops are compactions.

## Script

```python
import glob, json, os, collections, datetime
root = os.path.expanduser("~/.claude/projects")
seen = set(); agg = collections.defaultdict(lambda: collections.Counter()); days = collections.defaultdict(collections.Counter)
for p in glob.glob(root + "/*/**/*.jsonl", recursive=True) + glob.glob(root + "/*/*.jsonl"):
    proj = os.path.relpath(p, root).split(os.sep)[0]
    sub = "subagent" if "subagents" in p.replace("\\", "/") else "main"
    try:
        for line in open(p, encoding="utf-8", errors="replace"):
            try: e = json.loads(line)
            except ValueError: continue
            m = e.get("message") or {}
            u = m.get("usage")
            if not u or e.get("type") != "assistant": continue
            key = (m.get("id"), e.get("requestId"))
            if key in seen: continue
            seen.add(key)
            model = m.get("model") or "?"
            fam = "glm" if "glm" in model else "opus" if "opus" in model else "sonnet" if "sonnet" in model else "haiku" if "haiku" in model else "other"
            c = agg[proj]
            c["calls"] += 1; c["calls_" + fam] += 1; c["calls_" + sub] += 1
            c["out"] += u.get("output_tokens", 0); c["cw"] += u.get("cache_creation_input_tokens", 0)
            c["cr"] += u.get("cache_read_input_tokens", 0); c["in"] += u.get("input_tokens", 0)
            d = (e.get("timestamp") or "")[:10]
            days[proj][d] += 1
    except OSError:
        pass
tot = sum(c["calls"] for c in agg.values()); totout = sum(c["out"] for c in agg.values()); totcw = sum(c["cw"] for c in agg.values())
print("calls", tot, "output", totout, "cache_write", totcw)
print("project | calls (share) | main/sub | sonnet/opus/glm/other | output M | cache-write M | cache-read M")
for proj, c in sorted(agg.items(), key=lambda kv: -kv[1]["calls"])[:12]:
    print(f"{proj[-46:]} | {c['calls']} ({100*c['calls']/tot:.0f}%) | {c['calls_main']}/{c['calls_subagent']} | {c['calls_sonnet']}/{c['calls_opus']}/{c['calls_glm']}/{c['calls_haiku']+c['calls_other']} | {c['out']/1e6:.2f} | {c['cw']/1e6:.1f} | {c['cr']/1e6:.0f}")
```

Per-session script (addendum):

```python
import glob, json, os, collections, statistics, datetime
root = os.path.expanduser("~/.claude/projects")
dirs = ["C--Users-tyeca", "C--Users-tyeca-Documents-PhD-notes"]
seen = set(); sessions = []
for d in dirs:
    for p in sorted(glob.glob(os.path.join(root, d, "*.jsonl"))):   # sorted: a call shared by two files belongs to the first path          # main transcripts only (subagents are in subfolders)
        calls = []
        for line in open(p, encoding="utf-8", errors="replace"):
            try: e = json.loads(line)
            except ValueError: continue
            m = e.get("message") or {}; u = m.get("usage")
            if not u or e.get("type") != "assistant": continue
            key = (m.get("id"), e.get("requestId"))
            if key in seen: continue
            seen.add(key)
            calls.append((e.get("timestamp") or "", u.get("cache_read_input_tokens", 0), u.get("cache_creation_input_tokens", 0), u.get("output_tokens", 0), m.get("model") or ""))
        if calls: sessions.append((d, p, sorted(calls, key=lambda x: x[0])))   # ISO-8601 UTC strings sort chronologically; ties keep file order (stable)
n = [len(c) for _, _, c in sessions]
tot = sum(n)
print("main sessions", len(sessions), "calls", tot, "| calls/session median", statistics.median(n), "p90", sorted(n)[int(.9*len(n))], "max", max(n))
for lo, hi in ((1, 20), (21, 100), (101, 500), (501, 10**9)):
    ss = [c for _, _, c in sessions if lo <= len(c) <= hi]
    k = sum(len(c) for c in ss)
    cr = sum(x[1] for c in ss for x in c); cw = sum(x[2] for c in ss for x in c); out = sum(x[3] for c in ss for x in c)
    print(f"{lo}-{hi if hi<10**9 else '+'} calls: {len(ss)} sessions, {k} calls ({100*k/tot:.0f}%), cache-read {cr/1e6:.0f} M, cache-write {cw/1e6:.1f} M, output {out/1e6:.2f} M, mean cache-read/call {cr/max(1,k)/1e3:.0f} k")
# context growth: mean cache-read per call by position within a session (first 10 / 11-100 / 101-500 / 500+)
pos = collections.defaultdict(list)
for _, _, c in sessions:
    for i, x in enumerate(c):
        b = "1-10" if i < 10 else "11-100" if i < 100 else "101-500" if i < 500 else "501+"
        pos[b].append(x[1])
print("mean cache-read per call by position in session:", {b: round(sum(v)/len(v)/1e3) for b, v in pos.items()}, "(k tokens)")
# resets inside a session: a drop in cache-read of >50% between consecutive calls = compaction/restart-like event
drops = 0; steps = 0
for _, _, c in sessions:
    for a, b in zip(c, c[1:]):
        steps += 1
        if a[1] > 20000 and b[1] < 0.5 * a[1]: drops += 1
print("consecutive-call cache-read drops >50%:", drops, "of", steps, "steps")

# within-session growth: the SAME long sessions, early vs late
long_ = [c for _, _, c in sessions if len(c) >= 501]
early = [x[1] for c in long_ for x in c[:10]]; late = [x[1] for c in long_ for x in c[500:]]
print("within the", len(long_), "sessions of 501+ calls: mean cache-read calls 1-10 =", round(sum(early)/len(early)/1e3), "k; calls 501+ =", round(sum(late)/len(late)/1e3), "k")
ts_bad = sum(1 for _, _, c in sessions for x in c if not x[0].endswith("Z") or len(x[0]) < 20)
print("calls with missing or non-UTC-Z timestamps:", ts_bad)
```
