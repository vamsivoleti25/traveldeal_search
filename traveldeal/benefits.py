"""Benefit tracking: when each statement credit resets, and what's left to use."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from .models import Card, Credit, UserSettings

PERIOD_LABELS = {
    "calendar_year": "per calendar year",
    "anniversary_year": "per card year",
    "semiannual": "every half-year (Jan–Jun, Jul–Dec)",
    "quarterly": "every quarter",
}


def _month_end(year: int, month: int) -> date:
    first_next = date(year + (month == 12), 1 if month == 12 else month + 1, 1)
    return first_next - timedelta(days=1)


def period_end(period: str, today: date, anniversary_month: int | None = None) -> date | None:
    """Last day you can use this period's credit. None when it depends on an unknown card anniversary."""
    if period == "calendar_year":
        return date(today.year, 12, 31)
    if period == "semiannual":
        return date(today.year, 6, 30) if today.month <= 6 else date(today.year, 12, 31)
    if period == "quarterly":
        return _month_end(today.year, ((today.month - 1) // 3 + 1) * 3)
    if period == "anniversary_year":
        if not anniversary_month:
            return None
        year = today.year if today.month < anniversary_month else today.year + 1
        return date(year, anniversary_month, 1) - timedelta(days=1)
    return None


@dataclass
class CreditStatus:
    card: Card
    credit: Credit
    used: float
    remaining: float
    resets: date | None
    days_left: int | None

    @property
    def key(self) -> str:
        return f"{self.card.id}:{self.credit.id}"


def credit_statuses(cards: list[Card], settings: UserSettings, today: date) -> list[CreditStatus]:
    out = []
    for card in cards:
        for credit in card.credits:
            used = min(credit.amount, settings.credits_used.get(f"{card.id}:{credit.id}", 0.0))
            end = period_end(credit.period, today, settings.card_anniversary_month.get(card.id))
            out.append(CreditStatus(card, credit, used, credit.amount - used, end, (end - today).days if end else None))
    # Soonest-expiring unused credits first; unknown reset dates last.
    return sorted(out, key=lambda s: (s.remaining <= 0, s.days_left if s.days_left is not None else 10_000))
