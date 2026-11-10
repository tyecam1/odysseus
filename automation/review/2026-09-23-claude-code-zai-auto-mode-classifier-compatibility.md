# Claude Code Auto Mode on the Z.AI launchers: partial evidence (steps 1-3 only)

Task: `2026-09-23-claude-code-zai-auto-mode-classifier-compatibility`. **Status of this document: partial.** The root-cause hypothesis is supported by upstream documentation and by the launcher configuration, but the reported interactive failure was **not retested under matching conditions and nothing was fixed** here. No launcher or setting was changed. The task stays open.

## Environment (laptop, 2026-11-10)
- Claude Code installed: **2.1.322** (`claude --version`). The card reports the failure on **2.1.319**; the install has since been updated twice (renamed backups `claude.exe.old.*` dated 2026-11-06 and 2026-11-10 are present).
- Command chains resolved with `Get-Command -All`: `claude.exe`; `claude-glm.cmd` runs `claude-glm-impl.ps1` (GLM-5.3); `claude-glm-flash.cmd` runs `claude-glm-flash.ps1`, which runs the same `claude.exe` with `--settings %USERPROFILE%\.aoteru\claude-glm-settings.json`.
- `claude-glm-flash.ps1` (credential-bearing lines were withheld when reading) sets, process-locally: `ANTHROPIC_BASE_URL=https://api.z.ai/api/anthropic`, the Haiku, Sonnet and Opus tier defaults to `glm-5.3-flash[1m]`, `CLAUDE_CODE_AUTO_COMPACT_WINDOW=1000000`, and **`CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1`**. It does not set `CLAUDE_CODE_AUTO_MODE_SERVER`.
- A Flash launcher therefore exists on the laptop (distinct from `claude-glm`); its credential is DPAPI-protected to this Windows user, so it is not portable to the lab host.

## Upstream contract (Claude Code CHANGELOG, `anthropics/claude-code`, read 2026-11-10)
- **2.1.319:** "Changed auto mode with telemetry or feature flags off, including behind LLM gateways: calls the server can't check are asked about or denied, with no fallback to the built-in classifier; set `CLAUDE_CODE_AUTO_MODE_SERVER=0` to keep using it (Bedrock, Vertex and Foundry are unchanged)."
- 2.1.317: fixed auto mode failing every turn when a gateway answers 403 or 422 to the server-side check.
- 2.1.321 and 2.1.322: no auto-mode change relevant to gateways.
- Earlier entries record `CLAUDE_CODE_AUTO_MODE_SERVER=0` as the documented opt-out of the server-side classifier.

## Hypothesis (supported, not proven here)
The Flash launcher turns non-essential traffic (telemetry) off and points `ANTHROPIC_BASE_URL` at a non-Anthropic endpoint. That combination is a plausible match for the 2.1.319 behaviour in which calls "the server can't check are asked about or denied" without the built-in classifier; no classifier or server trace here shows that this path was taken. `CLAUDE_CODE_AUTO_MODE_SERVER=0` is a **documented candidate workaround** (an opt-out of server review); whether the Z.AI model supplies usable local classifier verdicts is untested. Applying it would be a one-line, reversible, launcher-scoped addition. `claude-glm-impl.ps1` was not read in this pass and may share the condition.

## Probe (headless, ephemeral child-process environment, no file changes)
Command, run from a temporary directory: pipe `Use the Bash tool to run exactly: echo AUTO_PROBE_OK ...` into `claude-glm-flash.cmd --print --permission-mode auto --no-session-persistence`.

| Run | `CLAUDE_CODE_AUTO_MODE_SERVER` | Result |
|---|---|---|
| A | unset | output `AUTO_PROBE_OK`, exit 0 |
| B | `0` | output `AUTO_PROBE_OK`, exit 0 |

The two headless probes on 2.1.322 both succeeded and returned the expected output; **the reported interactive 2.1.319 failure was not retested under matching conditions, and the probe does not discriminate between the two settings.** No tool transcript or debug record shows that Bash executed or that a classifier reviewed it (some actions are allowed without classifier review), so classified execution is not inferred. It does not show that interactive Auto Mode is restored: headless print mode may not exercise the same prompt path, and the effective model, classifier requests and `/status` Auto Mode state were not inspected. Standard GLM (`claude-glm`) was not probed.

## Open
1. Reproduce in an interactive session on 2.1.322 (`/status` Auto Mode state; whether a harmless shell command runs without a prompt and a risky one is held).
2. If it still asks, test the candidate workaround `CLAUDE_CODE_AUTO_MODE_SERVER=0` in an ephemeral environment for `claude-glm` and `claude-glm-flash`, then apply it launcher-scoped with a documented rollback; keep native `claude` unchanged.
3. Independent verification must check classified behaviour, not just the disappearance of a warning.

No safety bypass was attempted and no credential was read or printed. Independent (Sol) review of this document is owed.
