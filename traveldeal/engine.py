"""The comparison engine. Pure functions only: same inputs always give the same output.

For every (booking channel x card you hold) pair it computes

    effective cost = amount charged
                     + foreign transaction fee (foreign-currency charges)
                     - statement credits and card-linked offers
                     - shopping-portal cashback
                     - value of card points earned
                     - value of airline/hotel loyalty points earned
                     - value of elite perks (direct bookings)
                     - checked bags and rental-car waiver you don't have to buy

and ranks the options from cheapest to most expensive.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from .models import (
    TRAVEL_TYPES,
    Booking,
    Card,
    CardOffer,
    CatalogData,
    Channel,
    Credit,
    EarnRule,
    LineItem,
    LoyaltyProgram,
    Option,
    UserSettings,
)

CAP_PERIOD_LABEL = {
    "billing_cycle": "billing-cycle",
    "month": "monthly",
    "quarter": "quarterly",
    "calendar_year": "annual",
    "anniversary_year": "annual",
}


def round2(n: float) -> float:
    return round(n + 0.0, 2)


def today_iso() -> str:
    return date.today().isoformat()


def category_matches(rule_categories: tuple[str, ...], category: str) -> bool:
    if category in rule_categories or "everything" in rule_categories:
        return True
    return "travel" in rule_categories and category in TRAVEL_TYPES


def _effective_kind(kind: str) -> str:
    """Gift card purchases happen at a store, so they match like a direct purchase."""
    return "direct" if kind == "giftcard" else kind


def channel_matches(spec: str | tuple[str, ...], kind: str) -> bool:
    k = _effective_kind(kind)
    if spec == "any":
        return True
    return k in spec if isinstance(spec, tuple) else spec == k


def card_can_use_channel(card: Card, channel: Channel) -> bool:
    """A portal channel can only be paid with a card from that portal's issuer."""
    if channel.kind != "portal":
        return True
    return card.portal is not None and card.portal == channel.portal


def rule_is_active(rule: EarnRule, today: str) -> bool:
    if rule.valid_from and today < rule.valid_from:
        return False
    if rule.valid_until and today > rule.valid_until:
        return False
    return True


@dataclass
class PurchaseContext:
    category: str
    kind: str
    prepaid: bool = False
    merchant: str | None = None
    today: str = field(default_factory=today_iso)
    nights: int = 1


def purchase_context(booking: Booking, channel: Channel, today: str) -> PurchaseContext:
    if channel.kind == "giftcard":
        # The card is charged when you buy the gift card, e.g. at a grocery store.
        return PurchaseContext(channel.gift_card_purchase_category or "other", "giftcard", False, None, today)
    prepaid = channel.prepaid if channel.prepaid is not None else channel.kind == "portal"
    return PurchaseContext(booking.type, channel.kind, prepaid, booking.merchant, today, max(1, booking.nights or 1))


def rule_applies(rule: EarnRule, ctx: PurchaseContext) -> bool:
    return (
        category_matches(rule.categories, ctx.category)
        and channel_matches(rule.channel, ctx.kind)
        and not (rule.prepaid_only and not ctx.prepaid)
        and not (rule.merchant and rule.merchant != ctx.merchant)
        and rule_is_active(rule, ctx.today)
    )


@dataclass
class EarnResult:
    points: float
    rate: float
    rule: EarnRule | None = None
    notes: list[str] = field(default_factory=list)


def compute_earn(card: Card, ctx: PurchaseContext, spend: float, settings: UserSettings) -> EarnResult:
    """Points earned by `card` on `spend` dollars, honoring caps, dates and conditions."""
    matches = sorted(
        ((i, r) for i, r in enumerate(card.earn) if rule_applies(r, ctx)),
        key=lambda item: item[1].rate,
        reverse=True,
    )
    if not matches or matches[0][1].rate <= card.base_rate:
        return EarnResult(spend * card.base_rate, card.base_rate)

    index, rule = matches[0]
    notes: list[str] = []
    if rule.condition:
        notes.append(f"{card.name} {rule.rate:g}x assumes: {rule.condition}")
    if rule.valid_until:
        notes.append(f"{card.name} {rule.rate:g}x is limited-time, through {rule.valid_until}.")
    if rule.cap is None:
        return EarnResult(spend * rule.rate, rule.rate, rule, notes)

    used = settings.cap_spend_used.get(f"{card.id}:{index}", 0.0)
    remaining = max(0.0, rule.cap - used)
    at_bonus = min(spend, remaining)
    overflow = spend - at_bonus
    points = at_bonus * rule.rate + overflow * card.base_rate
    if overflow > 0:
        period = CAP_PERIOD_LABEL.get(rule.cap_period or "calendar_year", "annual")
        notes.append(f"${round2(overflow):g} is over the {rule.rate:g}x {period} cap and earns {card.base_rate:g}x.")
    return EarnResult(points, points / spend if spend > 0 else rule.rate, rule, notes)


