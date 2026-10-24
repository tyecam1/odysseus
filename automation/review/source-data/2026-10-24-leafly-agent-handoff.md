---
artifact_type: research-handoff
date: 2026-10-24
source_data: automation/review/source-data/2026-10-24-leafly-76-research.csv
related_task: automation/review/agent-tasks/inbox/2026-10-24-leafly-cultivar-reference-enrichment.agent-task.md
---

# Leafly research: user preferences

**Data:** `automation/review/source-data/2026-10-24-leafly-76-research.csv` (this branch). The CSV contains 76 research records. It is not proof of retailer contents or a deployed capability.

1. **Completeness:** Retain all 76 original product names, seven categories and one row per item.
2. **Layout:** Place **Product name immediately before Leafly description** in the spreadsheet and research display.
3. **Descriptions:** Use a sourced Leafly cultivar profile for a reliable match. Otherwise use the closest defensible **explicitly labelled analogy** or a neutral category explanation. Never invent genetics or imply an analogy verifies a product.
4. **Evidence:** Keep source URL(s), closest reference, match classification and uncertainty. Verify source claims independently before presenting them as established facts.
5. **Scope:** This is non-transactional research. Do not add live store prices, quantities, availability, purchase links or seller credentials.

**Remote read (no checkout changes):**

```bash
git fetch origin research/leafly-76-handoff-20261024
git show origin/research/leafly-76-handoff-20261024:automation/review/source-data/2026-10-24-leafly-76-research.csv
```

**Acceptance:** 76 distinct names; all descriptions present; names adjacent to descriptions; evidence distinctions retained; no fabricated matches. Continue through the existing Odysseus task and `AGENTS.md` for implementation, tests and deployment.

**Status:** Research handoff only. No merge or lab deployment is implied. Glasgow gig preferences belong to the separate Misumi events task, not here.
