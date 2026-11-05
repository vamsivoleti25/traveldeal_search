"""Gift card discount snapshot (data/giftcards.json).

Refreshed by scripts/refresh_giftcards.py (the opt-in "Refresh gift card discounts" workflow).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from .catalog import DATA_DIR

CATEGORY_NAMES = {
    "hotel": "Hotel",
    "airline": "Airline",
    "cruise": "Cruise",
    "vacation_rental": "Vacation rental",
    "rideshare": "Rideshare",
    "rail": "Rail",
    "attraction": "Attraction",
    "travel_booking": "Travel booking",
    "dining": "Dining",
    "retail": "Retail",
    "electronics": "Electronics",
    "home": "Home",
    "gas": "Gas",
}

# Gift card categories that map onto a booking the comparison engine understands.
CATEGORY_TO_BOOKING = {
    "hotel": "hotel",
    "airline": "flight",
    "cruise": "cruise",
    "vacation_rental": "vacation_rental",
    "travel_booking": "hotel",
    "attraction": "attraction",
}


@dataclass(frozen=True)
class GiftCardSeller:
    """Where you can buy the gift card at a discount (a resale marketplace or an official retailer)."""

    name: str
    slug: str
    discount_pct: float
    notes: tuple[str, ...] = ()

    @property
    def conditional(self) -> bool:
        """Offers that need something extra (e.g. "DashPass Required"); CardBear's headline discount skips them."""
        return any("required" in n.lower() for n in self.notes)

    @property
    def guarantee_days(self) -> int | None:
        m = next((n for n in self.notes if n.endswith("-Day Guarantee")), None)
        return int(m.split("-")[0]) if m and m.split("-")[0].isdigit() else None


@dataclass(frozen=True)
class GiftCardBrand:
    id: str
    name: str
    category: str
    travel: bool
    discount_pct: float
    live_url: str
    merchant: str | None = None
    avg_12m_pct: float | None = None
    high_12m_pct: float | None = None
    sellers: tuple[GiftCardSeller, ...] = ()

    @property
    def best_seller(self) -> GiftCardSeller | None:
        """Best seller anyone can buy from (offers with a membership requirement don't count)."""
        return max((s for s in self.sellers if not s.conditional), key=lambda s: s.discount_pct, default=None)


@dataclass(frozen=True)
class GiftCardSnapshot:
    as_of: str
    source_name: str
    source_url: str
    source_note: str
    brands: tuple[GiftCardBrand, ...]


@lru_cache(maxsize=1)
def load_gift_cards(path: Path = DATA_DIR / "giftcards.json") -> GiftCardSnapshot:
    raw = json.loads(path.read_text(encoding="utf-8"))
    brands = tuple(
        GiftCardBrand(
            id=b["id"],
            name=b["name"],
            category=b["category"],
            travel=b["travel"],
            discount_pct=float(b["discountPct"]),
            live_url=b["liveUrl"],
            merchant=b.get("merchant"),
            avg_12m_pct=b.get("avg12mPct"),
            high_12m_pct=b.get("high12mPct"),
            sellers=tuple(
                GiftCardSeller(x["name"], x.get("slug", x["name"].lower()), float(x["discountPct"]), tuple(x.get("notes", [])))
                for x in sorted(b.get("sellers", []), key=lambda x: -x["discountPct"])
            ),
        )
        for b in raw["brands"]
    )
    src = raw["source"]
    return GiftCardSnapshot(raw["asOf"], src["name"], src["url"], src["note"], brands)


def best_gift_card_for(merchant: str | None) -> GiftCardBrand | None:
    """Best snapshot discount for a gift card that works across a whole loyalty program (e.g. Marriott)."""
    if not merchant:
        return None
    matches = [b for b in load_gift_cards().brands if b.merchant == merchant]
    return max(matches, key=lambda b: b.discount_pct, default=None)
