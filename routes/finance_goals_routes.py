"""Read-only finance goal-status routes (MT-xx / FT-xx).

Minimal /goals transport on the EXISTING interface per task card
``finance-paper-trading-goals-2026-10-29.md`` deliverable 1: "If no
/goals transport exists, provide a minimal read-only goal-status adapter
on the existing interface, not a new service." One GET endpoint that
derives current lock state from live registries + receipts via
``src.finance_goals``. No writes, no scheduling, no new service.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request

from src.auth_helpers import _auth_disabled, get_current_user
from src.finance_goals import (
    DEFAULT_RECEIPTS_DIR,
    DEFAULT_REGISTRIES_DIR,
    evaluate_goals,
    load_policy,
    load_receipts,
    load_registries,
)

logger = logging.getLogger(__name__)


def setup_finance_goals_routes() -> APIRouter:
    router = APIRouter()

    def _require_user(request: Request) -> str:
        """Same gate as the research endpoints: authenticated user, or
        anonymous only when auth is disabled."""
        user = get_current_user(request)
        if not user:
            if _auth_disabled():
                return ""
            raise HTTPException(401, "Not authenticated")
        return user

    @router.get("/api/finance/goals")
    async def get_finance_goals(request: Request) -> dict:
        """Current MT/FT goal lock state, derived at read time.

        Lock state is recomputed from the mirrored registries and the
        evidence receipts on every call — never stored, never assumed.
        Receipts and goal definitions are read-only inputs.
        """
        _require_user(request)
        try:
            result = evaluate_goals(
                registries=load_registries(DEFAULT_REGISTRIES_DIR),
                receipts=load_receipts(DEFAULT_RECEIPTS_DIR),
                policy=load_policy(),
            )
        except Exception as exc:  # deterministic payload, not a 500
            logger.exception("finance goal evaluation failed")
            return {
                "ok": False,
                "error": f"goal evaluation failed: {exc}",
                "registries_dir": str(DEFAULT_REGISTRIES_DIR),
                "receipts_dir": str(DEFAULT_RECEIPTS_DIR),
            }
        result["receipts_dir"] = str(DEFAULT_RECEIPTS_DIR)
        result["simulation_only"] = True
        result["live_trading_allowed"] = False
        return result

    @router.get("/api/finance/goals/{program_id}")
    async def get_finance_program_goals(request: Request, program_id: str) -> dict:
        """Goal lock state filtered to one programme (program_id or its
        registry file stem, e.g. ``finance-paper-trading-goals``)."""
        _require_user(request)
        result = await get_finance_goals(request)
        if not result.get("ok"):
            return result
        programs = [
            p for p in result.get("programs", [])
            if p.get("program_id") == program_id
            or (p.get("file") or "").startswith(program_id)
        ]
        if not programs:
            raise HTTPException(404, f"no finance goal programme {program_id!r}")
        program_ids = {p.get("program_id") for p in programs}
        result["goals"] = [
            g for g in result["goals"] if g.get("program_id") in program_ids
        ]
        result["programs"] = programs
        return result

    return router
