from datetime import datetime, date as date_type

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Expense, ExpenseMember, Member
from app.deps import get_trip_by_token
from app.schemas import ExpenseIn
from app.serializers import serialize_expense

router = APIRouter()


def _validate_expense_members(db: Session, trip_id: str, involved_members: list[str], paid_by: str):
    """Validate that all referenced members belong to this trip."""
    trip_member_ids = {
        m.id for m in db.query(Member.id).filter(Member.trip_id == trip_id).all()
    }
    if paid_by not in trip_member_ids:
        raise HTTPException(status_code=400, detail="Payer is not a member of this trip")
    for mid in involved_members:
        if mid not in trip_member_ids:
            raise HTTPException(status_code=400, detail=f"Member {mid} is not in this trip")


def _sync_expense_members(db: Session, expense: Expense, involved_members: list[str], split_details: dict[str, float]):
    """Replace expense_members rows for an expense."""
    # Delete existing
    db.query(ExpenseMember).filter(ExpenseMember.expense_id == expense.id).delete()
    # Add new
    for member_id in involved_members:
        em = ExpenseMember(
            expense_id=expense.id,
            member_id=member_id,
            split_value=split_details.get(member_id),
        )
        db.add(em)


@router.post("/trips/{access_token}/expenses", status_code=201)
def add_expense(
    access_token: str,
    data: ExpenseIn,
    db: Session = Depends(get_db),
):
    trip = get_trip_by_token(access_token, db)
    _validate_expense_members(db, trip.id, data.involved_members, data.paid_by)

    expense = Expense(
        trip_id=trip.id,
        description=data.description,
        amount=data.amount,
        paid_by_id=data.paid_by,
        date=date_type.fromisoformat(data.date),
        split_method=data.split_method,
        currency=data.currency,
    )
    db.add(expense)
    db.flush()

    _sync_expense_members(db, expense, data.involved_members, data.split_details)

    trip.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(expense)
    return serialize_expense(expense)


@router.put("/trips/{access_token}/expenses/{expense_id}")
def update_expense(
    access_token: str,
    expense_id: str,
    data: ExpenseIn,
    db: Session = Depends(get_db),
):
    trip = get_trip_by_token(access_token, db)
    expense = db.query(Expense).filter(
        Expense.id == expense_id, Expense.trip_id == trip.id
    ).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")

    _validate_expense_members(db, trip.id, data.involved_members, data.paid_by)

    expense.description = data.description
    expense.amount = data.amount
    expense.paid_by_id = data.paid_by
    expense.date = date_type.fromisoformat(data.date)
    expense.split_method = data.split_method
    expense.currency = data.currency

    _sync_expense_members(db, expense, data.involved_members, data.split_details)

    trip.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(expense)
    return serialize_expense(expense)


@router.delete("/trips/{access_token}/expenses/{expense_id}", status_code=204)
def delete_expense(
    access_token: str,
    expense_id: str,
    db: Session = Depends(get_db),
):
    trip = get_trip_by_token(access_token, db)
    expense = db.query(Expense).filter(
        Expense.id == expense_id, Expense.trip_id == trip.id
    ).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")

    db.delete(expense)
    trip.updated_at = datetime.utcnow()
    db.commit()
    return None
