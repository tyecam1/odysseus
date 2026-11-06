# Sol call classification (partial, laptop rollouts, keyword and template level)

Addendum to `2026-11-04-sol-fragmentation-baseline.md`, taking a first, **crude** step at its "classification of each call" gap. It is partial: it classifies by prompt template and keywords only and does not establish which calls were avoidable.

## Method

For each laptop Codex rollout with a Sol-class model (714 at sampling on 2026-11-06; the earlier baseline counted 639 on 11-04), the longest `user` message was read in memory, bucketed by keyword rules, and fingerprinted by its first 300 characters with digits normalised. Only counts and token figures were kept; no prompt text is reproduced or committed. The script is below.

## Results

| Bucket (first match wins) | Calls | Share | Median uncached input |
|---|---:|---:|---:|
| independent review (keywords: adversarial/independent/read-only review, verdict) | 701 | 98% | 29.6 k |
| implementation or fix (apply patch, write lane, governance note) | 11 | 2% | 214 k |
| design consult | 1 | <1% | 1.67 M |
| other / unclassified | 1 | <1% | 1.10 M |

Prompt-prefix fingerprints: **13 distinct** across 714 calls; **7 are shared by more than one call and cover 708 calls**, the largest groups being 449, 182, 47 and 18 calls. The median prompt is about 93 k characters (p90 about 167 k).

## What this shows and does not show

- The laptop's Sol usage is dominated by one shape: templated, review-class calls. Nearly all calls reuse a small number of prompt templates, so the repeated part of each prompt is large, consistent with the task's "repeated setup/context cost per call" hypothesis, and consistent with the earlier finding that calls are not near-empty.
- The `verdict` keyword is broad, so the 98% review share is an upper bound on "review" and a lower bound on nothing else; it does not separate a **necessary independent review** from **repeated verification of unchanged work**. A shared template header also does not mean a shared subject, so the 708 figure is not a count of redundant calls.
- Separating those needs the subject of each call (for example the PR and head commit being reviewed) and whether the head changed between calls. That is not in these numeric fields and was not read.
- Lab and home usage are not covered (see `system-efficiency/2026-11-06-lab-codex-telemetry.md`).

## Script

```python
"""Keyword bucketing of the first user message of each laptop Codex rollout. Only counts are printed."""
import glob, json, os, re, collections
B = collections.Counter(); tok = collections.defaultdict(list); n = 0; rounds = collections.Counter()
rules = [
 ("independent_review_round2plus", re.compile(r"\bROUND\s*([2-9]|\d\d)\b", re.I)),
 ("independent_review", re.compile(r"adversarial review|independent (adversarial )?review|review \(read-only\)|read-only review|\bAPPROVE\b.*\bCHANGES\b|verdict", re.I)),
 ("design_consult", re.compile(r"design consult|consult\b|which of two|decide between|recommend", re.I)),
 ("implementation_or_fix", re.compile(r"implement|apply .*patch|git apply|fix round|governance note|write lane|you are running under", re.I)),
 ("ingest_or_extraction", re.compile(r"extract|ingest|chatgpt export|ledger", re.I)),
]
for p in glob.glob(os.path.expanduser("~/.codex/sessions/**/rollout-*.jsonl"), recursive=True):
    first = None; model = None; last_total = None
    try:
        for line in open(p, encoding="utf-8", errors="replace"):
            try: e = json.loads(line)
            except ValueError: continue
            pl = e.get("payload") or {}
            if pl.get("type") == "turn_context" or e.get("type") == "turn_context": model = pl.get("model") or model
            if pl.get("type") == "message" and pl.get("role") == "user":
                txt = " ".join(str(c.get("text") or "") for c in (pl.get("content") or []) if isinstance(c, dict))
                if len(txt) > len(first or ""): first = txt[:6000]
            if pl.get("type") == "token_count":
                t = ((pl.get("info") or {}).get("total_token_usage")) or {}
                if t: last_total = t
    except OSError:
        continue
    if not model or "sol" not in model: continue
    n += 1
    cat = "other_or_unclassified"
    if first:
        for name, rx in rules:
            if rx.search(first): cat = name; break
    B[cat] += 1
    if last_total: tok[cat].append(last_total.get("input_tokens", 0) - last_total.get("cached_input_tokens", 0))
print("sol rollouts", n)
for k, v in B.most_common():
    xs = sorted(tok[k]); med = xs[len(xs)//2] if xs else 0
    print(f"{k}: {v} ({100*v/n:.0f}%), median uncached input {med}")
```
