from app.models import Trip, Expense, Settlement, ExpenseMember


def serialize_member(member) -> dict:
    return {
        "id": member.id,
        "name": member.name,
        "settled_by_id": member.settled_by_id,
    }


def serialize_expense(expense: Expense) -> dict:
    involved_members = []
    split_details = {}
    for em in expense.involved_members:
        involved_members.append(em.member_id)
        if em.split_value is not None:
            split_details[em.member_id] = float(em.split_value)

    return {
        "id": expense.id,
        "description": expense.description,
        "amount": expense.amount,
        "paidBy": expense.paid_by_id,
        "date": expense.date.isoformat(),
        "splitMethod": expense.split_method,
        "splitDetails": split_details,
        "involvedMembers": involved_members,
        "currency": expense.currency,
    }


def serialize_settlement(settlement: Settlement) -> dict:
    return {
        "id": settlement.id,
        "from": settlement.from_member_id,
        "to": settlement.to_member_id,
        "amount": settlement.amount,
        "date": settlement.date.isoformat(),
        "currency": settlement.currency,
    }


def serialize_trip(trip: Trip, is_creator: bool = False) -> dict:
    return {
        "id": trip.id,
        "access_token": trip.access_token,
        "name": trip.name,
        "currency": trip.currency,
        "members": [serialize_member(m) for m in trip.members],
        "expenses": [serialize_expense(e) for e in trip.expenses],
        "settlements": [serialize_settlement(s) for s in trip.settlements],
        "createdAt": trip.created_at.isoformat(),
        "updatedAt": trip.updated_at.isoformat(),
        "creator_member_id": trip.creator_member_id,
        "is_creator": is_creator,
    }
