"""Human-readable labels for card rules and money."""

from __future__ import annotations

from .catalog import PORTAL_LABELS
from .models import Card, Credit, EarnRule

CATEGORY_LABELS = {
    "flight": "flights",
    "hotel": "hotels",
    "car_rental": "car rentals",
    "vacation_rental": "vacation rentals",
    "cruise": "cruises",
    "attraction": "attractions",
    "travel": "travel",
    "everything": "everything",
    "dining": "dining",
    "grocery": "groceries",
    "gas": "gas",
    "online_retail": "online shopping",
    "office_supply": "office supply stores",
    "drugstore": "drugstores",
    "wholesale_club": "wholesale clubs",
    "home_improvement": "home improvement",
    "transit": "transit",
    "rideshare": "rideshare",
    "streaming": "streaming",
    "entertainment": "entertainment",
    "phone_internet": "phone & internet",
    "advertising": "advertising",
    "shipping": "shipping",
    "fitness": "fitness",
    "rent": "rent",
    "foreign": "foreign purchases",
    "other": "other",
}

MERCHANT_LABELS = {
    "marriott": "Marriott",
    "hilton": "Hilton",
    "hyatt": "Hyatt",
    "ihg": "IHG",
    "wyndham": "Wyndham",
    "delta": "Delta",
    "united": "United",
    "american": "American Airlines",
    "southwest": "Southwest",
    "jetblue": "JetBlue",
    "alaska": "Alaska & Hawaiian",
    "air_canada": "Air Canada",
    "amazon": "Amazon",
    "apple": "Apple",
}

PERIOD_LABELS = {
    "billing_cycle": "billing cycle",
    "month": "month",
    "quarter": "quarter",
    "calendar_year": "year",
    "anniversary_year": "year",
    "semiannual": "half-year",
    "quarterly": "quarter",
}


def usd(n: float) -> str:
    sign = "−" if n < 0 else ""
    return f"{sign}${abs(n):,.2f}"


def _join(items: list[str]) -> str:
    if len(items) <= 2:
        return " & ".join(items)
    return f"{', '.join(items[:-1])} & {items[-1]}"


def rate_label(card: Card, rate: float) -> str:
    return f"{rate:g}%" if card.currency == "cash_back" else f"{rate:g}x"


def _channel_suffix(spec: str | tuple[str, ...], card: Card) -> str:
    portal = PORTAL_LABELS.get(card.portal or "", "the issuer portal")
    if spec == "any":
        return ""
    parts = spec if isinstance(spec, tuple) else (spec,)
    if parts == ("portal",):
        return f" via {portal}"
    if parts == ("direct",):
        return " booked direct"
    if "direct" in parts and "portal" in parts:
        return f" direct or via {portal}"
    if "direct" in parts and "ota" in parts:
        return " (not via portal)"
    return ""


def describe_rule(rule: EarnRule, card: Card) -> str:
    if rule.merchant:
        what = MERCHANT_LABELS.get(rule.merchant, rule.merchant) + (" hotels" if "hotel" in rule.categories else "")
    else:
        what = _join([CATEGORY_LABELS.get(c, c) for c in rule.categories])
    text = f"{rate_label(card, rule.rate)} {what}{_channel_suffix(rule.channel, card)}"
    return text + (" (prepaid)" if rule.prepaid_only else "")


def rule_details(rule: EarnRule) -> list[str]:
    out = []
    if rule.cap:
        out.append(f"up to ${rule.cap:,.0f}/{PERIOD_LABELS.get(rule.cap_period or 'calendar_year', 'year')}")
    if rule.valid_from and rule.valid_until:
        out.append(f"{rule.valid_from} to {rule.valid_until}")
    elif rule.valid_until:
        out.append(f"through {rule.valid_until}")
    elif rule.valid_from:
        out.append(f"from {rule.valid_from}")
    if rule.condition:
        out.append(rule.condition)
    return out


def describe_credit(credit: Credit) -> str:
    return f"{credit.name} (${credit.amount:,.0f}/{PERIOD_LABELS.get(credit.period, credit.period)})"