def credit_applies(credit: Credit, ctx: PurchaseContext, channel: Channel) -> bool:
    if not category_matches(credit.categories, ctx.category):
        return False
    if not channel_matches(credit.channel, ctx.kind):
        return False
    if credit.requires_tag and credit.requires_tag not in channel.tags:
        return False
    if credit.min_spend is not None and channel.price < credit.min_spend:
        return False
    if credit.merchant and credit.merchant != ctx.merchant:
        return False
    if credit.min_nights and ctx.nights < credit.min_nights:
        return False
    return True


@dataclass
class CreditResult:
    applied: float = 0.0
    non_earning: float = 0.0
    items: list[LineItem] = field(default_factory=list)
    used_credits: list[Credit] = field(default_factory=list)


def compute_credits(card: Card, ctx: PurchaseContext, channel: Channel, charged: float, settings: UserSettings) -> CreditResult:
    result = CreditResult()
    for credit in card.credits:
        if not credit_applies(credit, ctx, channel):
            continue
        used = settings.credits_used.get(f"{card.id}:{credit.id}", 0.0)
        amount = min(max(0.0, credit.amount - used), charged - result.applied)
        if credit.max_per_booking is not None:
            amount = min(amount, credit.max_per_booking)
        if amount <= 0:
            continue
        result.applied += amount
        if not credit.credited_amount_earns_points:
            result.non_earning += amount
        result.items.append(LineItem(credit.name, -round2(amount)))
        result.used_credits.append(credit)
    return result


def cpp_for(currency_id: str, data: CatalogData, settings: UserSettings) -> float:
    if currency_id in settings.cpp_overrides:
        return float(settings.cpp_overrides[currency_id])
    currency = next((c for c in data.currencies if c.id == currency_id), None)
    if currency is None:
        return 1.0
    return currency.transfer_cpp if settings.valuation_mode == "transfer" else currency.cash_cpp


@dataclass
class LoyaltyResult:
    points: int = 0
    value: float = 0.0
    perks: float = 0.0
    warnings: list[str] = field(default_factory=list)


def compute_loyalty(booking: Booking, channel: Channel, program: LoyaltyProgram | None, settings: UserSettings) -> LoyaltyResult:
    first_party = channel.kind in ("direct", "giftcard")
    perks_value = booking.direct_perks_value or 0.0
    if program is None:
        return LoyaltyResult(perks=perks_value if first_party else 0.0)

    earns = first_party or program.earns_on_third_party_bookings
    perks_apply = first_party or program.elite_perks_on_third_party_bookings
    warnings = []
    if not earns:
        warnings.append(f"Third-party bookings usually don't earn {program.name} points or elite credit.")
    if not perks_apply and perks_value > 0:
        warnings.append(f"Elite perks usually don't apply when booked outside {program.name}.")

    status = settings.elite_status.get(program.id, "member")
    bonus = program.elite_bonus.get(status, 0.0)
    points = channel.price * program.points_per_dollar * (1 + bonus) if earns else 0.0
    cpp = settings.loyalty_cpp_overrides.get(program.id, program.default_cpp)
    return LoyaltyResult(round(points), points * cpp / 100, perks_value if perks_apply else 0.0, warnings)


