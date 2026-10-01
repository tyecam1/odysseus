# Prompt-evolution graphs

Each substantive registered prompt application creates one evidence graph event:

```text
prompt_version -> application -> evolution_event -> child_version | reinforcement
```

Application traces are immutable raw evidence. Prompt bodies are immutable
version nodes. This directory records what was learned from each application and
why a descendant exists.

Do not create a child merely to paraphrase an already successful prompt.
Repeated clean applications reinforce the incumbent. Material/repeated failures
should create the smallest semantic child that directly addresses the observed
failure class.

No graph edge may widen authority or weaken evidence, verification, stop,
approval or safety gates.
