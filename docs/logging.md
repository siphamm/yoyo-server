# Logging & Monitoring

## Overview

| Layer | Tool | Env Var | Purpose |
|-------|------|---------|---------|
| Frontend | Google Analytics (GA4) | `VITE_GA_ID` | User behavior, page views, feature usage |
| Frontend | Sentry | `VITE_SENTRY_DSN` | JS errors, unhandled rejections |
| Backend | Sentry | `SENTRY_DSN` | Python exceptions, request context |
| Backend | Structured JSON logs | Always on | Request audit trail, action logs |

All are no-ops in development when env vars are unset.

---

## Frontend: Google Analytics

**File:** `src/lib/analytics.ts`

### Page Views
Tracked automatically on every route change in `App.tsx`:
- `/` (landing), `/trip/{token}`, `/trip/{token}/expenses`, `/balances`, `/settlements`
- `/about`, `/privacy`, `/help`

### Events

| Event | Where | When |
|-------|-------|------|
| `trip_created` | `TripCreateForm.tsx` | After successful trip creation |
| `expense_added` | `TripContext.tsx` | After expense API call succeeds |
| `expense_updated` | `TripContext.tsx` | After expense update succeeds |
| `expense_deleted` | `TripContext.tsx` | After expense delete succeeds |
| `settlement_recorded` | `TripContext.tsx` | After settlement API call succeeds |
| `member_added` | `TripContext.tsx` | After member add succeeds |
| `member_joined` | `TripContext.tsx` | After self-join succeeds (not on conflict) |
| `share_link_clicked` | `SettingsView.tsx` | When share button is tapped |
| `qr_shown` | `SettingsView.tsx` | When QR code is revealed |
| `language_changed` | `SideMenu.tsx` | When user switches language (includes `{ language }` param) |

---

## Frontend: Sentry

**File:** `src/main.tsx`

Automatically captures:
- Unhandled JavaScript errors
- Unhandled promise rejections
- Browser performance traces (10% sample rate)

---

## Backend: Sentry

**File:** `app/main.py`

Automatically captures:
- Unhandled FastAPI route exceptions
- Request context (URL, method)
- 10% transaction sample rate, no PII

---

## Backend: Structured Logs

**Format:** JSON to stdout (viewable in Render logs)

**File:** `app/logging_config.py`

```json
{"timestamp": "2026-02-14T12:00:00.000Z", "level": "INFO", "logger": "yoyo", "message": "POST /api/trips/abc123/expenses 201", "method": "POST", "path": "/api/trips/abc123/expenses", "status": 201, "duration_ms": 45, "ctk": "user_xyz"}
```

### Request Logging (every request)

**File:** `app/middleware.py` → `RequestLoggingMiddleware`

Logged for every request (except `/health`, `/docs`, `/openapi.json`, `/redoc`):
- HTTP method, path, status code, duration in ms, user CTK

### Action Logging

| Log Message | File | Level | Extra Data |
|-------------|------|-------|------------|
| `Trip created` | `routes/trips.py` | INFO | `trip_id`, `access_token` |
| `Trip deleted` | `routes/trips.py` | INFO | `trip_id` |
| `Expense added` | `routes/expenses.py` | INFO | `trip_id`, `expense_id` |
| `Expense updated` | `routes/expenses.py` | INFO | `trip_id`, `expense_id` |
| `Expense deleted` | `routes/expenses.py` | INFO | `trip_id`, `expense_id` |
| `Settlement recorded` | `routes/settlements.py` | INFO | `trip_id`, `from`, `to` |
| `Settlement deleted` | `routes/settlements.py` | INFO | `trip_id`, `settlement_id` |
| `Member added` | `routes/members.py` | INFO | `trip_id`, `member_name` |
| `Member claimed` | `routes/members.py` | INFO | `trip_id`, `member_id`, `user_id` |
| `Member joined` | `routes/members.py` | INFO | `trip_id`, `member_name`, `user_id` |
| `Creator verification failed` | `deps.py` | WARNING | `trip_id` |
| `Exchange rate fetch failed` | `exchange.py` | ERROR | `base`, `target` + traceback |
