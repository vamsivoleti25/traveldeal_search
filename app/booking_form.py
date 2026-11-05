"""Booking form state <-> engine Booking. Shared by the compare page, gift card page and saved trips."""

from __future__ import annotations

import streamlit as st

from traveldeal.catalog import PORTAL_LABELS
from traveldeal.models import Booking, Channel

SS = st.session_state

DEFAULTS = {
    "f_type": "hotel",
    "f_merchant": "marriott",
    "f_direct": 420.0,
    "f_ota": 0.0,
    "f_fhr": False,
    "f_gc_pct": 0.0,
    "f_gc_cat": "grocery",
    "f_perks": 0.0,
    "f_portal_chase_travel": 405.0,
}


def portal_price_key(portal: str) -> str:
    return f"f_portal_{portal}"


def prepaid_key(portal: str) -> str:
    return f"f_prepaid_{portal}"


def build_booking(portals: list[str], merchant_name: str) -> Booking:
    channels: list[Channel] = []
    direct = float(SS.get("f_direct", 0) or 0)
    if direct > 0:
        channels.append(Channel("direct", "direct", f"Direct ({merchant_name})" if merchant_name else "Direct", direct))
    for p in portals:
        price = float(SS.get(portal_price_key(p), 0) or 0)
        if price > 0:
            tags = ("amex_fhr_thc",) if p == "amex_travel" and SS.get("f_fhr") else ()
            channels.append(Channel(p, "portal", PORTAL_LABELS[p], price, portal=p, prepaid=SS.get(prepaid_key(p), True), tags=tags))
    ota = float(SS.get("f_ota", 0) or 0)
    if ota > 0:
        channels.append(Channel("ota", "ota", "Online travel agency", ota))
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
            )
        )
    return Booking(SS.get("f_type", "hotel"), channels, SS.get("f_merchant") or None, float(SS.get("f_perks", 0) or 0))


def load_booking(booking: Booking) -> None:
    """Fill the form from a saved booking."""
    SS.f_type = booking.type
    SS.f_merchant = booking.merchant or ""
    SS.f_perks = booking.direct_perks_value
    SS.f_direct = SS.f_ota = SS.f_gc_pct = 0.0
    SS.f_fhr = False
    for key in [k for k in SS.keys() if str(k).startswith("f_portal_")]:
        SS[key] = 0.0
    for ch in booking.channels:
        if ch.kind == "direct":
            SS.f_direct = ch.price
        elif ch.kind == "ota":
            SS.f_ota = ch.price
        elif ch.kind == "portal" and ch.portal:
            SS[portal_price_key(ch.portal)] = ch.price
            SS[prepaid_key(ch.portal)] = ch.prepaid if ch.prepaid is not None else True
            SS.f_fhr = SS.f_fhr or "amex_fhr_thc" in ch.tags
        elif ch.kind == "giftcard":
            SS.f_gc_pct = ch.gift_card_discount_pct or 0.0
            SS.f_gc_cat = ch.gift_card_purchase_category or "grocery"
