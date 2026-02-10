# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Development

Uses **uv** for dependency management and virtual environment.

```bash
make install    # uv sync — install dependencies
make dev        # Start FastAPI dev server with hot reload (port 8000)
make run        # Start production server (port 8000)
make lint       # Ruff linter
make format     # Ruff formatter
make test       # Run pytest
```

Requires a `.env` file (copy from `.env.example`):
```
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/splitwaiser
CORS_ORIGINS=http://localhost:5173
```

For local dev with SQLite (no Postgres needed): just omit `DATABASE_URL` and it defaults to `sqlite:///./splitwaiser.db`.

## Architecture

**Stack:** Python 3.12+ · FastAPI · SQLAlchemy ORM · PostgreSQL (SQLite for dev) · uv

### Project Structure
```
app/
├── main.py          # FastAPI app, CORS, routes
├── database.py      # Engine, session, Base
├── models.py        # SQLAlchemy ORM models (Trip, Member, Expense, ExpenseMember, Settlement)
├── schemas.py       # Pydantic request/response schemas
├── serializers.py   # Model → JSON dict converters (match frontend types)
├── deps.py          # Shared dependencies (get_trip_by_token, verify_creator, token generators)
└── routes/
    ├── trips.py       # Trip CRUD + rotate-token
    ├── members.py     # Member CRUD (creator-only)
    ├── expenses.py    # Expense CRUD
    └── settlements.py # Settlement CRUD
```

### Auth Model
- **No accounts.** `access_token` in URL grants read + write access to a trip.
- `creator_token` (returned at trip creation, stored client-side) required for creator-only actions: manage members, rotate link, delete trip. Sent via `X-Creator-Token` header.
- `verify_creator()` dependency in `deps.py` checks the header.

### Data Model
- All amounts stored as integers in smallest currency unit (cents for USD/HKD, yen for JPY).
- `expense_members` junction table stores both involved members and split values.
- `settled_by_id` on Member replaces the old Trip-level `settledBy` map.
- Supported currencies: USD, HKD, JPY.

### Serialization
`serializers.py` converts SQLAlchemy models to dicts matching the frontend TypeScript types (camelCase: `paidBy`, `splitMethod`, `involvedMembers`, etc.).

### API Endpoints
All under `/api`. Trip access via `access_token` path param. Creator-only endpoints check `X-Creator-Token` header.

```
POST   /api/trips                                → Create trip
GET    /api/trips/{access_token}                  → Full trip data
PATCH  /api/trips/{access_token}                  → Update name
DELETE /api/trips/{access_token}                  → Delete [CREATOR]
POST   /api/trips/{access_token}/rotate-token     → Rotate link [CREATOR]
POST   /api/trips/{access_token}/members          → Add member [CREATOR]
PATCH  /api/trips/{access_token}/members/{id}     → Update member [CREATOR]
DELETE /api/trips/{access_token}/members/{id}     → Remove member [CREATOR]
POST   /api/trips/{access_token}/expenses         → Add expense
PUT    /api/trips/{access_token}/expenses/{id}    → Update expense
DELETE /api/trips/{access_token}/expenses/{id}    → Delete expense
POST   /api/trips/{access_token}/settlements      → Add settlement
DELETE /api/trips/{access_token}/settlements/{id} → Delete settlement
```
