import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Member, Expense, ExpenseMember, Settlement
from app.deps import get_trip_by_token, get_or_create_user, verify_creator
from app.exchange import SUPPORTED_CURRENCIES
from app.schemas import AddMemberIn, JoinTripIn, UpdateMemberIn
from app.serializers import serialize_member, serialize_trip

logger = logging.getLogger("yoyo")

router = APIRouter()


@router.post("/trips/{access_token}/members", status_code=201)
def add_member(
    access_token: str,
    data: AddMemberIn,
    request: Request,
    db: Session = Depends(get_db),
):
    trip = get_trip_by_token(access_token, db)
    verify_creator(trip, request, db)

    member = Member(trip_id=trip.id, name=data.name)
    db.add(member)
    trip.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(member)
    logger.info("Member added", extra={"extra_data": {"trip_id": trip.id, "member_name": data.name}})
    return serialize_member(member)


@router.patch("/trips/{access_token}/members/{member_id}")
def update_member(
    access_token: str,
    member_id: str,
    data: UpdateMemberIn,
    request: Request,
    db: Session = Depends(get_db),
):
    trip = get_trip_by_token(access_token, db)
    verify_creator(trip, request, db)

    member = db.query(Member).filter(
        Member.id == member_id, Member.trip_id == trip.id
    ).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    if data.name is not None:
        member.name = data.name

    # Handle settled_by_id: check it's explicitly in the request body
    if "settled_by_id" in (data.model_fields_set or set()):
        if data.settled_by_id is not None:
            settled_by_int = int(data.settled_by_id)
            # Verify the payer exists in this trip
            payer = db.query(Member).filter(
                Member.id == settled_by_int, Member.trip_id == trip.id
            ).first()
            if not payer:
                raise HTTPException(status_code=400, detail="Payer member not found")
            member.settled_by_id = settled_by_int
        else:
            member.settled_by_id = None

    # Handle settlement_currency
    if "settlement_currency" in (data.model_fields_set or set()):
        sc = data.settlement_currency
        if sc is not None and sc not in SUPPORTED_CURRENCIES:
            raise HTTPException(status_code=400, detail="Invalid settlement currency")
        member.settlement_currency = sc

    trip.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(member)
    return serialize_member(member)


@router.delete("/trips/{access_token}/members/{member_id}", status_code=204)
def remove_member(
    access_token: str,
    member_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    trip = get_trip_by_token(access_token, db)
    verify_creator(trip, request, db)

    member = db.query(Member).filter(
        Member.id == member_id, Member.trip_id == trip.id
    ).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    # Check referential integrity
    in_expenses = db.query(ExpenseMember).filter(
        ExpenseMember.member_id == member_id
    ).first()
    paid_expenses = db.query(Expense).filter(
        Expense.paid_by_id == member_id
    ).first()
    in_settlements = db.query(Settlement).filter(
        (Settlement.from_member_id == member_id) | (Settlement.to_member_id == member_id)
    ).first()

    if in_expenses or paid_expenses or in_settlements:
        raise HTTPException(
            status_code=409,
            detail="Member is referenced in expenses or settlements",
        )

    # Clear settled_by references pointing to this member
    db.query(Member).filter(Member.settled_by_id == member_id).update(
        {"settled_by_id": None}
    )

    db.delete(member)
    trip.updated_at = datetime.utcnow()
    db.commit()
    return None


@router.post("/trips/{access_token}/claim/{member_id}")
def claim_member(
    access_token: str,
    member_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    trip = get_trip_by_token(access_token, db)
    user = get_or_create_user(request, db)
    if not user:
        raise HTTPException(status_code=400, detail="No user found for this browser")

    member = db.query(Member).filter(
        Member.id == member_id, Member.trip_id == trip.id
    ).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    # Prevent claiming the creator member
    if trip.creator_member_id and member.id == trip.creator_member_id:
        raise HTTPException(status_code=403, detail="Cannot claim the trip creator")

    # Clear this user's claim on any other member in the same trip
    db.query(Member).filter(
        Member.trip_id == trip.id,
        Member.user_id == user.id,
        Member.id != member_id,
    ).update({"user_id": None})

    member.user_id = user.id
    db.commit()
    db.refresh(member)
    logger.info("Member claimed", extra={"extra_data": {"trip_id": trip.id, "member_id": member.id, "user_id": user.id}})
    return serialize_member(member)


@router.post("/trips/{access_token}/join")
def join_trip(
    access_token: str,
    data: JoinTripIn,
    request: Request,
    db: Session = Depends(get_db),
):
    trip = get_trip_by_token(access_token, db)
    if not trip.allow_member_self_join:
        raise HTTPException(status_code=403, detail="Self-join is not allowed for this trip")

    user = get_or_create_user(request, db)
    if not user:
        raise HTTPException(status_code=400, detail="No user found for this browser")

    # Check if user already has a claimed member in this trip
    existing_claim = db.query(Member).filter(
        Member.trip_id == trip.id, Member.user_id == user.id
    ).first()
    if existing_claim:
        raise HTTPException(status_code=409, detail="You already have a member in this trip")

    # Check for name collision
    name_match = db.query(Member).filter(
        Member.trip_id == trip.id, Member.name == data.name
    ).first()
    if name_match and not data.force:
        return {"conflict": True, "existing_member_id": str(name_match.id), "message": f"A member named '{data.name}' already exists"}

    # Create new member and auto-claim
    member = Member(trip_id=trip.id, name=data.name)
    db.add(member)
    db.flush()
    member.user_id = user.id
    trip.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(trip)
    logger.info("Member joined", extra={"extra_data": {"trip_id": trip.id, "member_name": data.name, "user_id": user.id}})
    return serialize_trip(trip, is_creator=False, user_id=user.id)
