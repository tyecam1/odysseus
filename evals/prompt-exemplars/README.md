# Prompt exemplars

This directory preserves prompts worth remembering **before** the system knows
whether they should become reusable components or registered initialisers.

## Principle

Capture unusually strong prompt designs opportunistically, regardless of task,
domain, repository or existing taxonomy.

The gallery is intentionally permissive at capture and strict at promotion:

- **candidate** — worth preserving on design insight or explicit operator signal;
- **validated** — later execution/evaluation supports the prompt's claimed value;
- **mixed** — useful mechanisms plus material observed weaknesses;
- **superseded** — a later exemplar preserves the value more effectively;
- **rejected** — later evidence shows the prompt should not be reused.

Capture is not authority. A candidate exemplar may be scientifically wrong,
task-specific or untested. Its purpose is to preserve the exact design so those
questions can be evaluated later.

## Capture trigger

Capture when the operator explicitly asks to preserve a prompt, or when an agent
has high confidence that at least two aspects are unusually strong or novel,
such as:

- framing/decomposition;
- autonomy/continuation behaviour;
- verification/adversarial structure;
- authority/constraint handling;
- model/tool coordination;
- context compression;
- retrieval strategy;
- stopping/escalation logic;
- another clearly reusable prompting mechanism.

Do not require a pre-existing category or component. Do not collect routine
prompts merely to increase the gallery.

## Record shape

Each exemplar is one immutable Markdown record with frontmatter plus the exact
prompt body. Record:

- `exemplar_id`
- `status`
- `captured_at`
- `capture_basis`
- source/task context
- concise capture rationale
- reusable behaviours
- limitations/task-specific assumptions
- later application/evaluation pointers

Never include hidden chain-of-thought, credentials, sensitive context or a full
conversation transcript.

## Distillation

Exemplars are raw design evidence. Reusable components may later be distilled
from several exemplars and execution traces, but componentisation is downstream
of capture, not a prerequisite for it.
