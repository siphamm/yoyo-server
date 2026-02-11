import secrets

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.database import SessionLocal
from app.models import User

CTK_COOKIE_NAME = "ctk"
CTK_MAX_AGE = 315360000  # 10 years


class CTKMiddleware(BaseHTTPMiddleware):
    """Assigns a cookie tracking key (ctk) to every visitor."""

    async def dispatch(self, request: Request, call_next) -> Response:
        ctk = request.cookies.get(CTK_COOKIE_NAME)
        new_ctk = False

        if not ctk:
            ctk = secrets.token_urlsafe(24)
            new_ctk = True

        response: Response = await call_next(request)

        if new_ctk:
            # Create a User row for this new CTK
            db = SessionLocal()
            try:
                user = User(ctk=ctk)
                db.add(user)
                db.commit()
            finally:
                db.close()

            is_secure = request.url.hostname not in ("localhost", "127.0.0.1")
            response.set_cookie(
                key=CTK_COOKIE_NAME,
                value=ctk,
                max_age=CTK_MAX_AGE,
                httponly=True,
                samesite="lax",
                secure=is_secure,
                path="/api",
            )

        return response
