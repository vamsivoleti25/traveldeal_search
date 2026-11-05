"""Booking form state <-> engine Booking. Shared by the compare page, points page, gift card page and saved trips."""

from __future__ import annotations

import streamlit as st

from traveldeal.catalog import PORTAL_LABELS
from traveldeal.models import Booking, CardOffer, Channel

SS = st.session_state

DEFAULTS = {
    "f_type": "hotel",
    "f_merchant": "marriott",
    "f_direct": 420.0,
    "f_ota": 0.0,
    "f_fhr": False,
    "f_edit": False,
    "f_hilton_resort": False,
    "f_gc_pct": 0.0,
    "f_gc_cat": "grocery",
    "f_perks": 0.0,
    "f_portal_chase_travel": 405.0,
    # stacking extras
    "f_cb_direct": 0.0,
    "f_cb_ota": 0.0,
    "f_ccy": "USD",
    "f_fx_rate": 1.0,
    "f_offers": [],
    # trip details
    "f_nights": 2,
    "f_travelers": 1,
    "f_bags": 0,
    "f_bag_fee": 40.0,
    "f_legs": 2,
    "f_rental_days": 0,
    "f_cdw": 0.0,
}


def portal_price_key(portal: str) -> str:
    return f"f_portal_{portal}"


def prepaid_key(portal: str) -> str:
    return f"f_prepaid_{portal}"


def direct_price_usd() -> float:
    """The direct price in dollars (it's entered in the hotel or airline's currency)."""
    amount = float(SS.get("f_direct", 0) or 0)
    return amount * float(SS.get("f_fx_rate", 1.0) or 1.0) if SS.get("f_ccy", "USD") != "USD" else amount


def build_booking(portals: list[str], merchant_name: str) -> Booking:
    channels: list[Channel] = []
    btype = SS.get("f_type", "hotel")
    merchant = SS.get("f_merchant") or None
    ccy = SS.get("f_ccy", "USD")
    foreign = ccy if ccy != "USD" else None
    direct = round(direct_price_usd(), 2)
    if direct > 0:
        tags = ("hilton_resort",) if btype == "hotel" and merchant == "hilton" and SS.get("f_hilton_resort") else ()
        channels.append(Channel("direct", "direct", f"Direct ({merchant_name})" if merchant_name else "Direct", direct,
                                tags=tags, cashback_pct=float(SS.get("f_cb_direct", 0) or 0),
                                foreign_currency=foreign, foreign_price=float(SS.get("f_direct", 0) or 0) if foreign else None))
    for p in portals:
        price = float(SS.get(portal_price_key(p), 0) or 0)
        if price > 0:
            tags = ()
            if p == "amex_travel" and SS.get("f_fhr"):
                tags = ("amex_fhr_thc",)
            if p == "chase_travel" and btype == "hotel" and SS.get("f_edit"):
                tags = ("chase_edit",)
            channels.append(Channel(p, "portal", PORTAL_LABELS[p], price, portal=p, prepaid=SS.get(prepaid_key(p), True), tags=tags))
    ota = float(SS.get("f_ota", 0) or 0)
    if ota > 0:
        channels.append(Channel("ota", "ota", "Online travel agency", ota, cashback_pct=float(SS.get("f_cb_ota", 0) or 0)))
    pct = float(SS.get("f_gc_pct", 0) or 0)
    if pct > 0 and direct > 0:
        channels.append(
            Channel(
                "giftcard",
                "giftcard",
                f"Direct, paid with {merchant_name or 'merchant'} gift cards",
                direct,
                gift_card_discount_pct=pct,
                gift_card_purchase_category=SS.get("f_gc_cat", "grocery"),
                foreign_currency=foreign,
            )
        )
    offers = [CardOffer(o["card_id"], float(o.get("amount_back") or 0), float(o.get("min_spend") or 0))
              for o in SS.get("f_offers", []) if o.get("card_id") and (o.get("amount_back") or 0) > 0]
    return Booking(
        btype, channels, merchant, float(SS.get("f_perks", 0) or 0),
        offers=offers,
        nights=int(SS.get("f_nights", 1) or 1) if btype in ("hotel", "vacation_rental") else 1,
        travelers=int(SS.get("f_travelers", 1) or 1),
        checked_bags=int(SS.get("f_bags", 0) or 0) if btype == "flight" else 0,
        bag_fee=float(SS.get("f_bag_fee", 40) or 0),
        flight_legs=int(SS.get("f_legs", 2) or 2),
        rental_days=int(SS.get("f_rental_days", 0) or 0) if btype == "car_rental" else 0,
        rental_cdw_per_day=float(SS.get("f_cdw", 0) or 0),
    )


def load_booking(booking: Booking) -> None:
    """Fill the form from a saved booking."""
    SS.f_type = booking.type
    SS.f_merchant = booking.merchant or ""
    SS.f_perks = booking.direct_perks_value
    SS.f_direct = SS.f_ota = SS.f_gc_pct = SS.f_cb_direct = SS.f_cb_ota = 0.0
    SS.f_fhr = SS.f_edit = SS.f_hilton_resort = False
    SS.f_ccy, SS.f_fx_rate = "USD", 1.0
    for key in [k for k in SS.keys() if str(k).startswith("f_portal_")]:
        SS[key] = 0.0
    for ch in booking.channels:
        if ch.kind == "direct":
            if ch.foreign_currency and ch.foreign_price:
                SS.f_ccy, SS.f_direct = ch.foreign_currency, ch.foreign_price
                SS.f_fx_rate = ch.price / ch.foreign_price if ch.foreign_price else 1.0
            else:
                SS.f_direct = ch.price
            SS.f_cb_direct = ch.cashback_pct or 0.0
            SS.f_hilton_resort = "hilton_resort" in ch.tags
        elif ch.kind == "ota":
            SS.f_ota = ch.price
            SS.f_cb_ota = ch.cashback_pct or 0.0
        elif ch.kind == "portal" and ch.portal:
            SS[portal_price_key(ch.portal)] = ch.price
            SS[prepaid_key(ch.portal)] = ch.prepaid if ch.prepaid is not None else True
            SS.f_fhr = SS.f_fhr or "amex_fhr_thc" in ch.tags
            SS.f_edit = SS.f_edit or "chase_edit" in ch.tags
        elif ch.kind == "giftcard":
            SS.f_gc_pct = ch.gift_card_discount_pct or 0.0
            SS.f_gc_cat = ch.gift_card_purchase_category or "grocery"
    SS.pop("_offers_base", None)
    SS.f_offers = [{"card_id": o.card_id, "amount_back": o.amount_back, "min_spend": o.min_spend} for o in booking.offers]
    SS.f_nights, SS.f_travelers, SS.f_bags = booking.nights, booking.travelers, booking.checked_bags
    SS.f_bag_fee, SS.f_legs = booking.bag_fee, booking.flight_legs
    SS.f_rental_days, SS.f_cdw = booking.rental_days, booking.rental_cdw_per_day
