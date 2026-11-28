# System One decision layer — independent review (Opus 5.5)

## VERDICT: APPROVE_WITH_CONDITIONS

Governance: no gate bypass found. The estate_router.py addition (diff L408+) is purely additive and reuses existing helpers; it does not modify run_task, preflight, lease or approval paths. Stock config is inert: all adapters `enabled: false`, `bindings: []` (models.yaml L59-75), and every eligibility check fails closed (host, placement=local, contract, language, size, option bounds, latency, brier, accuracy, min_confidence, qualified_executors, reviewed, held_out_evidence — L481-493; omitted fields default to failing values). Hosted Jev is unreachable from this path: routing requires placement=="local", and Adapter.decide requires `remote_authorized=True` plus a token (system_one.py L764-770); the router never passes a token. Local endpoints are pinned to http://127.0.0.1/::1 with no path/query/credentials (L747-758); redirects refused and tested. No secrets in the diff; the token field is repr=False and never populated.

## Findings

1. (overclaim, note L40) "145 tests passed" is not corroborated: the controller verified 8 delivery tests plus 135 with the router/models suites. The 145 includes suites this review could not confirm, and the note itself reports the full HTTP route suite "did not complete". Reconcile or restate as per-suite counts.
2. (governance condition, estate_router.py L481-493) `reviewed`/`held_out_evidence`/quality metrics are self-attested YAML with no link to a review artifact. Acceptable while bindings=[], but the first binding change must cite its review evidence per the note's own remaining-acceptance list.
3. (minor, estate_router.py L497-499, L537-541) if the chosen call fails after route selection, `route` stays set, so the decision row records host_id and executor="system-one" for a call that never succeeded (concrete_model None). Telemetry accuracy only.
4. (minor, system_one.py L846-848 vs estate_router.py L515) tie handling is inconsistent: decode hard-rejects any tied choice distribution (provider_selection_mismatch) before the router's tie→low_confidence branch can apply; genuine ties are dropped rather than escalated. score/noul/rank unaffected.
5. (minor, system_one.py L826-829) a rank response carrying an abstention flag is silently treated as answered; abstention is only read in the non-rank branch.
6. (test gap) of ~12 binding-eligibility dimensions only min_accuracy is exercised (tests L995-1002); the decision_telemetry_unavailable fail-closed path (L564-566) and the CAS race (L608-612) are untested. Tests are otherwise substantive, not shapeless: they pin the 15/9 escalation split (L1084-1086), tuner-flip at unchanged probabilities, escalation precedence, wire shape, redirect refusal, telemetry round-trip and no-text-leak.

Models.yaml marks nothing qualified; the note's status ("zero promoted bindings, acceptance pending") matches the code.
