import logging
import secrets

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Member, Trip, User

logger = logging.getLogger("yoyo")


def generate_access_token() -> str:
    return secrets.token_urlsafe(18)  # ~24 chars


def get_trip_by_token(
    access_token: str,
    db: Session = Depends(get_db),
) -> Trip:
    trip = db.query(Trip).filter(Trip.access_token == access_token, Trip.is_deleted == False).first()  # noqa: E712
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    return trip


def verify_creator(trip: Trip, request: Request, db: Session) -> None:
    """Check that the current user is the trip creator via CTK-derived user."""
    user = getattr(request.state, "user", None)
    if user and trip.creator_member_id:
        creator_member = (
            db.query(Member)
            .filter(Member.id == trip.creator_member_id)
            .first()
        )
        if creator_member and creator_member.user_id == user.id:
            return

    logger.warning("Creator verification failed", extra={"extra_data": {"trip_id": trip.id}})
    raise HTTPException(status_code=403, detail="Creator token required")


def get_ctk(request: Request) -> str | None:
    """Read the cookie tracking key from the request."""
    return getattr(request.state, "ctk", None)


def get_or_create_user(request: Request, db: Session) -> User | None:
    """Look up or create a User for the request's ctk cookie."""
    ctk = get_ctk(request)
    if not ctk:
        return None
    user = db.query(User).filter(User.ctk == ctk).first()
    if not user:
        user = User(ctk=ctk)
        db.add(user)
        db.flush()
    return user
