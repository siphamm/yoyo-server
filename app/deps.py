import secrets

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Trip


def generate_access_token() -> str:
    return secrets.token_urlsafe(18)  # ~24 chars


def generate_creator_token() -> str:
    return secrets.token_urlsafe(36)  # ~48 chars


def get_trip_by_token(
    access_token: str,
    db: Session = Depends(get_db),
) -> Trip:
    trip = db.query(Trip).filter(Trip.access_token == access_token, Trip.is_deleted == False).first()  # noqa: E712
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    return trip


def verify_creator(
    trip: Trip,
    x_creator_token: str | None = Header(None),
) -> Trip:
    if not x_creator_token or x_creator_token != trip.creator_token:
        raise HTTPException(status_code=403, detail="Creator token required")
    return trip


def get_ctk(request: Request) -> str | None:
    """Read the cookie tracking key from the request."""
    return request.cookies.get("ctk")
