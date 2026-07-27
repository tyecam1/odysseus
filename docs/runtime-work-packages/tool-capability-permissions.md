# Tool capability and permission manifests

## Objective

Replace broad tool exposure with task-scoped capability manifests, explicit consent and expiring permissions.

## Manifest fields

Tool, action, resource scope, data classification, read/write effect, dry-run support, approval level, expiry, audit event, rollback and denied combinations.

## Requirements

- separate read, propose, execute and external-mutation authority;
- default-deny profiles by deployment and task type;
- field/path/domain allowlists where possible;
- one-time grants for high-risk actions;
- preview and diff before reversible writes;
- clear denial and degraded-state reporting;
- prompt content cannot grant permission.

## Acceptance criteria

Tests cover malicious documents, skills and memories, stale grants, cross-owner requests, symlink/path escape, chained tool escalation and rollback. No existing permission is widened by this specification alone.
