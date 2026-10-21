# Routing contract v0.2 - ratification, wiring, deployment and real-path regression (2026-10-06)

Ratified by the user on 2026-10-06 (Option A): routing contract v0.2 and the `routing.aliases` manifest field; learned routing-revision
cues stay on exact `keyword_present` matching and are neither migrated nor reinterpreted by stemming; the v0.1 kill switch is required and
v0.1 is the immediate rollback path. Contract and manifest: misumi PR #65 (`docs/core/aoteru-routing-contract-v0.2.md`,
`config/personas.yaml` `routing.aliases`, parity fixture, dry-run port). Runtime: odysseus PR #113 (`src/misumi_routing_v02.py`,
`resolve_auto_lead` switch, `resolve_auto_lead_v01` retained verbatim, `MISUMI_ROUTING_ALGORITHM=v0.1`). Deployed: home release
`1afc1ddedc` (staged side-by-side, then cut over; rollback = re-Install `867a9c667c`, or simply set the kill switch and restart).

A first push of the wiring (#112) failed CI on a string-escape error in a parity-digest test that I added after my last local run and
did not run; it was closed and replaced by #113 (143 passed, 3 skipped on a fresh dev tree). Kept here, not hidden.

## Real-path regression (`evals/misumi-routing/live/regress-v02.ps1`, items pinned in `regress-items.json`)

Every request goes through a DEPLOYED `/misumi/respond` with `persona: auto`; expectations (`expect_v02` / `expect_v01`) were computed from
the live manifest. Rows: the 12 deterministic fixtures + all 166 corpus prompts (dev 78, held-out v1 44, held-out v2 44). Follow-up rows send
their prior prompt first (persisted) and require it to have routed to the labelled prior lead; a row whose precondition fails is SKIPPED and
reported, not forced.

| Run | Target | Matched | Skipped | Wrong method string | Stores before -> after |
| --- | --- | --- | --- | --- | --- |
| v0.2 (default) | scratch `:1420`, release `1afc1ddedc` | **177 / 177** (dev 78/78, fixtures 12/12, held-out 43/43 and 44/44) | 1 | 0 | empty -> empty |
| v0.1 via `MISUMI_ROUTING_ALGORITHM=v0.1` | scratch `:1420` | **178 / 178** (all four groups) | 0 | 0 (no v0.2 field leaked) | empty -> empty |
| v0.2 (default) | **production `:420`** | **177 / 177** | 1 | 0 | persona-state 0/0, routing 2 candidates / 0 active -> unchanged |

The one skipped row (`hf1`) is a precondition miss, not a routing failure: its prior prompt "Plan meals for the week" routes to `erwin`
under v0.2 (the stem `plan` ties `planning` with `meals` and manifest order picks erwin - the recorded `c05` weakness), not to the
labelled `sanji`.

## Learned revisions keep exact semantics (`evals/misumi-routing/live/learned-exact-proof.ps1`, scratch)

| Step | Observed |
| --- | --- |
| L1/L2 base | "Check the cleaning rota" -> misato (reasons `cleaning, rota`); "Who cleaned the kitchen?" -> misato by STEM, reason literal `cleaning` |
| L3 | durable instruction "for cleaning questions, from now on use Jin" -> promoted, `user_instruction` authority, cue `cleaning` |
| L4 | exact cue fires: `routing-contract-v0.2+learned-revision`, persona jin, `base_selected` misato recorded |
| L5 | **stem-only "cleaned" does NOT fire the learned revision** (still the base route misato) |
| L6 | an unrelated cue is unaffected (l via finance, anomaly) |
| L8 | after a real restart the exact cue still fires |
| L9-L11 | rollback restores the v0.2 base route for both prompts |

## Raw output

### v0.2 scratch and v0.1 kill-switch scratch

```
===V02-SCRATCH=== 
regress target=scratch algorithm=v0.2 port=1420 short=1afc1ddedc
stores before: persona_state candidates=0 active=0; routing candidates=0 active=0
SKIP hf1: prior turn routed to 'erwin', labelled prior lead is 'sanji'
stores after:  persona_state candidates=0 active=0; routing candidates=0 active=0
RESULT algorithm=v0.2 target=scratch matched=177/177 skipped=1 wrong_method_string=0  [dev=78/78 fixtures=12/12 heldout=43/43 heldout2=44/44]
DONE
===V01-KILLSWITCH-SCRATCH=== 
regress target=scratch algorithm=v0.1 port=1420 short=1afc1ddedc
stores before: persona_state candidates=0 active=0; routing candidates=0 active=0
stores after:  persona_state candidates=0 active=0; routing candidates=0 active=0
RESULT algorithm=v0.1 target=scratch matched=178/178 skipped=0 wrong_method_string=0  [dev=78/78 fixtures=12/12 heldout=44/44 heldout2=44/44]
DONE
===ALLDONE===

[exited with code 0]
```

### v0.2 production

```
regress target=prod algorithm=v0.2 port=420 short=REPLACE_SHORT
stores before: persona_state candidates=0 active=0; routing candidates=2 active=0
SKIP hf1: prior turn routed to 'erwin', labelled prior lead is 'sanji'
stores after:  persona_state candidates=0 active=0; routing candidates=2 active=0
RESULT algorithm=v0.2 target=prod matched=177/177 skipped=1 wrong_method_string=0  [dev=78/78 fixtures=12/12 heldout=43/43 heldout2=44/44]
DONE
```

### learned-revision exact-semantics proof

```
scratch-up release=1afc1ddedc (routing contract v0.2 is the default)
L1-base-exact {"method":"routing-contract-v0.2","base":null,"learned":false,"reasons":["cleaning","rota"],"persona":"misato"}
L2-base-stem-only {"method":"routing-contract-v0.2","base":null,"learned":false,"reasons":["cleaning"],"persona":"misato"}
L3-durable-instruction {"note":{"evidence_id":"rev-ev-5254d1c08bde","evidence_type":"explicit_durable","cue":["cleaning"],"candidate_id":"aff-5f0f5c4b5471","candidate_status":"eligible","base_persona":"misato","proposed_persona":"jin","state":"active","promotion":{"authorised_by":"user_instruction","evidence_id":"rev-ev-5254d1c08bde","revision_id":"rr-3d726dc851ce","previous_revision_id":null}}}
L4-exact-cue-fires-learned {"method":"routing-contract-v0.2+learned-revision","base":"misato","learned":true,"reasons":["learned:rr-3d726dc851ce cue=cleaning"],"persona":"jin"}
L5-stem-only-does-NOT-fire {"method":"routing-contract-v0.2","base":null,"learned":false,"reasons":["cleaning"],"persona":"misato"}
L6-other-cue-unaffected {"method":"routing-contract-v0.2","base":null,"learned":false,"reasons":["finance","anomaly"],"persona":"l"}
L7-restarting
L8-after-restart-exact-cue {"method":"routing-contract-v0.2+learned-revision","base":"misato","learned":true,"reasons":["learned:rr-3d726dc851ce cue=cleaning"],"persona":"jin"}
L9-rollback status=200
L10-after-rollback {"method":"routing-contract-v0.2","base":null,"learned":false,"reasons":["cleaning","rota"],"persona":"misato"}
L11-after-rollback-stem-only {"method":"routing-contract-v0.2","base":null,"learned":false,"reasons":["cleaning"],"persona":"misato"}
DONE (household stores untouched)
```

## Correction (2026-10-06 evening, Sol review)

The claim above that a learned revision "fires only on its exact cue" is imprecise. Learned cues are matched over the closed variant set `keyword_variants` (plural, `-ing`/`-e`; from -07), so `clean rota` fires a revision stored as `cleaning`; v0.2's base stemming is not applied to learned cues. The proof showed that `cleaned` does not fire; it did not test every variant. The v0.1 kill switch (`MISUMI_ROUTING_ALGORITHM=v0.1`) restores the v0.1 base router only; the 178/178 kill-switch run used empty learned stores, so it did not test active overlays, which have their own switch (`MISUMI_ROUTING_ADAPTATION=0`). 177/177 is a deployment-conformance result (expected values come from the same implementation and manifest, and one follow-up row is skipped when its precondition disagrees), not an independent accuracy measurement.

