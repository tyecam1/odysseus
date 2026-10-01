# Agent-task queue ownership

This queue contains **Odysseus backend and shared cross-repository agentic work**.

Ownership rule:
- shared routing, execution, worker, lease, lifecycle, model/provider, orchestration, task-engine, skill/runtime, memory/runtime, evaluation and observability capabilities belong here;
- PhD research/domain tasks remain in `tyecam1/obsidian-PhD`;
- personal/Aoteru/Misumi-specific capabilities remain with their owning personal-domain repository;
- domain repositories keep independent task queues even when Odysseus supplies the shared execution backend.

Historical tasks migrated from `obsidian-PhD` retain their original content and queue status unless the task had already been executed, in which case the migrated copy is archived under `done/`.

See `docs/aoteru-repository-ownership-trajectory.md` and `automation/review/agent-task-migration-20260923.md`.
