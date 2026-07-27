# Multi-deployment isolation

## Objective

Make domain isolation a startup and test invariant when one Odysseus harness serves separate Misumi and PhD deployments.

## Requirements

- unique, explicit data directory, source roots, auth, memory, vector index, uploads, jobs, skills, integrations and credentials per deployment;
- no permissive shared default when configuration is missing;
- source-root and writable-path allowlists;
- owner-scoped sessions and jobs;
- startup rejection for overlapping paths or identifiers;
- tests for symlinks, path traversal, shared indexes, cross-domain retrieval, task dispatch and credential reuse.

## Acceptance criteria

Deliberately overlapping configurations fail startup, separate fixtures cannot retrieve or enumerate one another, and diagnostics identify the exact collision without printing private data.
