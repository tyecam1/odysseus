# Runtime-state and deployment-sidecar bake-off

## Objective

Determine whether existing JSON/SQLite state and manual Docker operations are sufficient before introducing PocketBase, Supabase, Appwrite, Coolify or n8n.

## Decision sequence

1. Inventory current runtime state, write rate, concurrency, query and backup requirements.
2. Measure defects in existing JSON/SQLite and Docker operations.
3. Compare the smallest plausible alternatives in isolated pilots.
4. Reject any candidate that duplicates task, memory, approval or research authority.

## Candidate boundaries

- PocketBase: compact local derived runtime state only.
- Supabase/Appwrite: defer unless multi-user auth, realtime or remote API requirements are demonstrated.
- Coolify: service deployment and rollback only after service inventory stabilises.
- n8n: connector and notification plumbing only for a named integration gap.

## Acceptance criteria

The report includes a no-change baseline, recurring maintenance, secrets, backup/restore, offline behaviour, migration and deletion cost. Adoption requires a measured current defect and a simpler net operating model.
