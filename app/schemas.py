from pydantic import BaseModel, Field


# --- Trip ---

class CreateTripIn(BaseModel):
    name: str
    currency: str = "USD"
    members: list[str]  # list of member names
    creator_name: str
    email: str | None = None


class UpdateTripIn(BaseModel):
    name: str | None = None
    currency: str | None = None
    settlement_currency: str | None = None
    password: str | None = None
    allow_member_edit_expenses: bool | None = None
    allow_member_self_join: bool | None = None


# --- Members ---

class AddMemberIn(BaseModel):
    name: str


class JoinTripIn(BaseModel):
    name: str
    force: bool = False  # if True, add even if name matches existing member


class UpdateMemberIn(BaseModel):
    name: str | None = None
    settled_by_id: str | None = None
    settlement_currency: str | None = None


# --- Expenses ---

class ExpenseIn(BaseModel):
    description: str
    amount: int
    paid_by: str
    date: str
    split_method: str
    split_details: dict[str, float] = {}
    involved_members: list[str]
    currency: str | None = None


# --- Settlements ---

class SettlementIn(BaseModel):
    from_member: str = Field(alias="from")
    to: str
    amount: int
    date: str
    currency: str | None = None

    model_config = {"populate_by_name": True}
