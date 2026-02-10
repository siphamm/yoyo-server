import uuid
from datetime import datetime, date as date_type

from sqlalchemy import (
    Column, String, Integer, Numeric, Date, DateTime, ForeignKey, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship

from app.database import Base


def new_uuid():
    return str(uuid.uuid4())


class Trip(Base):
    __tablename__ = "trips"

    id = Column(String, primary_key=True, default=new_uuid)
    access_token = Column(String(24), unique=True, nullable=False, index=True)
    creator_token = Column(String(48), nullable=False)
    creator_member_id = Column(String, ForeignKey("members.id", use_alter=True), nullable=True)
    name = Column(String(255), nullable=False)
    currency = Column(String(3), nullable=False, default="USD")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    members = relationship("Member", back_populates="trip", foreign_keys="Member.trip_id", cascade="all, delete-orphan")
    expenses = relationship("Expense", back_populates="trip", cascade="all, delete-orphan")
    settlements = relationship("Settlement", back_populates="trip", cascade="all, delete-orphan")


class Member(Base):
    __tablename__ = "members"

    id = Column(String, primary_key=True, default=new_uuid)
    trip_id = Column(String, ForeignKey("trips.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    settled_by_id = Column(String, ForeignKey("members.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    trip = relationship("Trip", back_populates="members", foreign_keys=[trip_id])


class Expense(Base):
    __tablename__ = "expenses"

    id = Column(String, primary_key=True, default=new_uuid)
    trip_id = Column(String, ForeignKey("trips.id", ondelete="CASCADE"), nullable=False)
    description = Column(String(500), nullable=False)
    amount = Column(Integer, nullable=False)
    paid_by_id = Column(String, ForeignKey("members.id", ondelete="RESTRICT"), nullable=False)
    date = Column(Date, nullable=False)
    split_method = Column(String(20), nullable=False)
    currency = Column(String(3), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    trip = relationship("Trip", back_populates="expenses")
    involved_members = relationship("ExpenseMember", back_populates="expense", cascade="all, delete-orphan")


class ExpenseMember(Base):
    __tablename__ = "expense_members"

    id = Column(String, primary_key=True, default=new_uuid)
    expense_id = Column(String, ForeignKey("expenses.id", ondelete="CASCADE"), nullable=False)
    member_id = Column(String, ForeignKey("members.id", ondelete="RESTRICT"), nullable=False)
    split_value = Column(Numeric, nullable=True)

    __table_args__ = (UniqueConstraint("expense_id", "member_id"),)

    expense = relationship("Expense", back_populates="involved_members")


class Settlement(Base):
    __tablename__ = "settlements"

    id = Column(String, primary_key=True, default=new_uuid)
    trip_id = Column(String, ForeignKey("trips.id", ondelete="CASCADE"), nullable=False)
    from_member_id = Column(String, ForeignKey("members.id", ondelete="RESTRICT"), nullable=False)
    to_member_id = Column(String, ForeignKey("members.id", ondelete="RESTRICT"), nullable=False)
    amount = Column(Integer, nullable=False)
    date = Column(Date, nullable=False)
    currency = Column(String(3), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    trip = relationship("Trip", back_populates="settlements")
