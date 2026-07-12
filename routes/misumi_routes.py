"""Misumi compatibility, policy, household, task, and status API."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple, Union

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from core.middleware import require_admin
from src.misumi_household import HouseholdReadOnlyAdapter, infer_household_domain
from src.misumi_memory import MisumiMemory
from src.misumi_observability import MisumiEventLog
from src.misumi_policy import load_persona_policy, normalize_persona, persona_record, policy_summary
from src.misumi_skills import installed_skill_files, security_review_files, skills_for_persona
from src.misumi_task_router import MisumiTaskRouter


logger = logging.getLogger(__name__)

_HONESTY_CONSTRAINTS = (
    "Answer concisely and never claim an action unless a structured tool result proves it. "
    "Phase A household access is read-only."
)
_RATIFICATION_CONSTRAINT = "Household changes go through proposals that the user ratifies."
_SENSITIVE_TEXT = re.compile(
    r"\b(password|passphrase|api[ _-]?key|access[ _-]?token|secret|private[ _-]?key|seed phrase)\b|"
    r"\b(?:sk[-_]|ody_)[A-Za-z0-9_-]{12,}\b|-----BEGIN [A-Z ]+PRIVATE KEY-----",
    re.IGNORECASE,
)
_DURABLE_MEMORY = re.compile(
    r"\b(remember|memor(?:ise|ize)|we decided|decided to|i prefer|i like|i dislike|"
    r"my favou?rite|always use|never use|still need to|next step|blocked by|my name is)\b",
    re.IGNORECASE,
)
_IMPLICIT_STABLE_FACT = re.compile(
    r"\bmy\s+[A-Za-z0-9 _'-]{1,48}\s+(?:is|are|was|were|has|have)\b|"
    r"\bi\s+(?:am|have|own|live|work|study)\b",
    re.IGNORECASE,
)
_ARTIFACT_REQUEST = re.compile(
    r"\b(create|make|write|save|draft|document|turn)\b.{0,48}"
    r"\b(file|document|note|plan|checklist|spec(?:ification)?|recipe|list|brief|report)\b|"
    r"\b(file|document|note|plan|checklist|spec(?:ification)?|recipe|list|brief|report)\b.{0,32}"
    r"\b(create|make|write|save|draft|document)\b",
    re.IGNORECASE,
)


class MisumiRespondRequest(BaseModel):
    prompt: str = ""
    intent: str = "reply"
    state: str = "idle"
    mood: str = "focused"
    context: Union[Dict[str, object], str] = Field(default_factory=dict)
    persona: str = "aoteru"
    session_id: Optional[str] = Field(default=None, max_length=120)
    retention_mode: Literal["auto", "off"] = "auto"
    persist_turn: bool = True


class MisumiTaskRequest(BaseModel):
    prompt: str
    persona: str = "aoteru"
    mode: str = "task"
    approval: str = "none"
    selected_task: Optional[str] = None


class MisumiSkillImportRequest(BaseModel):
    url: str
    persona: str = "aoteru"
    category: Optional[str] = None


class MisumiMemoryCaptureRequest(BaseModel):
    text: str
    source: str = "chat"
    type: Optional[str] = None
    persona: Optional[str] = None
    entities: List[str] = Field(default_factory=list)
    next_action: Optional[str] = None
    meta: Dict[str, object] = Field(default_factory=dict)


class MisumiMemoryRouteRequest(BaseModel):
    persona_primary: str
    persona_secondary: Optional[str] = None


class MisumiMemoryCloseRequest(BaseModel):
    resolution: Optional[str] = None


class MisumiHandoffRequest(BaseModel):
    from_persona: str
    to_persona: str
    action: str
    capsule_id: Optional[str] = None
    note: Optional[str] = None


def _owner(request: Request) -> Optional[str]:
    if getattr(request.state, "api_token", False):
        return getattr(request.state, "api_token_owner", None)
    return getattr(request.state, "current_user", None)


def _require_api_scope(request: Request, required: str) -> None:
    if not getattr(request.state, "api_token", False):
        return
    scopes = set(getattr(request.state, "api_token_scopes", []) or [])
    accepted = {"*", "admin", "misumi", required}
    if required == "misumi:read":
        accepted.add("chat")
    if not scopes.intersection(accepted):
        raise HTTPException(403, f"API token requires {required} scope")


def _short_text(value: object, limit: int = 420) -> str:
    text = re.sub(r"<think>.*?</think>", "", str(value or ""), flags=re.I | re.S)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit].rstrip()


def _consultation_enabled() -> bool:
    value = (os.getenv("MISUMI_CONSULT", "1") or "").strip().lower()
    return value not in {"", "0", "false", "no", "off"}


def _term_positions(text: str, terms: List[str]) -> List[int]:
    positions = []
    for term in terms:
        match = re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text, flags=re.I)
        if match:
            positions.append(match.start())
    return positions


def _intent_score(prompt: str, intents: List[str]) -> int:
    normalized_prompt = re.sub(r"[-_]", " ", prompt.lower())
    score = 0
    for intent in intents:
        normalized_intent = re.sub(r"[-_]", " ", intent.lower()).strip()
        terms = [normalized_intent]
        if " " in normalized_intent:
            terms.extend(part for part in normalized_intent.split() if len(part) >= 3)
        if any(re.search(rf"(?<!\w){re.escape(term)}(?!\w)", normalized_prompt) for term in terms):
            score += 1
    return score


def _consultation_plan(prompt: str, primary_reply: str, persona: str) -> List[str]:
    """Choose at most two synchronous consultation targets deterministically."""
    if persona != "aoteru" or not _consultation_enabled():
        return []

    from src.persona_capabilities import consult_edges, routing_intents

    policy_order = list(load_persona_policy())
    allowed = set(policy_order) - {"aoteru"}
    edges = [item.lower() for item in (consult_edges("aoteru") or [])]
    edges = [item for item in edges if item in allowed]
    intent_scores = {
        item: _intent_score(prompt, routing_intents(item) or [])
        for item in policy_order
        if item in allowed
    }
    mention_text = f"{prompt}\n{primary_reply}"
    mentioned = []
    for item in policy_order:
        if item not in allowed:
            continue
        record = persona_record(item)
        terms = list(dict.fromkeys((item, str(record.get("display_name") or item))))
        if _term_positions(mention_text, terms):
            mentioned.append(item)
    # Consultation is work, not ambient theatre. Only invoke a specialist when
    # the user names one or the request matches that persona's routing intents.
    complex_request = bool(re.search(
        r"\b(plan|planning|decide|decision|compare|review|risk|coordinate|approach|strategy|trade-?off)\b",
        prompt,
        re.IGNORECASE,
    ))
    intent_candidates = (
        [item for item in policy_order if intent_scores.get(item, 0)]
        if complex_request else []
    )
    candidates = list(dict.fromkeys(mentioned + intent_candidates))

    def rank(item: str) -> tuple[int, int, int, int]:
        record = persona_record(item)
        terms = list(dict.fromkeys((item, str(record.get("display_name") or item))))
        mentions = _term_positions(mention_text, terms)
        if mentions:
            return (0, min(mentions), 0, policy_order.index(item))
        score = intent_scores.get(item, 0)
        if score:
            return (1, 0, -score, policy_order.index(item))
        edge_index = edges.index(item) if item in edges else len(edges)
        return (2, edge_index, 0, policy_order.index(item))

    return sorted(candidates, key=rank)[:2]


async def _consult_persona(
    prompt: str,
    persona: str,
    backend: str,
    model: str,
) -> str:
    from src.llm_core import llm_call_async
    from src.persona_capabilities import capability_summary
    from src.seed_order_context import build_seed_order_context

    record = persona_record(persona)
    system = (
        f"You are {persona}, the Misumi {record.get('role')}. Analyze the user's request from your "
        f"specialist role and give Aoteru concise, practical evidence, critique, or next steps. "
        f"Do not address the user directly. {_HONESTY_CONSTRAINTS}"
    )
    capabilities = capability_summary(persona)
    if capabilities:
        system += f"\n\n{capabilities}"
    system += f"\n{_RATIFICATION_CONSTRAINT}"
    seed = build_seed_order_context()
    messages = []
    if seed:
        messages.append({"role": "system", "content": seed})
    messages.extend((
        {"role": "system", "content": system},
        {
            "role": "user",
            "content": f"User request for internal consultation:\n{prompt[:4000]}",
        },
    ))
    text = await llm_call_async(
        backend,
        model,
        messages,
        max_tokens=180,
        timeout=8,
        max_retries=1,
        allow_reasoning_fallback=False,
    )
    contribution = _short_text(text, 1200)
    if not contribution:
        raise RuntimeError("consulted model returned empty content")
    return contribution


def _resolve_model_endpoint() -> Tuple[str, str]:
    fallback_url = (os.getenv("MISUMI_MODEL_URL") or os.getenv("MISUMI_OLLAMA_URL") or "").strip()
    fallback_model = (os.getenv("MISUMI_MODEL") or "").strip()
    from src.endpoint_resolver import build_chat_url, normalize_base, resolve_endpoint

    if fallback_url and fallback_model:
        # A dedicated deployment may pin Misumi to a known-local model even
        # when the broader Odysseus UI has a different (or stale) default.
        # Treat the complete environment pair as an operational override.
        url, model = fallback_url, fallback_model
    else:
        url, model, _headers = resolve_endpoint(
            "default",
            fallback_url=fallback_url or None,
            fallback_model=fallback_model or None,
            owner=None,
        )
    if not url or not model:
        raise RuntimeError("no model endpoint configured")
    # Environment fallbacks are allowed to be either API roots or complete
    # chat endpoints. resolve_endpoint() normalizes database-backed endpoints,
    # but intentionally returns raw fallback URLs, so normalize that final
    # boundary here before dispatching to llm_core.
    chat_url = build_chat_url(normalize_base(str(url)))
    return chat_url, str(model)


def _json_object(text: str) -> Optional[Dict[str, Any]]:
    clean = re.sub(r"<think>.*?</think>", "", str(text or ""), flags=re.I | re.S).strip()
    clean = re.sub(r"^```(?:json)?\s*|\s*```$", "", clean, flags=re.I | re.S).strip()
    try:
        value = json.loads(clean)
    except (json.JSONDecodeError, TypeError):
        start, end = clean.find("{"), clean.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            value = json.loads(clean[start:end + 1])
        except (json.JSONDecodeError, TypeError):
            return None
    return value if isinstance(value, dict) else None


def _fallback_retention(prompt: str, answer: str) -> Dict[str, Optional[Dict[str, str]]]:
    memory_plan = None
    if _DURABLE_MEMORY.search(prompt) and not _SENSITIVE_TEXT.search(prompt):
        memory_plan = {
            "text": _short_text(prompt, 600),
            "category": "preference" if re.search(r"\b(prefer|like|favou?rite)\b", prompt, re.I) else "fact",
            "reason": "durable cue in the user's wording",
        }
    # A degraded or non-JSON answer is insufficient evidence for a useful file.
    # Fail closed instead of turning an error or unrelated search snippet into a draft.
    return {"memory": memory_plan, "artifact": None}


def _parse_model_turn(raw: str, prompt: str) -> Dict[str, Any]:
    parsed = _json_object(raw)
    if not parsed or not isinstance(parsed.get("answer"), str):
        answer = _short_text(raw, 4000)
        return {"answer": answer, **_fallback_retention(prompt, answer), "retention_decided": True}
    answer = _short_text(parsed.get("answer"), 4000)
    memory_plan = parsed.get("memory") if isinstance(parsed.get("memory"), dict) else None
    artifact_plan = parsed.get("artifact") if isinstance(parsed.get("artifact"), dict) else None
    return {
        "answer": answer,
        "memory": memory_plan,
        "artifact": artifact_plan,
        "retention_decided": True,
    }


async def _model_turn(
    prompt: str,
    persona: str,
    *,
    backend: str,
    model: str,
    context_messages: Optional[List[Dict[str, str]]] = None,
    contributions: Optional[List[Tuple[str, str]]] = None,
) -> Dict[str, Any]:
    """Generate one synthesized answer plus bounded retention decisions."""
    try:
        from src.llm_core import llm_call_async
        from src.persona_capabilities import capability_summary
        from src.seed_order_context import build_seed_order_context

        record = persona_record(persona)
        system = (
            f"You are {persona}, the Misumi {record.get('role')}. {_HONESTY_CONSTRAINTS}\n"
            "Return ONLY one JSON object with keys answer, memory, artifact. answer is the complete user-facing "
            "response. memory is null or {text, category, reason, confidence}; retain only stable user facts, "
            "preferences, "
            "explicit decisions, or open loops likely to matter later. artifact is null or {title, content, reason}; "
            "create a reusable Markdown draft only when the user requests a file/document/note or clearly forms a "
            "substantive reusable plan. Never retain credentials, secrets, transient small talk, guesses, or raw "
            "specialist chatter. If specialist input is supplied, silently reconcile it into answer rather than "
            "appending disconnected persona comments."
        )
        capabilities = capability_summary(persona)
        if capabilities:
            system += f"\n\n{capabilities}"
        system += f"\n{_RATIFICATION_CONSTRAINT}"
        messages = list(context_messages or [])
        if not messages:
            seed = build_seed_order_context()
            if seed:
                messages.append({"role": "system", "content": seed})
        messages.append({"role": "system", "content": system})
        consultation_text = ""
        if contributions:
            lines = [
                f"- {persona_record(name).get('display_name')}: {text}"
                for name, text in contributions
            ]
            consultation_text = "\n\nInternal specialist input to reconcile:\n" + "\n".join(lines)
        messages.append({"role": "user", "content": prompt[:4000] + consultation_text})
        raw = await llm_call_async(
            backend,
            model,
            messages,
            max_tokens=500,
            timeout=30,
            max_retries=1,
            allow_reasoning_fallback=False,
        )
        turn = _parse_model_turn(str(raw or ""), prompt)
        if not turn.get("answer"):
            raise RuntimeError("model returned empty content (reasoning-only)")
        return turn
    except Exception as exc:
        logger.exception("Misumi model reply failed: %s", exc)
        return {
            "answer": "Odysseus is available, but the configured model did not complete this request.",
            "memory": None,
            "artifact": None,
            "error": type(exc).__name__,
        }


async def _model_reply(prompt: str, persona: str) -> tuple[str, Optional[str], Optional[str]]:
    """Compatibility helper for callers that still need an unstructured reply."""
    try:
        from src.llm_core import llm_call_async
        from src.persona_capabilities import capability_summary
        from src.seed_order_context import build_seed_order_context

        backend, model = _resolve_model_endpoint()
        record = persona_record(persona)
        system = f"You are {persona}, the Misumi {record.get('role')}. {_HONESTY_CONSTRAINTS}"
        capabilities = capability_summary(persona)
        if capabilities:
            system += f"\n\n{capabilities}"
        system += f"\n{_RATIFICATION_CONSTRAINT}"
        messages = []
        seed = build_seed_order_context()
        if seed:
            messages.append({"role": "system", "content": seed})
        messages.extend((
            {"role": "system", "content": system},
            {"role": "user", "content": prompt[:4000]},
        ))
        raw = await llm_call_async(
            backend,
            model,
            messages,
            max_tokens=480,
            timeout=25,
            allow_reasoning_fallback=False,
        )
        reply = _short_text(raw, 4000)
        if not reply:
            raise RuntimeError("model returned empty content (reasoning-only)")
        return reply, backend, model
    except Exception as exc:
        logger.exception("Misumi model reply failed: %s", exc)
        return "Odysseus is available, but no working model backend is configured for this request.", None, None


def _ensure_session(session_manager, requested_id: Optional[str], owner: Optional[str], backend: str, model: str):
    if session_manager is None:
        return None, None
    session_id = (requested_id or "").strip() or f"misumi-{uuid.uuid4()}"
    try:
        session = session_manager.get_session(session_id)
    except Exception:
        session = None
    if session is not None:
        if owner is not None and getattr(session, "owner", None) != owner:
            raise HTTPException(403, "Conversation belongs to another user")
        return session_id, session
    session = session_manager.create_session(
        session_id,
        "Misumi interface",
        backend,
        model,
        rag=True,
        owner=owner,
    )
    return session_id, session


def _conversation_context(chat_processor, session, prompt: str, owner: Optional[str]) -> List[Dict[str, str]]:
    if chat_processor is None or session is None:
        return []
    preface, _rag_sources, _web_sources = chat_processor.build_context_preface(
        prompt,
        session,
        use_web=False,
        use_rag=True,
        use_memory=True,
        owner=owner,
        agent_mode=False,
        incognito=False,
    )
    history = []
    for item in session.get_context_messages()[-12:]:
        if isinstance(item, dict) and isinstance(item.get("content"), str):
            history.append({"role": str(item.get("role") or "user"), "content": item["content"]})
    return [*preface, *history]


def _persist_conversation_turn(
    session_manager,
    session_id: Optional[str],
    prompt: str,
    answer: str,
    persona: str,
) -> None:
    if session_manager is None or not session_id:
        return
    from core.models import ChatMessage

    session_manager.add_message(session_id, ChatMessage(
        "user", prompt, {"source": "misumi-interface", "persona": persona},
    ))
    session_manager.add_message(session_id, ChatMessage(
        "assistant", answer, {"source": "misumi-interface", "persona": persona},
    ))


def _safe_plan_text(plan: Optional[Dict[str, Any]], key: str, limit: int) -> str:
    if not isinstance(plan, dict):
        return ""
    return _short_text(plan.get(key), limit)


def _existing_document(title: str, content: str, owner: Optional[str]) -> Optional[Dict[str, str]]:
    """Return an exact active draft match from Odysseus's existing library."""
    try:
        from src.database import Document, SessionLocal

        db = SessionLocal()
        try:
            query = db.query(Document).filter(
                Document.title == title,
                Document.current_content == content,
                Document.is_active == True,
            )
            query = (
                query.filter(Document.owner == owner)
                if owner is not None
                else query.filter(Document.owner.is_(None))
            )
            document = query.order_by(Document.updated_at.desc()).first()
            if document:
                return {"doc_id": str(document.id), "title": str(document.title)}
        finally:
            db.close()
    except Exception as exc:
        logger.warning("Misumi document deduplication check failed: %s", exc)
    return None


