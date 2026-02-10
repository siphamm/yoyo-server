from datetime import datetime, date as date_type

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Settlement, Member
from app.deps import get_trip_by_token
from app.schemas import SettlementIn
from app.serializers import serialize_settlement

router = APIRouter()


@router.post("/trips/{access_token}/settlements", status_code=201)
def add_settlement(
    access_token: str,
    data: SettlementIn,
    db: Session = Depends(get_db),
):
    trip = get_trip_by_token(access_token, db)

    # Validate members belong to this trip
    trip_member_ids = {
        m.id for m in db.query(Member.id).filter(Member.trip_id == trip.id).all()
    }
    if data.from_member not in trip_member_ids:
        raise HTTPException(status_code=400, detail="'from' member not in this trip")
    if data.to not in trip_member_ids:
        raise HTTPException(status_code=400, detail="'to' member not in this trip")

    settlement = Settlement(
        trip_id=trip.id,
        from_member_id=data.from_member,
        to_member_id=data.to,
        amount=data.amount,
        date=date_type.fromisoformat(data.date),
        currency=data.currency,
    )
    db.add(settlement)
    trip.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(settlement)
    return serialize_settlement(settlement)


@router.delete("/trips/{access_token}/settlements/{settlement_id}", status_code=204)
def delete_settlement(
    access_token: str,
    settlement_id: str,
    db: Session = Depends(get_db),
):
    trip = get_trip_by_token(access_token, db)
    settlement = db.query(Settlement).filter(
        Settlement.id == settlement_id, Settlement.trip_id == trip.id
    ).first()
    if not settlement:
        raise HTTPException(status_code=404, detail="Settlement not found")

    db.delete(settlement)
    trip.updated_at = datetime.utcnow()
    db.commit()
    return None
