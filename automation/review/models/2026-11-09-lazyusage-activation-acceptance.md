# /lazyUsage activation acceptance (2026-11-09)

Lab is the sole execution host; the laptop holds only the user-level skill and the `aoteru` client.

## Change
- PR #249 (merge af856608): `scripts/agentic_portfolio.py` resolves repo roots from the host-local `~/.aoteru/config.local.json` when `AI_ROOT`/`HOUSEHOLD_ROOT`/`PHD_ROOT` are unset (environment still wins; relative, wrong-shape, malformed or absent values stay `root_environment_unset`).
- Deployed: lab checkout `/home/agent/projects/odysseus-aoteru` moved to `deploy/dev-20261109` at af856608. Rollback: `git checkout deploy/dev-20261106` (cbf7d43b); recorded in `~/.aoteru/rollback-lazyusage-20261109.txt` on the lab. The lab service was NOT restarted; `src/estate_router.py` changes from #246 are inert until the next governed restart.

## Real-path evidence
1. Skill: laptop `~/.claude/skills/lazyUsage/SKILL.md` is byte-identical to `.claude/skills/lazyUsage/SKILL.md` on `origin/dev`. A fresh `claude -p` session lists `lazyUsage` in both `skills` and `slash_commands`.
2. Discovery, lab, fresh SSH, `env -i` (no root variables): `scope_complete: true`, `unavailable: {}`, totals odysseus 45, misumi 63, obsidian-phd 24. Before the fix the same call reported misumi and obsidian-phd `root_environment_unset`.
3. Governed task, initiated from the laptop (`aoteru lab ... --repo odysseus --capability local-fast`), decision `a161c8af-275c-4a7e-ad2c-285e534e6e66`: routed and executed on `hz2-workstation` (`attested: true`, `transport: local`), `verification_outcome: pass`, `deterministic_gate: pass`. Output "Misumi has the most items with 63 ... total ... 132" was checked independently: 45+63+24 = 132. The task was bounded and read-only, with facts supplied in the prompt; `local-fast` is a reasoning surface and is not evidence of command execution (see aoteru CLI quirk 3).

## Verification and gates
- Tests: `tests/test_agentic_portfolio.py` + `tests/test_agentic_context.py` 340 passed, 1 skipped on the lab. No CI workflow produced checks for PR #249 (empty status rollup).
- Review: Sol (`gpt-6-sol`, lab catalogue newest non-astra; lab codex 0.155.1) FAILED with a real usage-limit error: "You've hit your usage limit ... try again at 3:18 PM." The review ran same-family GLM-5.3 (`claude-glm`, read-only): APPROVE with non-blocking findings; the absolute-path guard and extra tests were applied. **This is same-family GLM, not a Sol or cross-family verdict. A Sol review of af856608 is owed after the stated reset.**

## Usage evidence at acceptance (laptop reads)
- Codex (rollout telemetry 2026-11-09 11:17Z): 5h window 50% used, resets 15:18:32Z; weekly 49%, resets 2026-11-13 17:03Z; credits 0. Lab controller `provider_health` simultaneously says `quota_exhausted` (retry_after 2026-11-08 14:14Z, already past); the live Sol call hit the limit. Treat Codex as unavailable until reset.
- Claude: logged in (claude.ai); no allowance signal available: unknown.
- GLM: `glm-5.3` call succeeded; remaining quota unknown. Claude Code warns that it does not recognise the `glm-5.3` model id (context-window assumption only).

## Outstanding
- Sol review of af856608 (owed).
- Lab Misumi and obsidian-PhD checkouts are stale (151 and 143 commits behind origin/main); discovery reads their working trees, so queue contents may lag. Updating them is a separate governed action.
- Home PC worker unreachable (SSH timeout); irrelevant to lab-only execution.
- Persistent edit of the lab `~/.bashrc` was denied by the permission classifier and is no longer needed.
