# Instagram Saved semantic tier: pilot evidence (2026-10-20)

Scope: a bounded Stage-7 second opinion (`src/instagram_semantic.py`) for saved posts the deterministic rules left neutral.
Qualifies the capability alias `local-classify` (qwen3.5:9b, host hz2-workstation) for this one task only.

Method. Labels: 242 tuning, 123 + 115 holdout items, blind to classifier output, one rater (Claude). The prompt was tuned on the
tuning set only, then frozen with this acceptance rule before any holdout run: on the holdouts (H1) residual PhD/Misumi share among
deterministic-neutral items <= 10%; (H2) hybrid precision >= 0.60 and within 10 points of baseline; (H3) model-added items >= 40%
correct; (H4) usefulness-weighted recall >= 0.90 and not below baseline; (H5) < 2 s/item, zero egress.

Results on the 238 holdout items through the real production path (`resolve_alias` -> `execute_local`, `think=False`):

| | deterministic v2 | hybrid (v2 + model tier) |
|---|---|---|
| precision | 0.86 | 0.77 |
| recall | 0.73 | 0.91 |
| usefulness-weighted recall | 0.79 | 0.97 |
| residual PhD/Misumi share among neutral (n=139) | 23% | 8% (CI 4-14%) |
| model-added items correct | - | 21/38 (14 useful) |
| cost | - | 0.31 s/item, 0 failures, local only |

All of H1-H5 hold for the hybrid. Caveats: single rater (no independent validation yet); the holdouts contain only 5 genuine PhD
leads, so PhD model routing is unvalidated (dev: 4 of 10 model-added PhD predictions correct), which is why model-routed items carry
confidence `model` and the digest reports them as a separate tier; with PhD routing off the residual share is 11.5%. qwen3:8b
(`local-fast`) failed H1 and H3 (residual 15%, added correct 11/31) and qwen3.5:9b with the shared default (thinking on) was 8-17 s/item,
hence the additive `think` switch in `llm_core`/`execute_local`. gemma4:12b also passed (residual 8%) but is slower; qwen3.5:9b chosen on cost.

Operation. Off by default (`ODYSSEUS_INSTAGRAM_SEMANTIC=1`); inference only for neutral items that are new or changed (the answer is
stored in the handoff record, never re-asked); at most `ODYSSEUS_INSTAGRAM_SEMANTIC_BATCH` (400) calls per run; refused unless the
endpoint is local; the alias is withheld while an experiment holds the GPU; failures are retried next run, never guessed; no caption text is
stored or logged; nothing is promoted to a canonical repository.
