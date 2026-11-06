# Subscription usage attribution: ranked diagnosis (partial, project-level proxy)

Continues `2026-09-08-subscription-usage-attribution.md` (stage 1-2 baseline) and `2026-11-06-lab-codex-telemetry.md`. It adds a project-level attribution of the laptop's Claude and GLM usage, a ranked diagnosis with hypotheses to test, routing and cadence recommendations, and a minimal telemetry schema. It is **partial and unreviewed**: produced by Claude Sonnet 5.5 on 2026-11-06; the independent Sol review the task requires is **owed and not run**. Function-level attribution is approximated by the transcript's project directory, which is a proxy, not a function taxonomy.

## Method

Read-only, numeric fields only (`message.usage` token counts, model, request/message ids, project directory name, source file kind main/subagent, timestamp). No message content was read or is reproduced. Records were de-duplicated on message id plus request id across main and subagent transcripts. The script is below. Scope is everything on this laptop (2026-06-03 to 2026-11-06), so counts are larger than the 2026-10-02..11-02 window of the baseline; the two have not been reconciled and should not be subtracted from each other. Native units are not comparable across providers and are not compared.

## Results

20,819 unique calls. By family: Sonnet 11,458 (55%), GLM 6,833 (33%), Opus 2,102 (10%), Haiku and other 427 (2%).

| Project directory (proxy for function) | Calls (share) | main / subagent | Sonnet / Opus / GLM / other | Output M | Cache-write M | Cache-read M |
|---|---:|---:|---|---:|---:|---:|
| control-plane home (`C--Users-tyeca`) | 11,301 (54%) | 9,689 / 1,612 | 5,510 / 1,221 / 4,444 / 126 | 7.67 | 43.5 | 2,703 |
| PhD notes repository | 6,157 (30%) | 5,861 / 296 | 5,124 / 881 / 10 / 142 | 5.17 | 39.5 | 2,670 |
| PhD ROS2 measurement spine | 830 (4%) | 830 / 0 | 823 / 0 / 0 / 7 | 1.04 | 5.8 | 223 |
| PhD j2 work | 632 (3%) | 609 / 23 | 0 / 0 / 591 / 41 | 2.62 | 0.0 | 13 |
| aoteru controller | 547 (3%) | 547 / 0 | 0 / 0 / 547 / 0 | 0.19 | 0.0 | 53 |
| all others (scratchpads, worktrees, review trees) | 1,352 (6%) | | mostly GLM | | | |

Concentration: the first two directories hold 84% of calls, 93% of cache-write tokens (83.0 of 88.8 M), 94% of cache-read tokens (5,373 of 5,736 M) and 70% of output tokens (12.84 of 18.30 M). Opus is 10% of calls and all of it (1,221 + 881 = 2,102) is in those same two directories.

## Ranked diagnosis (hypotheses, each with the measurement that would confirm it)

1. **Two long-context coordination directories dominate consumption.** Evidence: the concentration above. Likely mechanism: very long sessions re-reading a large cached context on every call (cache-read is about 98% of the tokens counted). Not shown: session lengths, compaction behaviour, what the context consists of. Confirm by measuring calls and cache-read per session and per day in these two directories, and the share of calls whose cache-read exceeds a threshold.
2. **Opus in the same two directories is the most expensive per call.** Evidence: Opus is 10% of calls but sits entirely in the large-context directories, and the baseline found about 15.6 k cache-write tokens per Opus call. Policy already restricts Opus to exceptions; this checks whether the exceptions are being used for routine coordination. Confirm by listing Opus calls by day against the exception reasons recorded in the work.
3. **GLM carries a large delegated share but little of the cost drivers.** GLM is 33% of calls with no cache-write and small outputs per call except `j2 work` (2.62 M output over 632 calls). It is the intended overflow lane; its allowance is unknown, so this is a volume observation only.
4. **Sol/Codex consumption is dominated by templated review calls** (see `2026-11-06-sol-call-classification.md`: 98% review-class, 708 of 714 calls under 7 templates, median prompt about 93 k characters). The packet compiler (#214, wired inert in #220) is the planned remedy, gated on calibration and replay evidence.
5. **Lab Codex appears to be a separate account or plan anchor** (weekly window differs from the laptop's), so the laptop's Codex window is not the estate's whole Sol budget. Unconfirmed.

## Recommendations (to test, not to apply blindly)

- Measure first (hypotheses 1 and 2): add per-session aggregation to the existing numeric script and compare sessions that were compacted or restarted per work item against long-running ones in the same directories.
- Prefer one fresh, scoped session per work item or per PR for coordination work that can be resumed from a checkpoint; keep Opus for the recorded exception cases and require the exception reason in the work record.
- Keep delegating bounded review and implementation to GLM/Sol lanes (already policy); do not move coordination volume onto them without a measurement.
- Treat Sol call reduction as unmeasured until the replay and regression evidence exists; do not claim savings from #214/#220.
- Use the new call telemetry to close the attribution loop for Sol: `subject` and `head_sha` are now recorded for advisory and write-lane calls once the lab runs #225/#226/#227 and callers pass the flags.

## Minimal telemetry schema (proposed)

One row per paid call, joinable on existing ids: `provider`, `model` (resolved), `function` (task class or work-item kind), `subject` and `head_sha` (as in #225/#226), `input_tokens`, `cached_input_tokens`, `output_tokens`, and for Codex the provider `used_percent` for the 5-hour and weekly windows before and after the call. Only `subject`/`head_sha`/timestamps exist today (in the `|call=` suffix); model, token and window fields are not recorded by the estate and would need a separate, reviewed change.

## Not done

- Per-session analysis, before/after attribution for a representative function, and a true function taxonomy from repository activity.
- Claude allowance percent-remaining (no local source), and home-host usage.
- The independent Sol review of this report.

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
