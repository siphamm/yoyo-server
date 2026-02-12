import secrets

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.database import SessionLocal
from app.models import User

CTK_COOKIE_NAME = "ctk"
CTK_MAX_AGE = 315360000  # 10 years


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
                samesite="lax" if is_local else "none",
                secure=not is_local,
                path="/api",
            )

        return response
