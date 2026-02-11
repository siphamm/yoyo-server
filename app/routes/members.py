from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Member, Expense, ExpenseMember, Settlement
from app.deps import get_trip_by_token, get_user_by_ctk, verify_creator
from app.schemas import AddMemberIn, UpdateMemberIn
from app.serializers import serialize_member

router = APIRouter()


@router.post("/trips/{access_token}/members", status_code=201)
def add_member(
    access_token: str,
    data: AddMemberIn,
    db: Session = Depends(get_db),
    x_creator_token: str | None = Header(None),
):
    trip = get_trip_by_token(access_token, db)
    verify_creator(trip, x_creator_token)

    member = Member(trip_id=trip.id, name=data.name)
    db.add(member)
    trip.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(member)
    return serialize_member(member)


@router.patch("/trips/{access_token}/members/{member_id}")
def update_member(
    access_token: str,
    member_id: str,
    data: UpdateMemberIn,
    db: Session = Depends(get_db),
    x_creator_token: str | None = Header(None),
):
    trip = get_trip_by_token(access_token, db)
    verify_creator(trip, x_creator_token)

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
            # Verify the payer exists in this trip
            payer = db.query(Member).filter(
                Member.id == data.settled_by_id, Member.trip_id == trip.id
            ).first()
            if not payer:
                raise HTTPException(status_code=400, detail="Payer member not found")
        member.settled_by_id = data.settled_by_id

    # Handle settlement_currency
    if "settlement_currency" in (data.model_fields_set or set()):
        sc = data.settlement_currency
        if sc is not None and sc not in ("USD", "HKD", "JPY"):
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
    db: Session = Depends(get_db),
    x_creator_token: str | None = Header(None),
):
    trip = get_trip_by_token(access_token, db)
    verify_creator(trip, x_creator_token)

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
    user = get_user_by_ctk(request, db)
    if not user:
        raise HTTPException(status_code=400, detail="No user found for this browser")

    member = db.query(Member).filter(
        Member.id == member_id, Member.trip_id == trip.id
    ).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    member.user_id = user.id
    db.commit()
    db.refresh(member)
    return serialize_member(member)
