Resume and execute the Aoteru programme from `@GO.md` and `@docs/aoteru-autonomous-programme-state.md`.

Treat each wakeup as continuation of the same programme, not a status-check turn.

On every iteration:
1. pull/sync only if safe and needed;
2. read current programme state;
3. if any workstream is `active` or `eligible`, execute the highest-value unblocked substantive work next;
4. do not stop after one tiny edit if more meaningful work is available in the same iteration;
5. delegate bounded token-heavy implementation/review to Codex, qualified local models, and deterministic tooling when useful;
6. independently verify material changes;
7. commit and push cohesive verified checkpoints;
8. update programme state;
9. continue until this iteration reaches a genuine runtime/tool/context limit, then leave durable state for the next loop wakeup.

Human/physical/sudo/credential/host blockers must be recorded once and skipped while independent work remains. Do not repeatedly ask for them.

Do not emit a progress-only final answer while executable work remains. Use the available iteration to advance the system.

When no `active` or `eligible` repository-controlled work remains, run the final convergence audit from `GO.md`. Only then report stable completion or the exact irreducible external gates.
