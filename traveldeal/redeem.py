"""Points vs cash: what it costs to pay for a booking with points instead of cash.

For an award (e.g. 25,000 Hyatt points + $0) this finds every way you could fund it with
the points your cards earn: the program's own points, a transfer from a bank currency
(Chase, Amex, Capital One, Citi, Bilt), or the bank's travel portal at a fixed value.
Each option is priced at YOUR value for those points, so it can be compared directly
with the effective cost of paying cash (which also earns points).

    cost of a points option = points spent x your cents-per-point + taxes/fees paid in cash
    value you get           = (cash price - taxes/fees) / points spent      (cents per point)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .engine import cpp_for, round2, today_iso
from .models import Card, CatalogData, UserSettings


@dataclass
class RedemptionOption:
    kind: str  # "program" | "transfer" | "portal"
    label: str
    currency_id: str
    currency_name: str
    points: int
    cash: float
    value_cpp: float
    your_cpp: float
    cost: float
    notes: list[str] = field(default_factory=list)

    @property
    def good_value(self) -> bool:
        return self.value_cpp >= self.your_cpp


@dataclass
class CertificateMatch:
    card_name: str
    description: str
    covers: bool | None  # True: award fits under the cap; None: unknown (no award price or category-based)
    saves: float


def _held_currencies(wallet: list[Card]) -> set[str]:
    return {c.currency for c in wallet}


def best_transfer_ratio(from_currency: str, program: str, wallet: list[Card], data: CatalogData, today: str) -> tuple[float, str | None]:
    """Best partner points per bank point you can get, including an active transfer bonus."""
    held = {c.id for c in wallet}
    enabling = set(data.transfers.transfer_cards.get(from_currency, ()))
    if enabling and not (enabling & held):
        return 0.0, None  # e.g. Chase points from a Freedom card alone can't be transferred
    ratios = [t.ratio for t in data.transfers.transfers
              if t.from_currency == from_currency and t.to_program == program and (not t.cards or set(t.cards) & held)]
    if not ratios:
        return 0.0, None
    ratio = max(ratios)
    for b in data.transfers.bonuses:
        if b.from_currency == from_currency and b.to_program == program and today <= b.until:
            return ratio * (1 + b.bonus_pct / 100), f"Includes a {b.bonus_pct:g}% transfer bonus through {b.until}."
    return ratio, None


def redemption_options(
    program_id: str,
    cash_price: float,
    award_points: int,
    award_taxes: float,
    wallet: list[Card],
    data: CatalogData,
    settings: UserSettings,
    portal_cpp_overrides: dict[str, float] | None = None,
) -> list[RedemptionOption]:
    """Every way to pay with points that your wallet supports, cheapest (at your valuations) first."""
    today = settings.today or today_iso()
    out: list[RedemptionOption] = []
    held = _held_currencies(wallet)
    program = data.program(program_id)
    program_currency = data.transfers.program_currencies.get(program_id)
    net = max(0.0, cash_price - award_taxes)

    if program and award_points > 0:
        # 1. The program's own points, earned by a co-brand card you hold.
        if program_currency and program_currency in held:
            your = cpp_for(program_currency, data, settings)
            out.append(RedemptionOption(
                "program", f"Your {program.name} points", program_currency, program.name, award_points, award_taxes,
                round2(net / award_points * 100), your, round2(award_points * your / 100 + award_taxes)))
        # 2. Transfers from bank points.
        for cur in sorted(held):
            ratio, bonus_note = best_transfer_ratio(cur, program_id, wallet, data, today)
            if ratio <= 0:
                continue
            step = data.transfers.increments.get(cur, 1)
            bank_points = math.ceil(award_points / ratio / step) * step
            currency = data.currency(cur)
            your = cpp_for(cur, data, settings)
            notes = [f"{ratio:g} {program.name} points per point transferred."]
            if bonus_note:
                notes.append(bonus_note)
            notes.append("Transfers can't be undone. Confirm award space before you transfer.")
            out.append(RedemptionOption(
                "transfer", f"Transfer {currency.name if currency else cur} to {program.name}", cur,
                currency.name if currency else cur, bank_points, award_taxes,
                round2(net / bank_points * 100) if bank_points else 0.0, your, round2(bank_points * your / 100 + award_taxes), notes))

    # 3. Pay the cash price with points through the bank's travel portal.
    overrides = portal_cpp_overrides or {}
    loyalty_currencies = set(data.transfers.program_currencies.values())
    seen = set()
    for card in wallet:
        cur = card.currency
        # Only bank points pay in a bank's portal; hotel or airline points (e.g. Hilton points on an
        # Amex co-brand card) and cash back don't.
        if not card.portal or cur == "cash_back" or cur in loyalty_currencies or cur in seen:
            continue
        seen.add(cur)
        currency = data.currency(cur)
        portal_cpp = overrides.get(cur) or (currency.cash_cpp if currency else 1.0)
        if portal_cpp <= 0 or cash_price <= 0:
            continue
        points = math.ceil(cash_price / (portal_cpp / 100))
        your = cpp_for(cur, data, settings)
        notes = [f"Portal redemptions are worth about {portal_cpp:g}¢ per point (edit it if your card gets more)."]
        if program and program.kind == "hotel":
            notes.append("Hotel stays booked through a bank portal usually don't earn hotel points or elite benefits.")
        out.append(RedemptionOption(
            "portal", f"Pay with {currency.name if currency else cur} in the portal", cur,
            currency.name if currency else cur, points, 0.0, round2(portal_cpp), your, round2(points * your / 100), notes))

    return sorted(out, key=lambda o: o.cost)


def certificate_matches(program_id: str, cash_price: float, nights: int, award_points: int,
                        wallet: list[Card]) -> list[CertificateMatch]:
    """Free-night certificates from your hotel cards that could cover a night of this stay."""
    nights = max(1, nights or 1)
    per_night_cash = cash_price / nights if cash_price > 0 else 0.0
    per_night_award = award_points / nights if award_points > 0 else 0
    out = []
    for card in wallet:
        for cert in card.free_nights:
            if cert.program != program_id:
                continue
            covers: bool | None = None
            if cert.cap_points and per_night_award:
                covers = per_night_award <= cert.cap_points
            out.append(CertificateMatch(card.name, cert.describe(), covers, round2(per_night_cash) if covers is not False else 0.0))
    return out
