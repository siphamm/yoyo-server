from datetime import datetime, date as date_type, timedelta

import httpx
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import ExchangeRate

SUPPORTED_CURRENCIES = (
    "USD", "EUR", "GBP", "JPY", "CAD", "AUD", "CHF", "HKD",
    "SGD", "THB", "KRW", "INR", "CNY", "NZD", "MXN",
)
FRANKFURTER_BASE = "https://api.frankfurter.dev/v1"


def get_rate(db: Session, base: str, target: str) -> tuple[float, date_type]:
    """Get exchange rate from cache or fetch from frankfurter.dev.

    Returns (rate, date) tuple.
    Rates are cached permanently; "latest" rates refresh if older than 24h.
    """
    if base == target:
        return 1.0, date_type.today()

    now = datetime.utcnow()
    cutoff = now - timedelta(hours=24)

    # Check cache for a recent rate
    cached = (
        db.query(ExchangeRate)
        .filter(
            ExchangeRate.base_currency == base,
            ExchangeRate.target_currency == target,
            ExchangeRate.fetched_at >= cutoff,
        )
        .order_by(ExchangeRate.fetched_at.desc())
        .first()
    )
    if cached:
        return float(cached.rate), cached.date

    # Fetch from API
    resp = httpx.get(
        f"{FRANKFURTER_BASE}/latest",
        params={"from": base, "to": target},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()

    rate_value = data["rates"][target]
    rate_date = date_type.fromisoformat(data["date"])

    # Upsert into cache
    existing = (
        db.query(ExchangeRate)
        .filter(
            ExchangeRate.date == rate_date,
            ExchangeRate.base_currency == base,
            ExchangeRate.target_currency == target,
        )
        .first()
    )
    if existing:
        existing.rate = rate_value
        existing.fetched_at = now
    else:
        db.add(
            ExchangeRate(
                date=rate_date,
                base_currency=base,
                target_currency=target,
                rate=rate_value,
                fetched_at=now,
            )
        )
    try:
        db.commit()
    except IntegrityError:
        # Race condition: another request already inserted this rate
        db.rollback()

    return float(rate_value), rate_date


def get_rates_for_currencies(
    db: Session, target: str, currencies: list[str]
) -> tuple[dict[str, float], date_type | None]:
    """Get exchange rates from multiple currencies to a target currency.

    Returns ({currency: rate}, date) where rate converts 1 unit of currency to target.
    Only includes currencies different from target.
    """
    rates: dict[str, float] = {}
    rate_date: date_type | None = None

    for currency in currencies:
        if currency == target:
            continue
        rate, d = get_rate(db, currency, target)
        rates[currency] = rate
        rate_date = d

    return rates, rate_date