# ---------------------------------------------------------------- extras that stack on a booking
def foreign_fee(card: Card, channel: Channel, charged: float) -> tuple[float, str | None]:
    """Fee for a charge in a foreign currency. Returns (fee, warning)."""
    if not channel.foreign_currency or channel.kind not in ("direct", "ota"):
        return 0.0, None
    if card.foreign_transaction_fee is None:
        return 0.0, f"Check {card.name}'s foreign transaction fee before paying in {channel.foreign_currency}."
    return charged * card.foreign_transaction_fee / 100, None


def offer_value(card: Card, channel: Channel, offers: list[CardOffer], charged: float) -> list[LineItem]:
    """Card-linked offers (Amex Offers, Chase Offers...) are for the merchant's own site."""
    if channel.kind != "direct":
        return []
    items = []
    for o in offers:
        if o.card_id == card.id and o.amount_back > 0 and charged >= (o.min_spend or 0):
            items.append(LineItem(f"Card offer: ${o.amount_back:g} back" + (f" on ${o.min_spend:g}+" if o.min_spend else ""),
                                  -round2(min(o.amount_back, charged))))
    return items


def bag_savings(booking: Booking, channel: Channel, card: Card, wallet: list[Card]) -> tuple[float, str | None]:
    """Free checked bags from an airline card. Cards that need the ticket bought with them only count
    when this option pays with that card on the airline's own site."""
    if booking.type != "flight" or not booking.merchant or booking.checked_bags <= 0 or booking.bag_fee <= 0:
        return 0.0, None
    best, label = 0.0, None
    for held in wallet:
        b = held.checked_bags
        if b is None or b.program != booking.merchant:
            continue
        if b.requires_purchase_with_card and (held.id != card.id or channel.kind != "direct"):
            continue
        people = min(max(1, booking.travelers), 1 + b.companions)
        bags = min(booking.checked_bags, b.bags)
        # A second free bag is usually priced higher than the first; we value every bag at the first-bag fee.
        saved = people * bags * booking.bag_fee * max(1, booking.flight_legs)
        if saved > best:
            best, label = saved, f"Free checked bags with {held.name} ({people} traveler{'s' if people > 1 else ''})"
    return best, label


def rental_waiver_savings(booking: Booking, card: Card) -> tuple[float, str | None, str | None]:
    """Primary rental coverage lets you decline the counter's collision damage waiver."""
    if booking.type != "car_rental" or booking.rental_days <= 0 or booking.rental_cdw_per_day <= 0:
        return 0.0, None, None
    cov = card.rental_coverage
    if cov is None or cov.type != "primary":
        return 0.0, None, None
    warning = None
    limit = cov.max_days_home
    if limit and booking.rental_days > limit:
        warning = (f"{card.name} covers rentals up to {limit} days at home"
                   + (f" ({cov.max_days_abroad} abroad)" if cov.max_days_abroad and cov.max_days_abroad != limit else "")
                   + "; longer rentals aren't covered.")
        return 0.0, None, warning
    return booking.rental_days * booking.rental_cdw_per_day, f"Skip the counter's collision waiver ({card.name} primary coverage)", warning


