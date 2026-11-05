"""Where to buy a gift card, and which of your cards to buy it with.

A gift card saves you money twice: the seller's discount, plus the points your card earns
on what you actually pay. The best combination isn't always the biggest discount: a
grocery store selling the card at face value can beat a 4% online discount if your
grocery card earns 6%.

    net cost = what you pay for the gift card - value of the card points earned on it
    total savings % = (face value - net cost) / face value
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .engine import PurchaseContext, compute_earn, cpp_for, round2, today_iso
from .giftcards import GiftCardBrand
from .models import Card, CatalogData, UserSettings

# Stores that often sell travel gift cards at face value, and the purchase category they code as.
STORES = {
    "grocery": "Grocery store",
    "drugstore": "Drugstore",
    "office_supply": "Office supply store",
    "gas": "Gas station",
}
# Online gift card resellers don't have a bonus category on most cards, so they earn the base rate.
MARKETPLACE_CATEGORY = "other"


@dataclass
class CardEarn:
    card_id: str
    card_name: str
    points: float
    rate: float
    value: float


@dataclass
class BuyOption:
    venue: str
    venue_kind: str  # "seller" | "store"
    discount_pct: float
    paid: float
    best: CardEarn | None
    net_cost: float
    total_savings_pct: float
    notes: list[str] = field(default_factory=list)


def best_card(category: str, spend: float, wallet: list[Card], data: CatalogData, settings: UserSettings) -> CardEarn | None:
    """The card in your wallet that earns the most (in dollars) on `spend` at `category`."""
    ctx = PurchaseContext(category, "giftcard", False, None, settings.today or today_iso())
    best = None
    for card in wallet:
        earn = compute_earn(card, ctx, spend, settings)
        value = earn.points * cpp_for(card.currency, data, settings) / 100
        if best is None or value > best.value:
            best = CardEarn(card.id, card.name, earn.points, earn.rate, value)
    return best


def buy_options(brand: GiftCardBrand, face_value: float, wallet: list[Card], data: CatalogData,
                settings: UserSettings, include_stores: bool = True) -> list[BuyOption]:
    """Every seller of this gift card plus face-value stores, each with your best card, best deal first."""
    out: list[BuyOption] = []
    venues: list[tuple[str, str, float, str, list[str]]] = [
        (s.name, "seller", s.discount_pct, MARKETPLACE_CATEGORY, list(s.notes)) for s in brand.sellers
    ]
    if not venues and brand.discount_pct > 0:  # older snapshots only have the best discount
        venues.append(("Best listed seller", "seller", brand.discount_pct, MARKETPLACE_CATEGORY, []))
    if include_stores:
        venues += [(label, "store", 0.0, cat, ["Face value, if the store sells this brand"]) for cat, label in STORES.items()]
    for name, kind, pct, category, notes in venues:
        paid = face_value * (1 - pct / 100)
        best = best_card(category, paid, wallet, data, settings) if wallet else None
        net = paid - (best.value if best else 0.0)
        out.append(BuyOption(name, kind, pct, round2(paid), best, round2(net),
                             round2((face_value - net) / face_value * 100) if face_value else 0.0, notes))
    # A store only makes sense when your card's bonus there beats buying online.
    sellers_best = max((o.total_savings_pct for o in out if o.venue_kind == "seller"), default=0.0)
    out = [o for o in out if o.venue_kind == "seller" or o.total_savings_pct > sellers_best or not brand.sellers]
    return sorted(out, key=lambda o: o.net_cost)
