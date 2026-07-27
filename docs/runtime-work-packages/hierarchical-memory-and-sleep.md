# Hierarchical memory and offline consolidation

## Objective

Replace flat heuristic memory use with explicit session, episodic and durable runtime-memory classes plus an offline consolidation cycle.

## Requirements

- owner and deployment isolation;
- source, confidence, status, expiry, supersession and usage metadata;
- lexical, vector and hybrid retrieval evaluation;
- conflict detection before promotion;
- offline deduplication, compression, invalidation and candidate abstraction;
- optional bounded recombination of consolidated memories as hypotheses;
- user-visible save, replace, skip and forget outcomes;
- no automatic promotion into canonical external repositories.

## Acceptance criteria

The new design improves a fixed memory benchmark over the current keyword/Jaccard baseline, does not leak between deployments, preserves raw provenance pointers and supports deletion and rebuild.
