"""Held-out evaluation harness with first-class refusal expectations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from .errors import EvaluationError, QueryRefusedError, StaleGraphError
from .queries import execute_query


def _refusal_kind(exc: Exception) -> str:
    text = str(exc).lower()
    if isinstance(exc, StaleGraphError):
        return "stale"
    if "blocked" in text:
        return "blocked"
    return "unroutable"


def _assert_shape(value: Any, shape: Any, path: str = "answer") -> None:
    if isinstance(shape, list):
        if not isinstance(value, Mapping):
            raise EvaluationError(f"{path} must be an object")
        missing = [key for key in shape if key not in value]
        if missing:
            raise EvaluationError(f"{path} missing keys: {', '.join(missing)}")
        return
    if isinstance(shape, Mapping):
        if not isinstance(value, Mapping):
            raise EvaluationError(f"{path} must be an object")
        for key, child in shape.items():
            if key not in value:
                raise EvaluationError(f"{path} missing key {key!r}")
            _assert_shape(value[key], child, f"{path}.{key}")
        return
    if shape == "list" and not isinstance(value, list):
        raise EvaluationError(f"{path} must be a list")
    if shape == "string" and not isinstance(value, str):
        raise EvaluationError(f"{path} must be a string")


def load_cases(path: Path) -> list[Mapping[str, Any]]:
    try:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvaluationError(f"cannot load held-out cases {path}: {exc}") from exc
    if not isinstance(document, Mapping) or not isinstance(document.get("cases"), list):
        raise EvaluationError("held-out evaluation file requires a cases list")
    cases = document["cases"]
    if not cases:
        raise EvaluationError("held-out evaluation set is empty")
    for index, case in enumerate(cases):
        if not isinstance(case, Mapping) or not case.get("input_question"):
            raise EvaluationError(f"held-out case {index} requires input_question")
        if "expected_refusal" not in case and "expected_answer_shape" not in case:
            raise EvaluationError(
                f"held-out case {index} requires expected_refusal or expected_answer_shape"
            )
    return cases


def evaluate_cases(db_path: Path, case_path: Path) -> dict[str, Any]:
    cases = load_cases(case_path)
    results = []
    for index, case in enumerate(cases):
        case_id = str(case.get("id", index))
        expected_refusal = case.get("expected_refusal")
        try:
            answer = execute_query(
                db_path,
                str(case["input_question"]),
                route_id=str(case["route_id"]) if case.get("route_id") else None,
                request=str(case["request"]) if case.get("request") else None,
                allow_stale=bool(case.get("allow_stale", False)),
            )
        except (QueryRefusedError, StaleGraphError) as exc:
            actual_refusal = _refusal_kind(exc)
            if not expected_refusal:
                raise EvaluationError(
                    f"case {case_id}: unexpected {actual_refusal} refusal: {exc}"
                ) from exc
            if actual_refusal != expected_refusal:
                raise EvaluationError(
                    f"case {case_id}: expected {expected_refusal} refusal, got {actual_refusal}"
                ) from exc
            results.append({"id": case_id, "outcome": "refused", "reason": actual_refusal})
            continue
        if expected_refusal:
            raise EvaluationError(
                f"case {case_id}: expected {expected_refusal} refusal but graph answered"
            )
        expected_route = case.get("expected_route_id")
        if expected_route is not None and answer.get("route_id") != expected_route:
            raise EvaluationError(
                f"case {case_id}: expected route {expected_route!r}, got {answer.get('route_id')!r}"
            )
        _assert_shape(answer, case.get("expected_answer_shape"), f"case {case_id}")
        results.append({"id": case_id, "outcome": "answered", "route_id": answer["route_id"]})
    return {"passed": len(results), "failed": 0, "cases": results}

