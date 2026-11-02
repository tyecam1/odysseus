# AM command and Claude Code compatibility assessment

Status: implementation candidate, subject to local tests and real host verification (2026-10-29)
Owner: tyecam1/odysseus

## Names and authority

- **Aoteru**: persistent head human-facing assistant persona, with task-sensitive Misumi persona routing.
- **Misumi**: personal/household knowledgebase and persona/household policy authority, owned by `tyecam1/misumi`.
- **Odysseus**: domain-neutral execution, transport, authentication, model/host routing and leases. No second knowledge authority.
- **AM**: the operator's client command, not a distinct agent, model, service, or authority.

The existing `aoteru` CLI is a compatibility alias for `am`. The package, `aoteru.py` module, token-store path `~/.aoteru/client.json` and repo names need not be renamed; renaming those would break callers without removing practical friction.

## Contract

| Invocation | Endpoint | Meaning | Minimum token scope |
| --- | --- | --- | --- |
| `am "question"` | `POST /misumi/respond` | Conversational assistant; persona `auto`; session `am-cli` | `misumi:execute` |
| `am chat "question" --persona sanji` | `POST /misumi/respond` | Explicit persona; no new authority | `misumi:execute` |
| `am chat "question" --json` | `POST /misumi/respond` | Full source/provenance fields | `misumi:execute` |
| `am preflight "task"` | `POST /api/estate/preflight` | Routing/lease recommendation | `estate:read` or `estate:execute` |
| `am ask "task"` | `POST /api/estate/run` | Task execution, not ordinary chat | `estate:execute` |

The conversational CLI uses the explicit owner-scoped `am-cli` session key by default (overridable with `--session`), rather than submitting unrelated stateless requests. The CLI never infers permission from persona identity. Unknown personas remain subject to the server's validation. Keep the prior `aoteru` entry point and existing config. Existing scripts and `AGENTS.md` references remain valid.

## Claude Code: two different integration questions

**Aoteru as a Claude Code tool: feasible now.** Odysseus already provides a scoped Claude Agent skill under `integrations/claude/skills/odysseus` for the `/api/codex/*` surfaces, and `am sync` installs a separate scoped estate-routing skill. For conversational access, `am chat` can be called from a locally authorised Claude Code terminal; a dedicated stdio MCP bridge could wrap `/misumi/respond` and preflight in a later stage, but the existing HTTP endpoints are not themselves MCP endpoints. This retains Claude Code as the coding harness and Odysseus as the executor/routing authority.

**Aoteru as Claude Code's model provider: not directly supported by current Odysseus routes.** A custom `ANTHROPIC_BASE_URL` must provide Anthropic-compatible `POST /v1/messages` request/response semantics, model names, message/tool blocks, streaming SSE, and relevant headers. Current `/misumi/respond` is a single-response persona JSON protocol and `/api/estate/run` is a task envelope with execution semantics; neither is wire-compatible. Anthropic states that routing Claude Code to non-Claude models through gateways is not officially supported even if an unofficial translation works. The existing FCC proxy on the home host provides a separate technical precedent, not evidence that the Aoteru API passes Claude Code interoperability tests.

Sources checked:
- https://code.claude.com/docs/en/llm-gateway
- https://code.claude.com/docs/en/llm-gateway-protocol
- https://code.claude.com/docs/en/llm-gateway-connect
- https://code.claude.com/docs/en/mcp

## Verification and stopping condition

1. Run `pytest -q tests/test_laptop_client.py` on the new branch; verify `pipx` install exposes both `am` and `aoteru` with unchanged config.
2. Confirm `am --help`, `am status`, `am "Hello"` and `am chat "Hello" --json` on an authenticated host with `misumi:execute` scope.
3. Verify an `estate:execute`-only token is denied for chat, and a `misumi:execute`-only token cannot invoke estate task execution.
4. Run `am sync` and inspect the Claude skill; verify Claude Code can invoke `am chat` locally without adding a model gateway. Do not commit or expose secrets.
5. Only pursue a `/v1/messages` adapter if an actual Claude Code workflow demands replacing the model provider rather than using tools; test startup, tool calls, SSE events, model aliases, cancellation, timeouts, and authorization against a pinned Claude Code release before claiming compatibility.

**Deployment limit:** GitHub changes cannot install a command on the laptop or verify reachability of a private LAN host. Local installation, token provision and end-to-end smoke tests remain human/host gates.
