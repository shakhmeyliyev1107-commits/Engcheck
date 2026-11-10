"""FastAPI ilovasi."""
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from ..config import Settings
from ..ai.registry import build
from ..core.db import init_db
from ..core.secrets import SecretStore
from . import (routes_ai, routes_audit, routes_auth, routes_dashboard, routes_documents, routes_findings,
               routes_kb, routes_projects, routes_reviews)
from .deps import locale_of
from .errors import MESSAGES, ApiError, localize

FRONTEND_DIST = Path(__file__).resolve().parents[3] / "frontend" / "dist"
_STATUS_CODES = {401: "unauthorized", 403: "forbidden", 404: "not_found"}


def _error(request: Request, status: int, code: str, **fmt) -> JSONResponse:
    return JSONResponse({"code": code, "message": localize(MESSAGES, code, locale_of(request), **fmt)},
                        status_code=status)


def create_app(settings: Settings, frontend_dist: Path | None = FRONTEND_DIST) -> FastAPI:
    app = FastAPI(title="EngCheck", docs_url="/api/docs", openapi_url="/api/openapi.json")
    app.state.settings = settings
    app.state.session_factory = init_db(settings.db_url)
    app.state.secrets = SecretStore(settings.data_dir)
    app.state.provider_factory = build   # testlarda soxta provayder bilan almashtiriladi

    for module in (routes_auth, routes_projects, routes_documents, routes_reviews, routes_findings,
                   routes_dashboard, routes_audit, routes_ai, routes_kb):
        app.include_router(module.router, prefix="/api")

    @app.exception_handler(ApiError)
    async def api_error(request: Request, exc: ApiError):
        return _error(request, exc.status, exc.code, **exc.fmt)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        first = exc.errors()[0] if exc.errors() else {}
        field = ".".join(str(p) for p in first.get("loc", []) if p not in ("body", "query", "path"))
        return _error(request, 422, "validation_error", detail=field or "?")

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException):
        return _error(request, exc.status_code, _STATUS_CODES.get(exc.status_code, "internal_error"))

    @app.exception_handler(Exception)
    async def unexpected(request: Request, exc: Exception):
        return _error(request, 500, "internal_error")

    if frontend_dist is not None and (frontend_dist / "index.html").is_file():
        root = frontend_dist.resolve()

        @app.get("/{path:path}", include_in_schema=False)
        async def spa(path: str):
            if path.startswith("api/") or path == "api":
                raise StarletteHTTPException(404)
            target = (root / path).resolve()
            if path and target.is_file() and root in target.parents:
                return FileResponse(target)
            return FileResponse(root / "index.html")

    return app
