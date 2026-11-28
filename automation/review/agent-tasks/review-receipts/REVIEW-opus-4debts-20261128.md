# Independent review: four lazyUsage delivery debts (Opus 5.5, read-only, 2026-11-28)

Line numbers cite lines in each packet `.diff`. EVIDENCE.md metadata (sizes, line counts) verified against the packets.

## 1. bounded-persistent-continuation (14bdc71d, merged #295)

VERDICT: APPROVE

1. Real hole closed: `worker_finalize_attested` dropped as a verification basis (L227); `verify_attempt` no longer accepts exit-zero prose as a check (L277-282); a finalised commit alone yields `unverified`/`no_deterministic_check` (L241-273). Tests rewritten failing-first (L356-425). Governance-positive and correct.
2. No overclaim: doc states "Not shipped" and every ledger row says owed, including "No independent reviewer was invoked" (L10-15, L74-89); evals yaml records shipped/merged/deployed false (L156-162). Matches EVIDENCE.
3. Minor: the new `_observe` debt branch (L299-306) reads flags (`ran_ok`, `wrote`, ...) defined outside the packet hunk — not fully verifiable from the packet; dev suite is green and this code was further superseded on dev.
4. Scope: docs/evals/src/tests only; inside allowed paths.

## 2. qualify-glm-and-glm-flash (d7304448, merged #297)

VERDICT: APPROVE_WITH_CONDITIONS

1. Confirmed P1 that GLM's approve missed: `execute_glm` emits possibly partial `provider_usage` (L324-334) into a coordinator meter that then charged it as a measured total — fixed post-merge by #301. Review record must cite #301 and the merged state f0a10e03.
2. Good fail-closed work: `glm-flash` remaps onto the `glm` launch reservation so Flash cannot bypass quota cooldown (L200-204; tests L705-713); implementation-mode refusal extended to glm-flash (L371-376, tests L767-777); model regex `fullmatch` rejects FlashX/`-latest` (L316-323; tests L628-659); usage whitelist drops launcher-invented keys (L327-334; test L679-688 proves "DO-NOT-COPY"/costUSD not copied).
3. Honest docs: EPERM socket, Flash unqualified, rollback confirmation owed, card stays `ready` (L23, L84-91, L100-109); models.yaml marks the route "qualified nowhere" (L9-11).
Conditions: record names #297+#301; card acceptance (Flash qualification, real HTTP canary, failover, rollback) stays open.

## 3. sonnet-coordinator (129540ec, rejected)

VERDICT: CHANGES_REQUIRED (rejection confirmed)

1. CONFIRMED: the `CLAUDE_CONFIG_DIR` stub removal is real — `settings.json` `disableAllHooks` write, `.credentials.json` symlink and the env override all deleted (L223-271); the docstring's control narrative deleted (L194-204); replaced by `--safe-mode --restricted`. Test inversion CONFIRMED: the disableAllHooks/symlink assertions deleted, replaced by flag assertions and `not .../config.exists()` (L908-954).
2. Rejection justified: the removed control had live evidence (hook canary NOT firing, 2026-11-18); the replacement flags' isolation is asserted, never evidenced here; the operator's real user config (hooks, plugins, user CLAUDE.md) re-enters the lane, and the diff's own doc defers the unattended canary and permission/billing evidence (L160-169). Removing a proven safety gate without replacement evidence is a legitimate P1.
3. Mitigations real but insufficient: endpoint-override refusal (L212-215), pre-inference auth attestation (L241-255), `--tools "" --disallowedTools "*"` (L266).
4. Dead code: `_lane_qualified`'s second clause `lane != "claude-sonnet" or lane in executors` (L357-363) is a tautology; no distinct `claude-sonnet` executor is added to estate.yaml, so that registry gate is unenforced (the runtime 5.5 attestation check, L469-475, carries the protection).
5. Retake-worthy non-rejected parts: owner-priority fence in `_ordered` (L499-511; test L600-609), token reservation/reconciliation (L326-341, L415-434), legacy-plan replay fence (L393-406).

## 4. cross-repository-development-observer (a6f5d34c, open PR #309)

VERDICT: APPROVE_WITH_CONDITIONS

1. Docs-only, in scope; read-only discipline in reproduction SQL (`mode=ro`, `query_only`, ROLLBACK; L90-113); prompts/secrets/domain content explicitly excluded (L34, L59, L122).
2. Figures internally consistent (212=194+17+0+1 at L29; debts 15=8+2+2+3 at L15/L61; 15 retrospective rows, L69-83) but unverified against live state; the doc hedges correctly (L30, L90) — no overclaim found.
3. Governance gap: the GLM-5.3 APPROVE exists only as PR #309 body text, no receipt file, while the doc itself argues verdicts must be durably joinable (L120-122). Condition: attach a durable review receipt before merge; treat baseline numbers as unverified until reproduced.