def evaluate(booking: Booking, channel: Channel, card: Card, data: CatalogData, settings: UserSettings,
             wallet: list[Card] | None = None) -> Option:
    """Evaluate one channel paid with one card. `wallet` is every card held (for benefits like free bags)."""
    wallet = wallet if wallet is not None else [card]
    ctx = purchase_context(booking, channel, settings.today or today_iso())
    warnings: list[str] = []
    price_label = f"{channel.label} price"
    if channel.foreign_currency and channel.foreign_price:
        price_label += f" ({channel.foreign_price:,.2f} {channel.foreign_currency})"
    breakdown: list[LineItem] = [LineItem(price_label, round2(channel.price))]

    discount = (channel.gift_card_discount_pct or 0) / 100 if channel.kind == "giftcard" else 0.0
    charged = channel.price * (1 - discount)
    if discount > 0:
        breakdown.append(LineItem(f"Gift card discount ({channel.gift_card_discount_pct:g}%)", -round2(channel.price - charged)))

    credits = (
        CreditResult() if not settings.apply_credits else compute_credits(card, ctx, channel, charged, settings)
    )
    breakdown.extend(credits.items)
    fee, fee_warning = foreign_fee(card, channel, charged)
    if fee > 0:
        breakdown.append(LineItem(f"Foreign transaction fee ({card.foreign_transaction_fee:g}%)", round2(fee)))
    if fee_warning:
        warnings.append(fee_warning)
    offers = offer_value(card, channel, booking.offers, charged - credits.applied)
    breakdown.extend(offers)
    offers_total = -sum(i.amount for i in offers)
    cashback = channel.price * (channel.cashback_pct or 0) / 100 if channel.kind in ("direct", "ota") else 0.0
    if cashback > 0:
        breakdown.append(LineItem(f"Shopping portal cashback ({channel.cashback_pct:g}%)", -round2(cashback)))
        warnings.append("Shopping portals usually pay on the pre-tax price and take weeks to post; "
                        "start the booking from the portal's link.")
    for credit in credits.used_credits:
        if credit.channel == "any":
            warnings.append(
                f"{credit.name} works on any travel. If you'd use it elsewhere anyway, mark it as used "
                "in Settings so it doesn't skew this comparison."
            )

    earning_spend = max(0.0, charged - credits.non_earning)
    earn = compute_earn(card, ctx, earning_spend, settings)
    warnings.extend(earn.notes)
    cpp = cpp_for(card.currency, data, settings)
    card_points_value = earn.points * cpp / 100
    breakdown.append(
        LineItem(f"{card.name}: {round(earn.points):,} pts at {cpp:g}¢ ({round2(earn.rate):g}x)", -round2(card_points_value))
    )

    program = data.program(booking.merchant)
    loyalty = compute_loyalty(booking, channel, program, settings)
    warnings.extend(loyalty.warnings)
    if program and loyalty.points > 0:
        breakdown.append(LineItem(f"{program.name}: ~{loyalty.points:,} pts", -round2(loyalty.value)))
    if loyalty.perks > 0:
        breakdown.append(LineItem("Elite perks (your estimate)", -round2(loyalty.perks)))

    bags, bags_label = bag_savings(booking, channel, card, wallet)
    if bags > 0:
        breakdown.append(LineItem(bags_label, -round2(bags)))
    waiver, waiver_label, waiver_warning = rental_waiver_savings(booking, card)
    if waiver > 0:
        breakdown.append(LineItem(waiver_label, -round2(waiver)))
    if waiver_warning:
        warnings.append(waiver_warning)

    if channel.kind == "giftcard":
        warnings.append(
            "Confirm the merchant accepts gift cards for this booking. Some issuers exclude gift card purchases from bonus categories."
        )
    if card.needs_verification:
        warnings.append(f"{card.name} terms have not been verified yet.")

    effective = (charged + fee - credits.applied - offers_total - cashback - card_points_value
                 - loyalty.value - loyalty.perks - bags - waiver)
    sticker_prices = [c.price for c in booking.channels if c.kind != "giftcard" and c.price > 0] + [channel.price]
    baseline = min(sticker_prices)
    return Option(
        channel_id=channel.id,
        channel_label=channel.label,
        channel_kind=channel.kind,
        card_id=card.id,
        card_name=card.name,
        amount_charged=round2(charged),
        card_points=round(earn.points),
        card_currency=card.currency,
        card_points_value=round2(card_points_value),
        credits_applied=round2(credits.applied + offers_total + cashback + bags + waiver - fee),
        loyalty_points=loyalty.points,
        loyalty_value=round2(loyalty.value),
        perks_value=round2(loyalty.perks),
        effective_cost=round2(effective),
        return_pct=round2((baseline - effective) / baseline * 100) if baseline > 0 else 0.0,
        breakdown=breakdown,
        warnings=warnings,
    )


def compare_options(booking: Booking, cards: list[Card], data: CatalogData, settings: UserSettings) -> list[Option]:
    """Every (channel x card) combination the user can actually book, cheapest first."""
    options = [
        evaluate(booking, channel, card, data, settings, wallet=cards)
        for channel in booking.channels
        if channel.price > 0
        for card in cards
        if card_can_use_channel(card, channel)
    ]
    return sorted(options, key=lambda o: (o.effective_cost, -o.card_points_value))


def best_per_channel(options: list[Option]) -> list[Option]:
    seen: set[str] = set()
    out = []
    for o in options:
        if o.channel_id not in seen:
            seen.add(o.channel_id)
            out.append(o)
    return out