async def _apply_retention(
    *,
    prompt: str,
    turn: Dict[str, Any],
    retention_mode: str,
    owner: Optional[str],
    session_id: Optional[str],
    memory_manager,
    memory_vector,
    session_manager,
) -> Dict[str, Dict[str, Any]]:
    result: Dict[str, Dict[str, Any]] = {
        "memory": {"status": "none"},
        "artifact": {"status": "none"},
    }
    if retention_mode == "off" or re.search(r"\b(do not|don't|dont) (remember|save|store)\b", prompt, re.I):
        result["memory"] = {"status": "disabled"}
        result["artifact"] = {"status": "disabled"}
        return result

    memory_plan = turn.get("memory") if isinstance(turn.get("memory"), dict) else None
    memory_text = _safe_plan_text(memory_plan, "text", 700)
    category = _safe_plan_text(memory_plan, "category", 40).lower()
    if category not in {"fact", "identity", "preference", "decision", "open_loop"}:
        category = "fact"
    try:
        confidence = float((memory_plan or {}).get("confidence") or 0.0)
    except (TypeError, ValueError):
        confidence = 0.0
    model_stable = confidence >= 0.85 and (
        category in {"preference", "identity"}
        or (category == "fact" and bool(_IMPLICIT_STABLE_FACT.search(prompt)))
    )
    memory_gate = bool(_DURABLE_MEMORY.search(prompt)) or model_stable
    if memory_text and memory_gate:
        if _SENSITIVE_TEXT.search(prompt) or _SENSITIVE_TEXT.search(memory_text):
            result["memory"] = {"status": "blocked", "reason": "sensitive-content"}
        elif memory_manager is None:
            result["memory"] = {"status": "unavailable"}
        else:
            existing = memory_manager.load(owner=owner)
            if memory_manager.find_duplicates(memory_text, existing):
                result["memory"] = {"status": "duplicate"}
            else:
                entry = memory_manager.add_entry(
                    memory_text,
                    source="misumi-auto",
                    category=category,
                    owner=owner,
                )
                all_entries = memory_manager.load_all()
                all_entries.append(entry)
                memory_manager.save(all_entries)
                if memory_vector and getattr(memory_vector, "healthy", False):
                    memory_vector.add(entry["id"], memory_text)
                result["memory"] = {
                    "status": "saved",
                    "id": entry["id"],
                    "category": category,
                }

    artifact_plan = turn.get("artifact") if isinstance(turn.get("artifact"), dict) else None
    title = _safe_plan_text(artifact_plan, "title", 120)
    content = str((artifact_plan or {}).get("content") or "").strip()[:16000]
    artifact_gate = bool(_ARTIFACT_REQUEST.search(prompt)) or (
        bool(re.search(r"\bwe decided\b", prompt, re.I)) and len(prompt) >= 120
    )
    if title and content and artifact_gate:
        if _SENSITIVE_TEXT.search(prompt) or _SENSITIVE_TEXT.search(content):
            result["artifact"] = {"status": "blocked", "reason": "sensitive-content"}
        elif session_manager is None or not session_id:
            result["artifact"] = {"status": "unavailable"}
        else:
            from src.agent_tools.document_tools import CreateDocumentTool

            existing = _existing_document(title, content, owner)
            if existing:
                result["artifact"] = {"status": "duplicate", **existing}
                return result
            created = await CreateDocumentTool().execute(
                f"{title}\nmarkdown\n{content}",
                {"session_id": session_id, "owner": owner},
            )
            if created.get("doc_id"):
                result["artifact"] = {
                    "status": "created",
                    "doc_id": created["doc_id"],
                    "title": created.get("title") or title,
                }
            else:
                result["artifact"] = {
                    "status": "failed",
                    "reason": _short_text(created.get("error"), 160) or "document-tool-failed",
                }
    return result


