---
title: Aoteru systemd cutover finalisation
status: execution-contract
owner: odysseus
as_of: 2026-08-21
parent: docs/aoteru-lab-execution-convergence.md
---

# Aoteru systemd cutover finalisation

Complete the remaining lab persistence step from the verified LAB-FIRST EXECUTION CUTOVER at `6b1c508`. Do not redesign prior work and do not reinstall the generic `odysseus-ui.service`.

## Goal

Make `svc:odysseus-lab` survive normal service restarts and host reboot through the dedicated `odysseus-aoteru-lab.service`, while preserving the verified private topology:

- user: `agent`
- checkout: `/home/agent/projects/odysseus-aoteru`
- venv from that checkout
- application bind: `127.0.0.1:7001` only
- isolated ChromaDB: `127.0.0.1:8101`
- tailnet exposure remains through existing Tailscale Serve only
- never bind `0.0.0.0`

## Execution

1. `git pull --ff-only` and confirm a clean working tree.
2. Re-read `odysseus-aoteru-lab.service`, `docs/aoteru-lab-execution-convergence-evidence.md`, and the current operator guide. Verify the unit still matches the live deployment before taking privileged action.
3. Inspect port 7001. If the old manually launched backend is running as `agent`, stop only that confirmed process cleanly so systemd can own the port. Do not kill unrelated processes.
4. Determine whether privileged installation is available non-interactively with a bounded check such as `sudo -n true`.
   - If it succeeds, continue autonomously.
   - If it fails because sudo needs human authentication, do not bypass, request, print, or capture the password. Complete all non-privileged prechecks, then stop at the genuine human boundary and report only the exact minimal commands the operator must run.
5. If non-interactive sudo is available, install the dedicated unit:

```bash
sudo cp odysseus-aoteru-lab.service /etc/systemd/system/odysseus-aoteru-lab.service
sudo systemctl daemon-reload
sudo systemctl enable --now odysseus-aoteru-lab.service
```

6. Verify, not assume:
   - `systemctl is-enabled odysseus-aoteru-lab.service` -> enabled
   - `systemctl is-active odysseus-aoteru-lab.service` -> active
   - unit runs as `agent`
   - listener is `127.0.0.1:7001`, not `0.0.0.0`
   - `curl -fsS http://127.0.0.1:7001/api/health` succeeds
   - existing Tailscale Serve mapping still reaches the backend and remains tailnet-only; Funnel/public exposure remains absent
   - isolated ChromaDB remains on 8101 and the canonical backend does not attach to the upstream 8100 instance
7. Exercise service-manager persistence without rebooting the host unless explicitly authorized:
   - restart the service through systemd;
   - verify it returns active and healthy;
   - verify relevant Aoteru SQLite state remains intact across the restart;
   - verify `Restart=on-failure` behaviour using the smallest safe bounded test if this can be done without corrupting work or killing unrelated services.
8. Do not perform an actual machine reboot solely to prove reboot persistence unless the operator explicitly authorizes it. `enabled` plus successful systemd-managed restart is sufficient for this pass; record full reboot verification as pending if not already observed.
9. Update the durable evidence/operator docs with the observed state. Remove stale wording saying systemd is uninstalled only if installation actually succeeded.
10. Run focused regressions relevant to service/routing/auth plus a live end-to-end local execution smoke. Do not re-run expensive unrelated work without a reason.
11. Commit cohesive changes to `dev` and push to `origin/dev` if any repo files changed. Confirm remote/local HEAD match.

## Gates

Declare the persistence step complete only if all are true:

- dedicated unit installed and enabled;
- service active after a systemd restart;
- backend healthy;
- app binds loopback only;
- private Tailscale exposure unchanged and no Funnel/public route exists;
- local routing/execution still works after restart;
- durable evidence is current;
- no new regression introduced.

Do not claim full-estate completion. Home/interface/mobile/Codex/Claude/dual-worker items remain deferred unless separately verified.

## Stop conditions

Stop only at one of:

1. verified persistent LAB-FIRST EXECUTION CUTOVER;
2. a genuine human-only sudo/privilege boundary after all possible non-privileged checks are complete;
3. a newly discovered safety/architecture defect that makes installation unsafe until fixed.

If blocked on human sudo, report only:

- why the boundary is genuine;
- the exact commands to run;
- the one-line continuation instruction to send after they succeed.

If completed autonomously, report only:

- verified service state;
- private exposure evidence;
- restart/persistence evidence;
- tests/smoke result;
- remaining deferred items;
- final HEAD SHA.
