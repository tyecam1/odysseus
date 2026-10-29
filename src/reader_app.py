"""Compose a reader from existing auth/BBC routes, without joint runtime managers."""
from __future__ import annotations

import re
from pathlib import Path

from fastapi import Request
from fastapi.responses import JSONResponse, RedirectResponse


_READS = {
    "/", "/login", "/bbc", "/api/health", "/api/ready", "/api/version",
    "/api/auth/status", "/api/auth/features",
    "/api/bbc/v1/schemas", "/api/bbc/v1/health", "/api/bbc/v1/ship",
    "/api/bbc/v1/repositories", "/api/bbc/v1/capabilities",
    "/api/bbc/v1/capabilities/bbc.repository.inspect",
    "/api/bbc/v1/persona-locations", "/api/bbc/v1/audit", "/api/bbc/v1/state/events",
}
_AUTH_POSTS = {"/api/auth/setup", "/api/auth/signup", "/api/auth/login", "/api/auth/logout"}
_REPOSITORY_READ = re.compile(r"^/api/bbc/v1/repositories/[^/]+(?:/work-nodes|/resolve)?$")


class ReaderBoundary:
    """Default-deny before auth exemptions, request activity or endpoint execution."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] not in {"http", "websocket"}:
            return await self.app(scope, receive, send)
        path = scope.get("path", "")
        method = scope.get("method", "")
        allowed = scope["type"] == "http" and (
            (method in {"GET", "HEAD"} and (path in _READS or path.startswith("/static/") or _REPOSITORY_READ.fullmatch(path)))
            or (method == "POST" and (path in _AUTH_POSTS or path == "/api/bbc/v1/capabilities/bbc.repository.inspect/invoke"))
        )
        if not allowed:
            if scope["type"] == "websocket":
                return await send({"type": "websocket.close", "code": 1008})
            return await JSONResponse({"detail": "operation unavailable in reader profile"}, status_code=403)(scope, receive, send)
        return await self.app(scope, receive, send)


def configure_reader_app(app, auth_manager, profile):
    from routes.auth_routes import setup_auth_routes
    from routes.bbc_routes import setup_bbc_routes
    from src.app_helpers import serve_html_with_nonce
    from src.constants import STATIC_DIR, APP_VERSION

    app.include_router(setup_auth_routes(auth_manager))
    app.include_router(setup_bbc_routes())

    @app.get("/")
    async def index():
        return RedirectResponse("/bbc")

    @app.get("/login")
    async def login(request: Request):
        return serve_html_with_nonce(request, str(Path(STATIC_DIR) / "login.html"))

    @app.get("/api/health")
    async def health():
        return {"status": "ok"}

    @app.get("/api/ready")
    async def ready():
        return {"ready": True, "profile": profile.name}

    @app.get("/api/version")
    async def version():
        return {"version": APP_VERSION}

    app.state.runtime_profile = profile.name
    # Added last: this is the outermost boundary, including routes registered above.
    app.add_middleware(ReaderBoundary)
