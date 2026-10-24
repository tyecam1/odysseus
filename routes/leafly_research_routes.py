"""Read-only Leafly cultivar-research lookup + workbook export routes.

Backs task card ``2026-10-24-leafly-cultivar-reference-enrichment``: neutral,
source-grounded descriptive research over the operator's 76-row investigation
inventory. Strictly read-only — no writes, no retailer data, no prices.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

from src.auth_helpers import _auth_disabled, get_current_user

from src.constants import DATA_DIR
from src.leafly_research import (
    DEFAULT_CSV_PATH,
    ingest_provenance,
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

    def _require_user(request: Request) -> str:
        """Same gate as the other research endpoints: research data requires
        an authenticated user; anonymous access only when auth is disabled."""
        user = get_current_user(request)
        if not user:
            if _auth_disabled():
                return ""
            raise HTTPException(401, "Not authenticated")
        return user


    @router.get("/api/research/leafly76")
    async def get_leafly76(request: Request) -> dict:
        """The 76 inventory rows with their Leafly descriptions and provenance."""
        _require_user(request)
        try:
            ingest_provenance(load_inventory())
        except Exception:  # provenance is best-effort; lookup must stay read-only-safe
            logger.exception("Leafly provenance ingest failed")
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
    async def export_leafly76(request: Request) -> Response:
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
