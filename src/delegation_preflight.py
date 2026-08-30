"""Live delegation classification at the existing estate boundary.

This module identifies the appropriate execution lane, then asks
`estate_router` for live host, alias, and Codex evidence. It owns no host,
model, provider, or lease policy of its own.
"""
from __future__ import annotations

import re
from typing import Iterable

from src import estate_router


LEGITIMATE_NONDELEGATION_REASONS = {
    "architecture_judgement",
    "ambiguity_resolution",
    "cross_worker_synthesis",
    "arbitration",
    "final_acceptance",
}

_CODE_PATTERN = re.compile(
    r"\b(implement(?:ation|ing|ed|s)?|refactor(?:ing|ed)?|debug(?:ging|ged)?|code[ _-]?repair|"
    r"test[ _-]?author(?:ing)?|code[ _-]?review|repo(?:sitory)?[ _-]?reconnaissance|"
    r"bounded[ _-]?code|coding)\b"
)
_WRITE_CODE_PATTERN = re.compile(
    r"\b(implement(?:ation|ing|ed|s)?|refactor(?:ing|ed)?|debug(?:ging|ged)?|"
    r"code[ _-]?repair|test[ _-]?author(?:ing)?|bounded[ _-]?code|coding)\b"
)
_REMOTE_PATTERN = re.compile(
    r"\b(batch|scan(?:ning|ned)?|test(?:s|ing|[ _-]?execution)?|index(?:ing|ed)?|eval(?:uation)?|"
    r"simulation|data[ _-]?process(?:ing)?|extract(?:ion)?|classif(?:y|ication))\b"
)
_CONTROLLER_PATTERN = re.compile(
    r"\b(intent|architect(?:ure|ural)|methodolog(?:y|ical)|research[ _-]?synthesis|"
    r"ambiguity|arbitrat(?:e|ion)|cross[ _-]?worker[ _-]?synthesis|final[ _-]?acceptance)\b"
)


def _task_text(task: dict) -> str:
    objective = task.get("objective")
    if not isinstance(objective, str):
        objective = ""
    return f"{task.get('task_class') or ''} {objective}".lower().replace("-", " ").replace("_", " ")


def recommended_lane_for_task(task: dict) -> str:
    """Return the structural lane before live availability is applied."""
    text = _task_text(task)
    if _CODE_PATTERN.search(text):
        return "codex_eligible"
    if _REMOTE_PATTERN.search(text):
        return "remote_compute_eligible"
    if _CONTROLLER_PATTERN.search(text):
        return "controller_retained"
    return "controller_retained"


def _requires_repo_write(task: dict) -> bool:
    return bool(task.get("repo") and _WRITE_CODE_PATTERN.search(_task_text(task)))


def _valid_nondelegation_reason(reason: object) -> bool:
    if not isinstance(reason, str) or not reason.strip():
        return False
    value = reason.strip()
    if value in LEGITIMATE_NONDELEGATION_REASONS:
        return True
    return value.startswith("other:") and bool(value.removeprefix("other:").strip())


def _unit_task(unit: dict, capabilities: list[str]) -> dict:
    return {
        "task_class": unit.get("task_class") or "unclassified",
        "repo": unit.get("repo"),
        "objective": unit.get("objective"),
        "requirements": {"capabilities": capabilities},
        "placement": unit.get("placement") or {},
    }


