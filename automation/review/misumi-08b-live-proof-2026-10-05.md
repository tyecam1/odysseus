# Application -08b - live proofs on a scratch instance (2026-10-05)

Release under test: home `ce8d353a8f` (deployed, unchanged). Instance: labelled side-by-side `:1420` with
`MISUMI_ROUTING_STATE_ROOT` pointing at the scratch directory `routing-scratch-08b` under the home release folder;
the household store behind `:420` was not touched (the script never addresses it). Script:
`evals/misumi-routing/live/demo-08b-scratch-ratification.ps1`. Token read from the host USER env, never printed.

| Item | Claim | Observed | Verdict |
| --- | --- | --- | --- |
| -08b(a) | An eligible candidate with no ratification act does not promote, across a real process restart and further traffic | A1 eligible / `user-ratification`, 0 active revisions; after kill + restart and unrelated + cue-mentioning requests: A3 route still `misato` via `routing-contract-v0.1`, A4 candidate unchanged, 0 active revisions | PASS |
| -08b(b) | Contradictory evidence is handled and blocks promotion | B1 eligible (3 corrections); one contradicting correction (Erwin) -> B2 `shadow` / `contradicting-evidence`, contradicting count 1; B3 promote -> HTTP 409 `candidate ... is 'shadow', not eligible` | PASS |
| -08b(c) | Reject is terminal, preserves evidence, cannot be bypassed | C2 reject 200 (`rejected`, reason + time recorded); C3 re-reject 409 `already rejected (terminal)`; C4 promote-after-reject 409; C5 supporting evidence 3 -> 3; C6 route stays `ginko` | PASS |
| -08b(d) | Conversational proposal surface | Not implemented here; folded into -12 (embodiment) with the runtime-first design | OPEN |

Unit counterpart: `test_silence_never_promotes_an_eligible_candidate` (three simulated restarts, repeated cue
traffic, store snapshot byte-identical, promotable only by an explicit authorisation act).

Transport notes (script defects found and fixed during this run, not product findings): a PowerShell function
returning `byte[]` is unrolled to `object[]` and corrupts the request body (HTTP 422 `json_invalid`; return
`,$bytes`); the candidates API names its list `active_revisions`; Windows PowerShell 5.1 hides HTTP error bodies
unless they are read from `$_.ErrorDetails`.

## Raw output

```
scratch-up root=C:\Users\User\odysseus-releases\routing-scratch-08b
A1-eligible-before-restart {"id":"aff-7df783caa6f6","cue":"cleaning+rota","status":"eligible","awaiting":"user-ratification","to":"jin","base":"misato","corr":3}
A1-active-revisions-before=0
A2-restarting
A3-route-after-restart-no-ratification {"method":"routing-contract-v0.1","reasons":["cleaning","rota"],"source":"auto","persona":"misato"}
A4-candidate-after-restart {"id":"aff-7df783caa6f6","cue":"cleaning+rota","status":"eligible","awaiting":"user-ratification","to":"jin","base":"misato","corr":3}
A4-active-revisions-after=0
B1-eligible {"id":"aff-7164d329a756","cue":"listening+records","status":"eligible","awaiting":"user-ratification","to":"misato","base":"jin","corr":3}
B2-after-contradiction {"id":"aff-7164d329a756","cue":"listening+records","status":"shadow","awaiting":"contradicting-evidence","to":"misato","base":"jin","corr":3}
B2-contradicting-count=1
B3-promote-contradicted {"detail":"{\"detail\":\"candidate aff-7164d329a756 is \u0027shadow\u0027, not eligible\"}","status":409}
C1-eligible {"id":"aff-6bbed81d54b9","cue":"pests+watering","status":"eligible","awaiting":"user-ratification","to":"sanji","base":"ginko","corr":3}
C2-reject {"json":{"rejected":true,"candidate":{"awaiting":null,"base_persona":"ginko","candidate_id":"aff-6bbed81d54b9","confidence":{"basis":"count of supporting evidence by type (durable=3, correction=1, confirmation=1), minus contradictions; never bypasses ratification","corrections":3,"durable":0,"score":3},"contradicting_evidence":[],"created_at":"2026-10-05T17:34:48Z","cue":["pests","watering"],"proposed_persona":"sanji","rationale":"3 consistent correction(s) across separate interactions","status":"rejected","supporting_evidence":["rev-ev-c474ae17b477","rev-ev-47dc59fd6c58","rev-ev-ef1e986227fd"],"updated_at":"2026-10-05T17:34:49Z","rejection":{"reason":"operator rejects (scratch proof)","at":"2026-10-05T17:34:49Z"}}},"status":200}
C3-reject-again {"detail":"{\"detail\":\"candidate is already rejected (terminal)\"}","status":409}
C4-promote-after-reject {"detail":"{\"detail\":\"candidate aff-6bbed81d54b9 is \u0027rejected\u0027, not eligible\"}","status":409}
C5-candidate-after {"id":"aff-6bbed81d54b9","cue":"pests+watering","status":"rejected","awaiting":null,"to":"sanji","base":"ginko","corr":3}
C5-supporting-evidence before=3 after=3
C6-route-after-reject {"persona":"ginko","method":"routing-contract-v0.1"}
scratch-stopped listeners=0
DONE (household store on :420 untouched)
```
