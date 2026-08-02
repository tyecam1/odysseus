---
artifact_type: workflow
task_schema: agent-task/v1
task_id: 2026-06-18-asi-evolve-compute-box-evidence-ingest
title: Complete ASI-Evolve compute-box evidence ingest and research-engine adoption audit
status: done
priority: high
task_type: evidence-ingest-and-system-audit
created_by: chatgpt
created_at: 2026-06-18T14:00:00+01:00
executor: odysseus
execution_mode: handoff
requires_remote_compute: true
requires_local_model: true
requires_zotero: true
requires_mcp: true
requires_web: false
verification_route: V2_HUMAN_VERIFIED
risk_level: medium
approval_required: true
source_traceability_required: true
repo: tyecam1/obsidian-PhD
allowed_paths:
  - automation/review/agent-tasks/**/2026-06-18-asi-evolve-compute-box-evidence-ingest.agent-task.md
  - automation/review/02-library/02-evidence/asi-evolve/**
  - automation/review/queues/overnight-pdf-evidence/*asi-evolve*
  - automation/review/queues/overnight-pdf-evidence/*xuasievolveaiaccelerates2026*
  - automation/review/research-engine/2026-06-18-asi-evolve-adoption-audit.md
  - automation/review/research-engine/2026-06-18-asi-evolve-research-gathering-pipeline-patch-proposal.md
  - automation/review/research-engine/2026-06-18-asi-evolve-ingest-run-summary.md
denied_paths:
  - 01-research-plan/**
  - 02-library/00-papers/**
  - 02-library/01-annotations/**
  - 02-library/02-evidence/**
  - 02-library/04-pdfs/**
  - 03-concept/**
  - 07-standards/**
  - 00-dashboards/**
inputs:
  - 02-library/00-papers/xuasievolveaiaccelerates2026.md
  - 02-library/04-pdfs/Xu et al. - 2026 - ASI-Evolve AI Accelerates AI.pdf
  - 11-projects/tye/J1/j1Hub.md
  - automation/review/J1/agentic-gathering/2026-06-16-j1-agent-memory.md
  - automation/review/J1/agentic-gathering/2026-06-16-j1-paragraph-research-gathering-matrix.md
  - automation/docs/current-capabilities.md
  - automation/docs/capability_manifest.json
  - automation/config/settings.compute-box.example.ini
outputs:
  - automation/review/02-library/02-evidence/asi-evolve/xuasievolveaiaccelerates2026.evidence_bundle.json
  - automation/review/02-library/02-evidence/asi-evolve/xuasievolveaiaccelerates2026.atomic-evidence-review.md
  - automation/review/research-engine/2026-06-18-asi-evolve-adoption-audit.md
  - automation/review/research-engine/2026-06-18-asi-evolve-research-gathering-pipeline-patch-proposal.md
  - automation/review/research-engine/2026-06-18-asi-evolve-ingest-run-summary.md
operator_decision_path: ""
---
# Task: Complete ASI-Evolve compute-box evidence ingest and research-engine adoption audit

## Objective

ASI-Evolve is already present in the vault as a paper note and has been used as a J1 workflow pattern. That is not enough. Complete a bounded compute-box ingestion pass so the paper's claims become staged, atomic, source-traceable workflow evidence and so the research engine has an explicit adoption audit against the paper's findings.

This task must not treat ASI-Evolve as industrial HRC evidence. Its role is research-engine / agentic research workflow evidence.

## Current adoption baseline to verify

Check and cite the current vault state before running new work:

1. `02-library/00-papers/xuasievolveaiaccelerates2026.md` exists as a paper note with `artifact_type: paper`, `rq: J1`, and `claim: research-workflow-support`.
2. `11-projects/tye/J1/j1Hub.md` lists the paper as a research workflow resource, not HRC evidence.
3. `automation/review/J1/agentic-gathering/2026-06-16-j1-paragraph-research-gathering-matrix.md` explicitly uses the ASI-Evolve loop for paragraph-level research gathering and contains a P00 stop rule limiting it to workflow design.
4. `automation/review/J1/agentic-gathering/2026-06-16-j1-agent-memory.md` preserves the rule that ASI-Evolve is a workflow resource, not J1 evidence.
5. Search the repo for `xuasievolveaiaccelerates2026` and verify whether any staged or canonical atomic evidence bundle already exists. If it exists, audit it rather than duplicating it.

## Required compute-box pipeline actions

Run this as a bounded, single-paper, compute-box-backed pass. Use remote models only through the configured Odysseus / compute-box route. Do not pull model weights locally.

1. Run remote readiness checks:
   - `python -m Scripts.automation model-endpoint-diagnostics --require-remote`
   - `python -m Scripts.automation model-preflight --require-ready`
   - if semantic retrieval is configured, run the smallest appropriate retrieval smoke/eval command before relying on semantic ranking.
2. Confirm the PDF source through the existing paper note and/or governed Zotero catalog. Prefer the existing Zotero attachment key and vault PDF path. Do not mutate Zotero.
3. Run the narrowest existing single-paper evidence/review-pack/overnight-PDF worker route that can produce page-anchored staged evidence from this PDF. Do not run broad batch discovery.
4. Stage outputs only under the allowed paths above. If the existing command insists on a different review-safe path, stop and write the exact command/path conflict into the run summary instead of widening the write scope.

## Atomic evidence targets

Extract only workflow-relevant claims. Minimum expected atoms:

1. **Scientific Task Length framing**: `Ltask = <Cexec, Sspace, Dfeedback>` as a way to classify long-horizon research tasks by execution cost, search-space complexity, and feedback complexity.
2. **Closed loop pattern**: learn-design-experiment-analyze, with durable write-back of outputs into future context.
3. **Cognition base**: literature-derived priors improve cold-start and reduce blind search.
4. **Analyzer**: structured interpretation of multidimensional results is needed for sustained improvement, not just scalar scoring.
5. **Database / durable memory**: nodes store motivation, program, results, analysis, score and metadata for future sampling.
6. **Sampling strategy lesson**: parent/context selection changes exploration-exploitation behaviour; UCB1 may outperform diversity-preserving sampling when cognition priors are strong.
7. **Ablation lesson**: removing the analyzer produces plateaus; removing cognition slows cold-start but does not remove learning capacity.
8. **Boundary warning**: the paper supports research-engine design, not HRC domain evidence.

For each atom include source page, section, quote/window status, confidence/trust tier, and routing comment.

## Required adoption audit

Write `automation/review/research-engine/2026-06-18-asi-evolve-adoption-audit.md` with:

1. What the research engine already adopts.
2. What is only partially adopted.
3. What is not adopted and should not be adopted.
4. What would be overclaiming.
5. Minimal pragmatic changes to future J1/manuscript research-gathering practice.

The audit must be blunt: do not dress a paper note and one paragraph matrix as full adoption. Distinguish real behaviour from documented aspiration.

## Required research-gathering patch proposal

Write `automation/review/research-engine/2026-06-18-asi-evolve-research-gathering-pipeline-patch-proposal.md` containing a patch proposal, not direct canonical edits. It should specify whether future research-gathering tasks should require:

- explicit cognition packet inputs;
- bounded design/action plan;
- execution logs;
- analyzer section with `what changed`, `what remains unsupported`, `reuse in next task`, and `stop rule`;
- durable review-side memory handoff;
- scope guard preventing workflow-method papers from being routed as domain evidence.

## Hard constraints

- Do not create canonical evidence in `02-library/02-evidence/**`.
- Do not modify paper notes, annotations, PDFs, dashboards, ontology, or J1 canonical planning files.
- Do not mutate Zotero.
- Do not treat parsed/extracted PDF text alone as trusted evidence; route it as review-side support material unless audited annotation provenance exists.
- Do not collect more agentic-science papers. This task is about ingesting and auditing this paper, not expanding the literature set.
- Do not turn the research engine into ASI-Evolve cosplay. Adopt only the parts that reduce future overhead and improve traceability.

## Acceptance criteria

The task is complete only if:

1. The existing adoption state is verified with file/path evidence.
2. A staged ASI-Evolve evidence bundle or clear blocked-run summary exists.
3. The evidence atoms are page-anchored and source-traceable.
4. The adoption audit distinguishes implemented, partial, absent, and not-applicable findings.
5. The patch proposal is review-side only and uses minimal future-overhead changes.
6. No canonical or Zotero mutation occurred.

## Ready-to-run Codex prompt

Read and execute the agent task at:

`automation/review/agent-tasks/inbox/2026-06-18-asi-evolve-compute-box-evidence-ingest.agent-task.md`

Follow the task exactly. Use the compute-box/Odysseus route for model-backed work. Treat Zotero as read-only. Do not mutate canonical vault paths. Do not create canonical evidence notes. Stage only the allowed review-side outputs. If a required pipeline command is unavailable or its write path conflicts with the task contract, stop and write a blocked-run summary with the exact missing command or path conflict.
