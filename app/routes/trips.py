from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.email import send_trip_link
from app.models import Trip, Member
from app.deps import generate_access_token, generate_creator_token, get_trip_by_token, get_user_by_ctk, verify_creator
from app.ratelimit import limiter
from app.schemas import CreateTripIn, UpdateTripIn
from app.serializers import serialize_trip

router = APIRouter()


@router.post("/trips", status_code=201)
@limiter.limit("5/hour")
def create_trip(request: Request, data: CreateTripIn, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    if len(data.members) < 1:
        raise HTTPException(status_code=400, detail="At least 1 member required")
    if data.creator_name not in data.members:
        raise HTTPException(status_code=400, detail="Creator must be one of the members")
    if data.currency not in ("USD", "HKD", "JPY"):
        raise HTTPException(status_code=400, detail="Currency must be USD, HKD, or JPY")

    trip = Trip(
        access_token=generate_access_token(),
        creator_token=generate_creator_token(),
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

    if creator_member:
        trip.creator_member_id = creator_member.id
        user = get_user_by_ctk(request, db)
        if user:
            creator_member.user_id = user.id

    db.commit()
    db.refresh(trip)

    if data.email:
        background_tasks.add_task(send_trip_link, data.email, trip.name, trip.access_token)

    return {
        "trip": serialize_trip(trip, is_creator=True),
        "creator_token": trip.creator_token,
    }


@router.get("/trips/{access_token}")
def get_trip(
    access_token: str,
    db: Session = Depends(get_db),
    x_creator_token: str | None = Header(None),
):
    trip = get_trip_by_token(access_token, db)
    is_creator = bool(x_creator_token and x_creator_token == trip.creator_token)
    return serialize_trip(trip, is_creator=is_creator)


@router.patch("/trips/{access_token}")
def update_trip(
    access_token: str,
    data: UpdateTripIn,
    db: Session = Depends(get_db),
    x_creator_token: str | None = Header(None),
):
    trip = get_trip_by_token(access_token, db)
    verify_creator(trip, x_creator_token)

    if data.name is not None:
        trip.name = data.name

    # settlement_currency: use UNSET sentinel to distinguish null (clear) from absent
    raw = data.model_dump(exclude_unset=True)
    if "settlement_currency" in raw:
        sc = data.settlement_currency
        if sc is not None and sc not in ("USD", "HKD", "JPY"):
            raise HTTPException(status_code=400, detail="Invalid settlement currency")
        trip.settlement_currency = sc

    trip.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(trip)
    is_creator = bool(x_creator_token and x_creator_token == trip.creator_token)
    return serialize_trip(trip, is_creator=is_creator)


@router.delete("/trips/{access_token}", status_code=204)
def delete_trip(
    access_token: str,
    db: Session = Depends(get_db),
    x_creator_token: str | None = Header(None),
):
    trip = get_trip_by_token(access_token, db)
    verify_creator(trip, x_creator_token)
    trip.is_deleted = True
    trip.updated_at = datetime.utcnow()
    db.commit()
    return None


@router.post("/trips/{access_token}/rotate-token")
def rotate_token(
    access_token: str,
    db: Session = Depends(get_db),
    x_creator_token: str | None = Header(None),
):
    trip = get_trip_by_token(access_token, db)
    verify_creator(trip, x_creator_token)
    trip.access_token = generate_access_token()
    trip.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(trip)
    return {"access_token": trip.access_token}
