"""BBC route-level authentication and scoped bearer-token policy."""

from __future__ import annotations

from fastapi import HTTPException, Request

from src.auth_helpers import effective_user, require_user


_SCOPES = {
    "read": {"*", "admin", "bbc", "bbc:read"},
    "invoke": {"*", "admin", "bbc", "bbc:invoke"},
    "write": {"*", "admin", "bbc", "bbc:write"},
}

_CAPABILITY_GRANTS = {
    "bbc:invoke": {"repository:read"},
}


def require_bbc_access(request: Request, access: str = "read") -> str:
    """Authenticate the caller and enforce BBC scopes for bearer tokens."""

    if access not in _SCOPES:
        raise ValueError(f"unknown BBC access class: {access}")
    if getattr(request.state, "api_token", False):
        scopes = set(getattr(request.state, "api_token_scopes", ()) or ())
        if not scopes.intersection(_SCOPES[access]):
            raise HTTPException(403, f"API token requires bbc:{access} scope")
        return effective_user(request) or "api"
    return require_user(request) or "operator"


def bbc_caller_grants(request: Request) -> set[str]:
    """Return capability grants without bypassing the route authentication gate."""

    if getattr(request.state, "api_token", False):
        scopes = set(getattr(request.state, "api_token_scopes", ()) or ())
        grants = set(scopes)
        for scope in scopes:
            grants.update(_CAPABILITY_GRANTS.get(scope, ()))
        return grants
    # Browser callers have already passed require_user at the BBC route boundary.
    return {"*"}
