import hashlib
import logging
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.email import send_trip_link
from app.models import Trip, Member
from app.deps import generate_access_token, get_trip_by_token, get_or_create_user, verify_creator
from app.exchange import SUPPORTED_CURRENCIES
from app.ratelimit import limiter
from app.schemas import CreateTripIn, UpdateTripIn
from app.serializers import serialize_trip

logger = logging.getLogger("yoyo")


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

router = APIRouter()


@router.post("/trips", status_code=201)
@limiter.limit("5/hour")
def create_trip(request: Request, data: CreateTripIn, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    if len(data.members) < 1:
        raise HTTPException(status_code=400, detail="At least 1 member required")
    if data.creator_name not in data.members:
        raise HTTPException(status_code=400, detail="Creator must be one of the members")
    if data.currency not in SUPPORTED_CURRENCIES:
        raise HTTPException(status_code=400, detail="Unsupported currency")

    trip = Trip(
        access_token=generate_access_token(),
        name=data.name,
        currency=data.currency,
    )
    db.add(trip)
    db.flush()  # get trip.id

    creator_member = None
    for name in data.members:
        member = Member(trip_id=trip.id, name=name)
        db.add(member)
        if name == data.creator_name:
            creator_member = member

    db.flush()  # get member IDs

    user = get_or_create_user(request, db)
    if creator_member:
        trip.creator_member_id = creator_member.id
        if user:
            creator_member.user_id = user.id
            if not user.name:
                user.name = data.creator_name

    db.commit()
    db.refresh(trip)
    logger.info("Trip created", extra={"extra_data": {"trip_id": trip.id, "access_token": trip.access_token}})

    if data.email:
        background_tasks.add_task(send_trip_link, data.email, trip.name, trip.access_token)

    return {
        "trip": serialize_trip(trip, is_creator=True, user_id=user.id if user else None),
    }


@router.get("/trips/{access_token}")
def get_trip(
    access_token: str,
    request: Request,
    password: str | None = Query(None),
    db: Session = Depends(get_db),
):
    trip = get_trip_by_token(access_token, db)
    user = getattr(request.state, "user", None)
    user_id = user.id if user else None

    # Determine creator status
    is_creator = False
    if user_id and trip.creator_member_id:
        creator_member = db.query(Member).filter(Member.id == trip.creator_member_id).first()
        if creator_member and creator_member.user_id == user_id:
            is_creator = True

    # Password protection: non-creators must provide correct password
    if trip.password_hash and not is_creator:
        if not password or _hash_password(password) != trip.password_hash:
            raise HTTPException(
                status_code=403,
                detail={"message": "Password required", "password_protected": True},
            )

    return serialize_trip(trip, is_creator=is_creator, user_id=user_id)


@router.patch("/trips/{access_token}")
def update_trip(
    access_token: str,
    data: UpdateTripIn,
    request: Request,
    db: Session = Depends(get_db),
):
    trip = get_trip_by_token(access_token, db)
    verify_creator(trip, request, db)

    if data.name is not None:
        trip.name = data.name

    # currency: validate if provided
    raw = data.model_dump(exclude_unset=True)
    if "currency" in raw:
        c = data.currency
        if c is not None and c not in SUPPORTED_CURRENCIES:
            raise HTTPException(status_code=400, detail="Unsupported currency")
        if c is not None:
            trip.currency = c

    # settlement_currency: use UNSET sentinel to distinguish null (clear) from absent
    if "settlement_currency" in raw:
        sc = data.settlement_currency
        if sc is not None and sc not in SUPPORTED_CURRENCIES:
            raise HTTPException(status_code=400, detail="Invalid settlement currency")
        trip.settlement_currency = sc

    # password: set or clear trip password
    if "password" in raw:
        pw = data.password
        trip.password_hash = _hash_password(pw) if pw else None

    # permission settings
    if "allow_member_edit_expenses" in raw:
        trip.allow_member_edit_expenses = data.allow_member_edit_expenses
    if "allow_member_self_join" in raw:
        trip.allow_member_self_join = data.allow_member_self_join

    trip.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(trip)
    user = getattr(request.state, "user", None)
    return serialize_trip(trip, is_creator=True, user_id=user.id if user else None)


@router.delete("/trips/{access_token}", status_code=204)
def delete_trip(
    access_token: str,
    request: Request,
    db: Session = Depends(get_db),
):
    trip = get_trip_by_token(access_token, db)
    verify_creator(trip, request, db)
    trip.is_deleted = True
    trip.updated_at = datetime.utcnow()
    db.commit()
    logger.info("Trip deleted", extra={"extra_data": {"trip_id": trip.id}})
    return None


@router.post("/trips/{access_token}/rotate-token")
def rotate_token(
    access_token: str,
    request: Request,
    db: Session = Depends(get_db),
):
    trip = get_trip_by_token(access_token, db)
    verify_creator(trip, request, db)
    trip.access_token = generate_access_token()
    trip.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(trip)
    return {"access_token": trip.access_token}