def delegation_preflight(units: Iterable[dict]) -> dict:
    """Classify task units using live evidence from the canonical router.

    Retained units are valid only with a machine-readable reason. Valid
    retention is recorded immediately because no later worker dispatch
    exists to create its decision row; delegable recommendations are
    recorded by `run_task` when they are actually dispatched.
    """
    unit_list = [dict(unit) for unit in units]
    hosts = estate_router.eligible_hosts()
    codex_live, codex_detail = estate_router._codex_available()
    alias_resolutions: dict[str, dict] = {}
    recommendations = []

    for index, unit in enumerate(unit_list):
        structural_lane = recommended_lane_for_task(unit)
        reason = unit.get("nondelegation_reason")
        retention_requested = (
            unit.get("requested_route") == "controller_retained"
            or unit.get("retain_by_controller") is True
            or reason is not None
            or structural_lane == "controller_retained"
        )

        if retention_requested:
            valid_reason = _valid_nondelegation_reason(reason)
            result = {
                "index": index,
                "task_class": unit.get("task_class") or "unclassified",
                "classification": "controller_retained",
                "recommended_route": structural_lane,
                "actual_route": "controller" if valid_reason else None,
                "ok": valid_reason,
                "requires_justification": not valid_reason,
                "nondelegation_reason": reason if valid_reason else None,
                "reason": (
                    f"controller retention accepted: {reason}"
                    if valid_reason else
                    "controller retention requires a fixed reason code or non-empty 'other: ...' justification"
                ),
            }
            if valid_reason:
                record_task = {
                    **unit,
                    "recommended_route": structural_lane,
                    "actual_route": "controller",
                    "nondelegation_reason": reason.strip(),
                }
                result["decision_id"] = estate_router._record_decision(
                    record_task, host_id=estate_router.current_host_id(), executor="controller",
                    model_alias=None, concrete_model=None, status="complete",
                )
            recommendations.append(result)
            continue

        capabilities = list(unit.get("capabilities") or [])
        if structural_lane == "codex_eligible" and not capabilities:
            capabilities = ["code-strong"]
        task = _unit_task(unit, capabilities)
        route = estate_router.resolve_route(task, record_decision=False)
        for resolved in route.get("capability_resolutions") or []:
            alias_resolutions[resolved["alias"]] = resolved

        if structural_lane == "codex_eligible":
            alias = capabilities[0] if capabilities else None
            provider = estate_router._resolve_paid_provider(alias).get("provider")
            host_ready = bool((route.get("route") or {}).get("host"))
            write_authority = None
            write_ready = True
            write_required = _requires_repo_write(unit)
            if write_required:
                route_host = (route.get("route") or {}).get("host")
                backend_host = estate_router.current_host_id()
                lease = (
                    estate_router.active_lease_for_repo(unit["repo"], backend_host)
                    if backend_host and backend_host == route_host else None
                )
                write_ready = lease is not None
                write_authority = {
                    "ready": write_ready,
                    "host_id": backend_host,
                    "lease_id": lease.get("lease_id") if lease else None,
                    "reason": (
                        "active non-stale repo lease matches the execution host"
                        if write_ready else
                        "codex-write requires an active non-stale repo lease held by the execution host"
                    ),
                }
            ok = host_ready and codex_live and provider == "codex" and write_ready
            evidence = []
            if not host_ready:
                evidence.append(route.get("reason") or route.get("error") or "no eligible host")
            if not codex_live:
                evidence.append(f"codex unavailable: {codex_detail}")
            if provider != "codex":
                evidence.append(f"configured paid provider for {alias!r} is {provider!r}, not codex")
            if write_authority and not write_ready:
                evidence.append(write_authority["reason"])
            why = (
                f"substantial separable code work; Codex is live on {(route.get('route') or {}).get('host')}"
                if ok else "; ".join(evidence)
            )
            recommendations.append({
                "index": index,
                "task_class": task["task_class"],
                "classification": structural_lane,
                "recommended_route": "codex-write" if write_required else "codex",
                "ok": ok,
                "requires_justification": False,
                "nondelegation_reason": None,
                "route": route.get("route"),
                "hosts_checked": route.get("hosts_checked") or hosts,
                "capability_resolutions": route.get("capability_resolutions") or [],
                "write_authority": write_authority,
                "reason": why,
            })
            continue

        ok = bool(route.get("ok"))
        recommendations.append({
            "index": index,
            "task_class": task["task_class"],
            "classification": structural_lane,
            "recommended_route": route.get("route"),
            "ok": ok,
            "requires_justification": False,
            "nondelegation_reason": None,
            "route": route.get("route"),
            "hosts_checked": route.get("hosts_checked") or hosts,
            "capability_resolutions": route.get("capability_resolutions") or [],
            "reason": route.get("reason") or route.get("error"),
        })

    return {
        "ok": all(item["ok"] for item in recommendations),
        "snapshot": {
            "eligible_hosts": hosts,
            "codex": {"available": codex_live, "reason": "live" if codex_live else codex_detail},
            "alias_resolutions": list(alias_resolutions.values()),
        },
        "units": recommendations,
    }
