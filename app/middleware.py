import logging
import secrets
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.database import SessionLocal
from app.models import User

logger = logging.getLogger("yoyo")

CTK_COOKIE_NAME = "ctk"
CTK_MAX_AGE = 315360000  # 10 years

SKIP_LOG_PATHS = {"/health", "/docs", "/openapi.json", "/redoc"}


class CTKMiddleware(BaseHTTPMiddleware):
    """Assigns a cookie tracking key (ctk) to every visitor and resolves User."""

    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip CTK processing for CORS preflight requests
        if request.method == "OPTIONS":
            return await call_next(request)

        ctk = request.cookies.get(CTK_COOKIE_NAME)
        new_ctk = False

        if not ctk:
            ctk = secrets.token_urlsafe(24)
            new_ctk = True

        # Make CTK and resolved user available to route handlers
        request.state.ctk = ctk
        request.state.user = None
        if not new_ctk:
            db = SessionLocal()
            try:
                request.state.user = db.query(User).filter(User.ctk == ctk).first()
            finally:
                db.close()

        response: Response = await call_next(request)

        if new_ctk:
            is_local = request.url.hostname in ("localhost", "127.0.0.1")
            response.set_cookie(
                key=CTK_COOKIE_NAME,
                value=ctk,
                max_age=CTK_MAX_AGE,
                httponly=True,
                samesite="lax",
                secure=not is_local,
                path="/api",
                domain=".getyoyo.co" if not is_local else None,
            )

        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Logs method, path, status code, duration, and ctk for each request."""

    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.time()
        response = await call_next(request)
        duration_ms = round((time.time() - start) * 1000)

        path = request.url.path
        if path in SKIP_LOG_PATHS:
            return response

        ctk = getattr(request.state, "ctk", None)
        logger.info(
            f"{request.method} {path} {response.status_code}",
            extra={"extra_data": {
                "method": request.method,
                "path": path,
                "status": response.status_code,
                "duration_ms": duration_ms,
                "ctk": ctk,
            }},
        )
        return response
