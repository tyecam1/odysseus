# Finance goal registries (runtime mirror)

Read-only mirror of the canonical finance goal registries owned by
`tyecam1/misumi@main`:

- `finance-paper-trading-goals.json` ← `tyecam1/misumi@main:config/finance-paper-trading-goals.json`
- `finance-market-media-intelligence-goals.json` ← `tyecam1/misumi@main:config/finance-market-media-intelligence-goals.json`

Misumi owns the goal definitions and personal finance policy (see
`misumi/docs/core/finance-paper-trading-goals-v0.1.md` and
`misumi/docs/core/finance-market-media-trend-goals-v0.1.md`). Odysseus owns
the runtime: `src/finance_goals.py` derives current lock state from these
definitions plus evidence receipts in
`automation/review/finance/receipts/` on every evaluation — nothing here is
manually set, and saving these files alone implements nothing.

`runtime-evaluation.json` is Odysseus-owned runtime policy (receipt TTLs,
accepted independent verifier lanes), not goal authority.

When Misumi updates a canonical registry, re-sync the mirror in the same
change that adopts it; the evaluator records each mirror's sha256 in every
evaluation result so drift is visible.

Simulation only. No real-money orders, exchange execution credentials,
leverage, deposits or financial commitments are authorised by anything in
this directory.