def setup_misumi_routes(
    skills_manager,
    task_scheduler=None,
    memory_vector=None,
    memory_root=None,
    memory_manager=None,
    session_manager=None,
    chat_processor=None,
) -> APIRouter:
    router = APIRouter(prefix="/misumi", tags=["misumi"])
    adapter = HouseholdReadOnlyAdapter()
    task_router = MisumiTaskRouter(adapter)
    events = MisumiEventLog()
    memory = MisumiMemory(memory_root)

    def memory_call(operation, *args, **kwargs):
        try:
            return operation(*args, **kwargs)
        except KeyError as exc:
            raise HTTPException(404, "Memory record not found") from exc
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        except OSError as exc:
            raise HTTPException(503, "Misumi memory store is unavailable") from exc

    @router.get("/health")
    async def health():
        return {
            "status": "ok",
            "node": "odysseus-misumi",
            "source": "odysseus",
            "phase": "A",
            "auth_required_for_actions": True,
            "household_reachable": adapter.reachable,
        }

    @router.post("/respond")
    async def respond(request: Request, body: MisumiRespondRequest):
        _require_api_scope(request, "misumi:read")
        if body.retention_mode == "auto" and body.persist_turn:
            _require_api_scope(request, "misumi:execute")
        started = time.monotonic()
        request_id = events.request_id()
        persona = normalize_persona(body.persona)
        interface_context = body.context if isinstance(body.context, str) else ""
        prompt = (body.prompt or interface_context or body.intent or "status").strip()
        owner = _owner(request)
        domain = infer_household_domain(prompt)
        sources = adapter.search(prompt, domain=domain, limit=4) if adapter.reachable else []
        if not domain:
            # General chat belongs to the normal model/RAG path. Lexical matches
            # against task/docs files are too weak to replace a conversational answer.
            sources = []
        model_required = not domain or bool(_ARTIFACT_REQUEST.search(prompt))
        backend = model = None
        turn: Dict[str, Any] = {"memory": None, "artifact": None}
        consulted: List[Dict[str, str]] = []
        contributions: List[Tuple[str, str]] = []
        capsule_id = None
        handoff_ids: List[str] = []
        if sources and not model_required:
            lead = sources[0]
            text = _short_text(f"From {lead['path']} line {lead['line']}: {lead['snippet']}")
            backend = "household-read-only"
        elif domain and not model_required:
            present = any(item["id"] == domain and item["present"] for item in adapter.domains())
            if present:
                text = f"No matching {domain} fact was found in the canonical household repository."
            else:
                text = f"The canonical household repository has no {domain} data surface yet."
            backend = "household-read-only"
        else:
            try:
                backend, model = _resolve_model_endpoint()
            except Exception as exc:
                logger.warning("Misumi model endpoint unavailable: %s", exc)
                text = "Odysseus is available, but no working model backend is configured for this request."
            else:
                targets = _consultation_plan(prompt, "", persona)

                async def consult(target: str):
                    try:
                        return target, await _consult_persona(prompt, target, backend, model)
                    except Exception as exc:
                        logger.warning(
                            "Misumi consultation failed for %s: %s", target, exc,
                            exc_info=True,
                        )
                        return target, None

                rows = await asyncio.gather(*(consult(target) for target in targets))
                contributions = [
                    (target, contribution)
                    for target, contribution in rows
                    if contribution
                ]
                consulted = [
                    {"persona": target, "contribution": contribution}
                    for target, contribution in contributions
                ]

        should_persist = body.persist_turn and body.retention_mode == "auto"
        if should_persist:
            session_id, session = _ensure_session(
                session_manager,
                body.session_id,
                owner,
                backend or "unavailable",
                model or "none",
            )
        else:
            session_id, session = body.session_id, None
        if model_required and backend and model:
            context_messages = _conversation_context(chat_processor, session, prompt, owner)
            if sources:
                from src.prompt_security import untrusted_context_message

                source_text = "\n".join(
                    f"- {item['path']} line {item['line']}: {item['snippet']}"
                    for item in sources
                )
                context_messages.append(untrusted_context_message(
                    "read-only household repository search",
                    source_text,
                ))
            turn = await _model_turn(
                prompt,
                persona,
                backend=backend,
                model=model,
                context_messages=context_messages,
                contributions=contributions,
            )
            text = str(turn["answer"])

        outcome = (
            "grounded" if sources and not model_required else
            "absent" if domain and not model_required else
            "degraded" if not backend or not model or turn.get("error") else
            "model"
        )

        if contributions and should_persist:
            capsule_type = (
                "decision"
                if re.search(r"\b(plan|planning|decide|deciding|decision)\b", prompt, re.I)
                else "observation"
            )
            try:
                capsule = memory.capture(
                    prompt,
                    source="consultation",
                    capsule_type=capsule_type,
                    persona="aoteru",
                    meta={
                        "contributions": [
                            {"persona": target, "text": contribution}
                            for target, contribution in contributions
                        ],
                        "synthesized_answer": _short_text(text, 1200),
                    },
                )
                capsule_id = str(capsule["id"])
            except Exception as exc:
                logger.warning("Misumi consultation capsule failed: %s", exc, exc_info=True)

            for target, _contribution in (contributions if capsule_id else []):
                try:
                    handoff = memory.create_handoff(
                        "aoteru",
                        target,
                        f"analyze the request from the {persona_record(target).get('role')} perspective",
                        capsule_id,
                    )
                    memory.resolve_handoff(str(handoff["id"]))
                    handoff_ids.append(str(handoff["id"]))
                except Exception as exc:
                    logger.warning(
                        "Misumi consultation handoff failed for %s: %s", target, exc,
                        exc_info=True,
                    )

        if not turn.get("retention_decided"):
            turn.update(_fallback_retention(prompt, text))
        retention = await _apply_retention(
            prompt=prompt,
            turn=turn,
            retention_mode=body.retention_mode if body.persist_turn else "off",
            owner=owner,
            session_id=session_id,
            memory_manager=memory_manager,
            memory_vector=memory_vector,
            session_manager=session_manager,
        )
        if should_persist:
            _persist_conversation_turn(session_manager, session_id, prompt, text, persona)

        files_changed = []
        if retention["artifact"].get("status") == "created":
            files_changed.append(f"document:{retention['artifact']['doc_id']}")
        events.emit({
            "request_id": request_id,
            "persona": persona,
            "files_read": sorted({item["path"] for item in sources}),
            "files_changed": files_changed,
            "model": model,
            "backend": backend,
            "latency_ms": int((time.monotonic() - started) * 1000),
            "outcome": outcome,
            "approval_mode": "none",
        })
        response = {
            "text": text,
            "state": "speaking",
            "mood": body.mood or "focused",
            "source": (
                "model" if outcome == "model" else
                "household-read-only" if outcome in {"grounded", "absent"} else
                "degraded"
            ),
            "node": "odysseus",
            "persona": persona,
            "who": persona_record(persona).get("display_name"),
            "audio_url": None,
            "voice": None,
            "tts_provider": None,
            "request_id": request_id,
            "sources": sources,
            "session_id": session_id,
            "retention": retention,
        }
        if _consultation_enabled():
            response.update({
                "consulted": consulted,
                "capsule_id": capsule_id,
                "handoff_ids": handoff_ids,
            })
        return response

    @router.post("/task")
    async def task(request: Request, body: MisumiTaskRequest):
        _require_api_scope(request, "misumi:execute")
        started = time.monotonic()
        request_id = events.request_id()
        result = task_router.route(
            body.prompt,
            persona=body.persona,
            approval=body.approval,
            selected_task=body.selected_task,
        )
        result["request_id"] = request_id
        events.emit({
            "request_id": request_id,
            "persona": result.get("persona"),
            "task_id": result.get("selected_task"),
            "files_read": result.get("files_read"),
            "files_changed": [],
            "blocked_tools": (result.get("policy") or {}).get("tools_blocked"),
            "latency_ms": int((time.monotonic() - started) * 1000),
            "outcome": result.get("status"),
            "blocker": "; ".join(result.get("blockers") or []),
            "approval_mode": body.approval,
        })
        return result

    @router.get("/personas")
    async def personas(request: Request):
        _require_api_scope(request, "misumi:read")
        return {
            "personas": [
                {"id": name, **record}
                for name, record in sorted(load_persona_policy().items())
            ],
            "head_persona": "aoteru",
            "security_principal": "odysseus",
        }

    @router.get("/personas/{persona}/skills")
    async def persona_skills(request: Request, persona: str):
        _require_api_scope(request, "misumi:read")
        name = normalize_persona(persona)
        installed = skills_manager.load(owner=_owner(request))
        visible = skills_for_persona(name, installed)
        return {
            "persona": name,
            "categories": persona_record(name).get("allowed_skill_categories"),
            "skills": visible,
            "count": len(visible),
        }

    @router.post("/skills/import-draft")
    async def import_draft(request: Request, body: MisumiSkillImportRequest):
        require_admin(request)
        from services.memory.skill_importer import SkillImportError, fetch_skill_bundle

        persona = normalize_persona(body.persona)
        categories = list(persona_record(persona).get("allowed_skill_categories") or [])
        category = body.category if body.category in categories else categories[0]
        try:
            files, _source = fetch_skill_bundle(body.url.strip())
            review = security_review_files(files)
            entry = skills_manager.import_bundle_from_files(
                files,
                owner=_owner(request),
                source_url=body.url.strip(),
                category=str(category),
            )
        except SkillImportError as exc:
            raise HTTPException(400, str(exc)) from exc
        return {
            "status": "draft",
            "persona": persona,
            "skill": entry,
            "security_review": review,
            "scripts_executed": False,
        }

    @router.get("/skills/security-review/{skill_name}")
    async def security_review(request: Request, skill_name: str):
        require_admin(request)
        installed = skills_manager.load(owner=_owner(request))
        skill = next((item for item in installed if item.get("name") == skill_name), None)
        if not skill:
            raise HTTPException(404, "Skill not found")
        return {"skill": skill_name, **security_review_files(installed_skill_files(skill))}

    @router.post("/personas/{persona}/skills/audit")
    async def audit_persona_skills(request: Request, persona: str):
        require_admin(request)
        name = normalize_persona(persona)
        visible = skills_for_persona(name, skills_manager.load(owner=_owner(request)))
        results = []
        for skill in visible:
            files = installed_skill_files(skill) if not skill.get("first_party") else {"SKILL.md": Path(str(skill["path"])).read_text(encoding="utf-8")}
            results.append({"name": skill.get("name"), **security_review_files(files)})
        return {"persona": name, "results": results, "count": len(results), "publication_changed": False}

    @router.get("/status")
    async def status(request: Request):
        _require_api_scope(request, "misumi:read")
        from src.readiness import check_readiness

        readiness = check_readiness(
            skills_manager=skills_manager,
            task_scheduler=task_scheduler,
            memory_vector=memory_vector,
        )
        candidates = task_router.discover()
        installed = skills_manager.load(owner=_owner(request))
        memory_state = memory_call(memory.glance)
        return {
            "status": "ready" if readiness.get("ready") else "degraded",
            "source": "odysseus-misumi-status",
            "phase": "A",
            "readiness": readiness,
            "household": adapter.status(),
            "tasks": {
                "count": len(candidates),
                "queues": {queue: sum(1 for item in candidates if item.get("queue") == queue) for queue in {item.get("queue") for item in candidates}},
            },
            "skills": {
                "installed": len(installed),
                "by_persona": {name: len(skills_for_persona(name, installed)) for name in load_persona_policy()},
            },
            "events": {"recent_count": len(events.recent(100))},
            "memory": {
                "capsules": len(memory_call(memory.capsules)[0]),
                "inbox": memory_state["inbox_count"],
                "open_loops": memory_state["open_loop_count"],
                "stale_loops": memory_state["stale_loop_count"],
                "pending_handoffs": memory_state["pending_handoff_count"],
                "newest_capture": memory_state["newest_capture"],
                "top_open_loop": memory_state["top_open_loop"],
                "next_recommended_action": memory_state["next_recommended_action"],
                "responsible_persona": memory_state["responsible_persona"],
                "writes_allowed": False,
            },
            "writes_allowed": False,
        }

    @router.post("/memory/capture")
    async def capture_memory(request: Request, body: MisumiMemoryCaptureRequest):
        _require_api_scope(request, "misumi:execute")
        return memory_call(
            memory.capture, body.text, source=body.source, capsule_type=body.type,
            persona=body.persona, entities=body.entities, next_action=body.next_action,
            meta=body.meta,
        )

    @router.get("/memory/inbox")
    async def memory_inbox(request: Request, limit: int = 20):
        _require_api_scope(request, "misumi:read")
        capsules, corrupt = memory_call(memory.capsules)
        selected = [item for item in capsules if item.get("status") == "open" and not item.get("human_confirmed")]
        selected.sort(key=lambda item: str(item.get("created", "")), reverse=True)
        return {"capsules": selected[:max(1, min(limit, 100))], "corrupt_lines": corrupt}

    @router.get("/memory/recent")
    async def memory_recent(request: Request, limit: int = 20):
        _require_api_scope(request, "misumi:read")
        capsules, corrupt = memory_call(memory.capsules)
        capsules.sort(key=lambda item: str(item.get("created", "")), reverse=True)
        return {"capsules": capsules[:max(1, min(limit, 100))], "corrupt_lines": corrupt}

    @router.get("/memory/open-loops")
    async def memory_open_loops(request: Request):
        _require_api_scope(request, "misumi:read")
        loops, corrupt = memory_call(memory.loops)
        selected = [item for item in loops if item.get("status") == "open"]
        selected.sort(key=lambda item: str(item.get("created", "")))
        return {"open_loops": selected, "corrupt_lines": corrupt}

    @router.post("/memory/{capsule_id}/confirm")
    async def confirm_memory(request: Request, capsule_id: str):
        _require_api_scope(request, "misumi:execute")
        return memory_call(memory.confirm, capsule_id)

    @router.post("/memory/{capsule_id}/route")
    async def route_memory(request: Request, capsule_id: str, body: MisumiMemoryRouteRequest):
        _require_api_scope(request, "misumi:execute")
        return memory_call(memory.reroute, capsule_id, body.persona_primary, body.persona_secondary)

    @router.post("/memory/{capsule_id}/close")
    async def close_memory(request: Request, capsule_id: str, body: Optional[MisumiMemoryCloseRequest] = None):
        _require_api_scope(request, "misumi:execute")
        return memory_call(memory.close, capsule_id, body.resolution if body else None)

    @router.post("/handoff")
    async def create_handoff(request: Request, body: MisumiHandoffRequest):
        _require_api_scope(request, "misumi:execute")
        return memory_call(
            memory.create_handoff, body.from_persona, body.to_persona, body.action,
            body.capsule_id, body.note,
        )

    @router.get("/handoffs")
    async def list_handoffs(request: Request, status: Optional[str] = None):
        _require_api_scope(request, "misumi:read")
        if status is not None and status not in {"pending", "resolved"}:
            raise HTTPException(422, "Unknown handoff status")
        handoffs, corrupt = memory_call(memory.handoffs)
        selected = [item for item in handoffs if status is None or item.get("status") == status]
        selected.sort(key=lambda item: str(item.get("created", "")), reverse=True)
        return {"handoffs": selected, "corrupt_lines": corrupt}

    @router.post("/handoffs/{handoff_id}/resolve")
    async def resolve_handoff(request: Request, handoff_id: str):
        _require_api_scope(request, "misumi:execute")
        return memory_call(memory.resolve_handoff, handoff_id)

    @router.get("/glance")
    async def glance(request: Request):
        _require_api_scope(request, "misumi:read")
        return memory_call(memory.glance)

    return router
