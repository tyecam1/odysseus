"""Read-only Leafly cultivar-research lookup + workbook export routes.

Backs task card ``2026-10-24-leafly-cultivar-reference-enrichment``: neutral,
source-grounded descriptive research over the operator's 76-row investigation
inventory. Strictly read-only — no writes, no retailer data, no prices.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter
from fastapi.responses import Response

from src.constants import DATA_DIR
from src.leafly_research import (
    DEFAULT_CSV_PATH,
    EXPECTED_ROW_COUNT,
    SOURCE_NAME,
    SCAFFOLD_NOTE,
    LeaflyResearchValidationError,
    build_workbook,
    load_inventory,
    retrieval_records,
)

logger = logging.getLogger(__name__)

_XLSX_MEDIA_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)


def setup_leafly_research_routes() -> APIRouter:
    router = APIRouter()

    @router.get("/api/research/leafly76")
    async def get_leafly76() -> dict:
        """The 76 inventory rows with their Leafly descriptions and provenance."""
        try:
            rows = load_inventory()
        except (OSError, LeaflyResearchValidationError) as exc:
            logger.warning("Leafly research inventory unavailable: %s", exc)
            return {
                "ok": False,
                "error": f"research inventory unavailable: {exc}",
                "expected_rows": EXPECTED_ROW_COUNT,
            }
        return {
            "ok": True,
            "source": str(DEFAULT_CSV_PATH.relative_to(
                DEFAULT_CSV_PATH.parents[3])),
            "row_count": len(rows),
            "provenance_source": SOURCE_NAME,
            "scaffold_note": SCAFFOLD_NOTE,
            "rows": retrieval_records(rows),
        }

    @router.get("/api/research/leafly76/export")
    async def export_leafly76() -> Response:
        """Colour-coded XLSX workbook (product name beside description).

        Advertised-option and price-comparison columns are blank scaffolding
        by design; see ``scaffold_note``.
        """
        rows = load_inventory()
        payload = build_workbook(rows)
        return Response(
            content=payload,
            media_type=_XLSX_MEDIA_TYPE,
            headers={
                "Content-Disposition":
                    'attachment; filename="leafly76-cultivar-research.xlsx"',
                "X-Scaffold-Note": SCAFFOLD_NOTE,
            },
        )

    return router
