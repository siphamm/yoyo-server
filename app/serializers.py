from app.models import Trip, Expense, Settlement


def serialize_member(member) -> dict:
    return {
        "id": str(member.id),
        "name": member.name,
        "user_id": str(member.user_id) if member.user_id is not None else None,
        "settled_by_id": str(member.settled_by_id) if member.settled_by_id is not None else None,
        "settlementCurrency": member.settlement_currency,
    }


def serialize_expense(expense: Expense) -> dict:
    involved_members = []
    split_details = {}
    for em in expense.involved_members:
        mid = str(em.member_id)
        involved_members.append(mid)
        if em.split_value is not None:
            split_details[mid] = float(em.split_value)

    return {
        "id": str(expense.id),
        "description": expense.description,
        "amount": expense.amount,
        "paidBy": str(expense.paid_by_id),
        "date": expense.date.isoformat(),
        "splitMethod": expense.split_method,
        "splitDetails": split_details,
        "involvedMembers": involved_members,
        "currency": expense.currency,
    }


def serialize_settlement(settlement: Settlement) -> dict:
    return {
        "id": str(settlement.id),
        "from": str(settlement.from_member_id),
        "to": str(settlement.to_member_id),
        "amount": settlement.amount,
        "date": settlement.date.isoformat(),
        "currency": settlement.currency,
    }


def serialize_trip_summary(trip: Trip) -> dict:
    return {
        "access_token": trip.access_token,
        "name": trip.name,
        "currency": trip.currency,
        "createdAt": trip.created_at.isoformat(),
        "updatedAt": trip.updated_at.isoformat(),
        "memberCount": len(trip.members),
    }


def serialize_trip(trip: Trip, is_creator: bool = False, user_id: int | None = None) -> dict:
    your_member_id = None
    if user_id:
        for m in trip.members:
            if m.user_id == user_id:
                your_member_id = str(m.id)
                break

    return {
        "id": str(trip.id),
        "access_token": trip.access_token,
        "name": trip.name,
        "currency": trip.currency,
        "settlementCurrency": trip.settlement_currency,
        "members": [serialize_member(m) for m in trip.members],
        "expenses": [serialize_expense(e) for e in trip.expenses],
        "settlements": [serialize_settlement(s) for s in trip.settlements],
        "createdAt": trip.created_at.isoformat(),
        "updatedAt": trip.updated_at.isoformat(),
        "creator_member_id": str(trip.creator_member_id) if trip.creator_member_id is not None else None,
        "is_creator": is_creator,
        "your_member_id": your_member_id,
        "isPasswordProtected": trip.password_hash is not None,
        "allowMemberEditExpenses": trip.allow_member_edit_expenses,
        "allowMemberSelfJoin": trip.allow_member_self_join,
    }
