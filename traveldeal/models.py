"""Domain types for TravelDeal Search.

The card catalog is stored as camelCase JSON in data/ (shared with any future
frontend). These dataclasses are the Python view of it, built with from_dict().
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

BookingType = Literal["flight", "hotel", "car_rental", "vacation_rental", "cruise", "attraction"]
ChannelKind = Literal["direct", "portal", "ota", "giftcard"]
ValuationMode = Literal["cash", "transfer"]

BOOKING_TYPES: tuple[str, ...] = ("flight", "hotel", "car_rental", "vacation_rental", "cruise", "attraction")
TRAVEL_TYPES = frozenset(BOOKING_TYPES)


def _channel(value: Any) -> str | tuple[str, ...]:
    return tuple(value) if isinstance(value, list) else value


@dataclass(frozen=True)
class EarnRule:
    categories: tuple[str, ...]
    channel: str | tuple[str, ...]
    rate: float
    prepaid_only: bool = False
    merchant: str | None = None
    cap: float | None = None
    cap_period: str | None = None
    valid_from: str | None = None
    valid_until: str | None = None
    condition: str | None = None
    note: str | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> EarnRule:
        return cls(
            categories=tuple(d["categories"]),
            channel=_channel(d["channel"]),
            rate=float(d["rate"]),
            prepaid_only=bool(d.get("prepaidOnly", False)),
            merchant=d.get("merchant"),
            cap=d.get("cap"),
            cap_period=d.get("capPeriod"),
            valid_from=d.get("validFrom"),
            valid_until=d.get("validUntil"),
            condition=d.get("condition"),
            note=d.get("note"),
        )


@dataclass(frozen=True)
class Credit:
    id: str
    name: str
    amount: float
    period: str
    categories: tuple[str, ...]
    channel: str | tuple[str, ...]
    credited_amount_earns_points: bool
    merchant: str | None = None
    min_spend: float | None = None
    requires_tag: str | None = None
    note: str | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Credit:
        return cls(
            id=d["id"],
            name=d["name"],
            amount=float(d["amount"]),
            period=d["period"],
            categories=tuple(d["categories"]),
            channel=_channel(d["channel"]),
            credited_amount_earns_points=bool(d["creditedAmountEarnsPoints"]),
            merchant=d.get("merchant"),
            min_spend=d.get("minSpend"),
            requires_tag=d.get("requiresTag"),
            note=d.get("note"),
        )


@dataclass(frozen=True)
class Card:
    id: str
    name: str
    issuer: str
    network: str
    type: str
    annual_fee: float
    currency: str
    base_rate: float
    earn: tuple[EarnRule, ...]
    credits: tuple[Credit, ...]
    last_verified: str | None
    needs_verification: bool
    sources: tuple[str, ...]
    portal: str | None = None
    notes: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Card:
        return cls(
            id=d["id"],
            name=d["name"],
            issuer=d["issuer"],
            network=d["network"],
            type=d["type"],
            annual_fee=float(d["annualFee"]),
            currency=d["currency"],
            base_rate=float(d["baseRate"]),
            earn=tuple(EarnRule.from_dict(r) for r in d["earn"]),
            credits=tuple(Credit.from_dict(c) for c in d["credits"]),
            last_verified=d.get("lastVerified"),
            needs_verification=bool(d["needsVerification"]),
            sources=tuple(d["sources"]),
            portal=d.get("portal"),
            notes=tuple(d.get("notes", [])),
        )


@dataclass(frozen=True)
class Currency:
    id: str
    name: str
    cash_cpp: float
    transfer_cpp: float

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Currency:
        return cls(d["id"], d["name"], float(d["cashCpp"]), float(d["transferCpp"]))


@dataclass(frozen=True)
class LoyaltyProgram:
    id: str
    name: str
    kind: str
    points_per_dollar: float
    elite_bonus: dict[str, float]
    default_cpp: float
    earns_on_third_party_bookings: bool
    elite_perks_on_third_party_bookings: bool

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> LoyaltyProgram:
        return cls(
            id=d["id"],
            name=d["name"],
            kind=d["kind"],
            points_per_dollar=float(d["pointsPerDollar"]),
            elite_bonus={k: float(v) for k, v in d["eliteBonus"].items()},
            default_cpp=float(d["defaultCpp"]),
            earns_on_third_party_bookings=bool(d["earnsOnThirdPartyBookings"]),
            elite_perks_on_third_party_bookings=bool(d["elitePerksOnThirdPartyBookings"]),
        )


@dataclass
class Channel:
    id: str
    kind: str
    label: str
    price: float
    portal: str | None = None
    prepaid: bool | None = None
    gift_card_discount_pct: float | None = None
    gift_card_purchase_category: str | None = None
    tags: tuple[str, ...] = ()


@dataclass
class Booking:
    type: str
    channels: list[Channel]
    merchant: str | None = None
    direct_perks_value: float = 0.0


@dataclass
class UserSettings:
    valuation_mode: str = "cash"
    apply_credits: bool = True
    cpp_overrides: dict[str, float] = field(default_factory=dict)
    credits_used: dict[str, float] = field(default_factory=dict)
    cap_spend_used: dict[str, float] = field(default_factory=dict)
    elite_status: dict[str, str] = field(default_factory=dict)
    loyalty_cpp_overrides: dict[str, float] = field(default_factory=dict)
    today: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d = dict(self.__dict__)
        d.pop("today", None)
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> UserSettings:
        d = d or {}
        known = {k: v for k, v in d.items() if k in cls.__dataclass_fields__ and k != "today"}
        return cls(**known)


@dataclass
class LineItem:
    label: str
    amount: float  # positive = cost, negative = value back to you


@dataclass
class Option:
    channel_id: str
    channel_label: str
    channel_kind: str
    card_id: str
    card_name: str
    amount_charged: float
    card_points: int
    card_currency: str
    card_points_value: float
    credits_applied: float
    loyalty_points: int
    loyalty_value: float
    perks_value: float
    effective_cost: float
    return_pct: float
    breakdown: list[LineItem]
    warnings: list[str]

    @property
    def total_value(self) -> float:
        return round(self.credits_applied + self.card_points_value + self.loyalty_value + self.perks_value, 2)


@dataclass(frozen=True)
class CatalogData:
    cards: tuple[Card, ...]
    currencies: tuple[Currency, ...]
    loyalty: tuple[LoyaltyProgram, ...]

    def card(self, card_id: str) -> Card | None:
        return next((c for c in self.cards if c.id == card_id), None)

    def program(self, program_id: str | None) -> LoyaltyProgram | None:
        return next((p for p in self.loyalty if p.id == program_id), None) if program_id else None
