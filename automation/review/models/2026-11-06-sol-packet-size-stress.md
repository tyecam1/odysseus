# Sol packet compiler size-stress (partial evidence)

Evidence toward the `2026-10-01-sol-packet-efficiency` size-stress acceptance criterion. It is **partial**: size-stress only. Paired historical replay and independent quality/defect regression are **not** measured here and still gate any activation of batching (see #220: batching is inert without a calibrated Policy).

## Method

`plan()` from `src/sol_packet_compiler.py` (as merged in #214, unchanged by #220) was run on synthetic items with a clearly labelled **fixture** policy (`max_items=8`, generous token bounds, evidence version `stress-fixture`). The fixture is not a calibration and must not be promoted to a default. Items shared one context key and protocol; the first 40 had pairwise compatibility certificates, the rest had none. Two cases: all items compatible (no independence requirement) and every item requiring independence (must never batch). Single run on the laptop, Python 3.14, 2026-11-06; wall time via `perf_counter`, peak memory via `tracemalloc`.

## Results

| n items | compatible: seconds | peak MB | batch / single groups | independence-required: seconds | batch / single groups |
|---:|---:|---:|---|---:|---|
| 10 | 0.008 | 0.0 | 2 / 0 | 0.004 | 0 / 10 |
| 100 | 0.70 | 0.3 | 5 / 60 | 0.31 | 0 / 100 |
| 500 | 3.26 | 0.4 | 5 / 460 | 1.57 | 0 / 500 |
| 1000 | 6.42 | 0.6 | 5 / 960 | 3.29 | 0 / 1000 |
| 2000 | 12.8 | 1.1 | 5 / 1960 | 6.45 | 0 / 2000 |
| 4000 | 25.5 | 1.6 | 5 / 3960 | 12.7 | 0 / 4000 |

## What this shows

- Cost is linear in item count (about 6.4 ms per item in the compatible case, 3.2 ms when independence is required), memory is linear and small (1.6 MB at 4,000 items), and no input raised. There is no super-linear blow-up at these sizes.
- Independence-required items never batched at any size (fail closed holds under load).
- Without certificates only the certified prefix batched; the remaining items were sent singly with a stable reason, as designed.
- The router in #220 caps a prepared collection at 16 items, so the measured range is far beyond what the wired path can present; the compiler itself is not the bottleneck.

## What this does not show

- Whether batching preserves decision quality, reduces Sol calls, or what the right Policy numbers are. Those need the paired replay and regression runs and remain owed.
- Behaviour with real (non-fixture) items, real deadlines, or hostile inputs beyond the unit tests.

## Reproduce

```python
import time, tracemalloc, sys
import sol_packet_compiler as P
from datetime import datetime, timezone
now = datetime(2026, 11, 6, 8, 0, tzinfo=timezone.utc)
def mk(i, ctx="ctx", indep=False):
    return P.Item(f"d{i:05d}", "parent", "reviewer", "Q", "review", "medium", "verification", ("e",), ("c",),
                  P.VERIFICATION_VERDICTS, P.NO_DEADLINE, indep, protocol="p", open_judgment=True,
                  shared_context_key=ctx, context_manifest_hash="a"*64, context_tokens=100, unique_tokens=10, output_reserve_tokens=10)
# FIXTURE policy only: not a calibration.
pol = P.Policy({}, 1, 1, 10**9, 10**9, 8, 1, 2, 1, 0, "stress-fixture")
print("n  groups  batch  single  needs_prep  seconds  peakMB")
for label, indep in (("compatible", False), ("independence-required", True)):
    print("--", label)
    for n in (10, 100, 500, 1000, 2000, 4000):
        items = [mk(i, indep=indep) for i in range(n)]
        certs = [(items[i].decision_id, items[j].decision_id) for i in range(min(n, 40)) for j in range(i + 1, min(n, 40))]
        tracemalloc.start(); t = time.perf_counter()
        g = P.plan(items, pol, certs, now, 0)
        dt = time.perf_counter() - t; peak = tracemalloc.get_traced_memory()[1] / 1e6; tracemalloc.stop()
        c = {k: sum(1 for x in g if x.decision.outcome == k) for k in (P.BATCH, P.SINGLE, P.NEEDS_PREPARATION)}
        print(n, len(g), c[P.BATCH], c[P.SINGLE], c[P.NEEDS_PREPARATION], round(dt, 3), round(peak, 1))
```
