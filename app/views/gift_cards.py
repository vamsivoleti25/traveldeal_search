from __future__ import annotations

import pandas as pd
import streamlit as st

from app import state, theme
from app.booking_form import DEFAULTS
from app.pages import compare_page
from traveldeal.formatting import usd
from traveldeal.giftcard_buy import buy_options
from traveldeal.giftcards import CATEGORY_NAMES, CATEGORY_TO_BOOKING, load_gift_cards

SS = st.session_state
FILTERS = {
    "All travel": lambda b: b.travel,
    "Hotels": lambda b: b.category == "hotel",
    "Airlines": lambda b: b.category == "airline",
    "Cruises": lambda b: b.category == "cruise",
    "Rentals & booking sites": lambda b: b.category in ("vacation_rental", "travel_booking"),
    "Rides & rail": lambda b: b.category in ("rideshare", "rail"),
    "Everyday": lambda b: not b.travel,
}


def _seller_label(b) -> str:
    s = b.best_seller
    return s.name if s else "See live page"


def _buy_smart(snap, rows) -> None:
    """Where to buy the selected gift card, and which of your cards to pay for it with."""
    cat = state.catalog()
    wallet = [c for c in (cat.card(cid) for cid in state.wallet()) if c]
    settings = state.settings()
    with st.container(border=True, key="card-gift-buy"):
        st.subheader("Buy it the smart way")
        st.caption("Each seller's discount plus the points your best card earns on what you pay. "
                   "A store selling the card at face value shows up only when your card's bonus there beats buying online.")
        choices = [b for b in rows if b.sellers] or [b for b in snap.brands if b.sellers]
        if not choices:
            st.caption("No seller details in this snapshot yet.")
            return
        c1, c2 = st.columns([3, 1])
        brand = c1.selectbox("Gift card", choices, key="gc_buy_brand",
                             format_func=lambda b: f"{b.name} · up to {b.discount_pct:g}% off at {_seller_label(b)}")
        face = c2.number_input("Gift card amount ($)", min_value=25.0, max_value=5000.0, value=500.0, step=25.0, key="gc_buy_face")
        if not wallet:
            st.info("Add your cards on the Compare page to see which one to buy with.")
        opts = buy_options(brand, face, wallet, cat, settings)
        if not opts:
            return
        top = opts[0]
        how = f"at **{top.venue}** ({top.discount_pct:g}% off)" if top.venue_kind == "seller" else f"at a **{top.venue.lower()}** (face value)"
        card_part = f" with your **{top.best.card_name}** ({top.best.rate:g}x)" if top.best else ""
        st.markdown(theme.md(f"**Best:** buy {usd(face)} of {brand.name} gift cards {how}{card_part}. "
                             f"You pay {usd(top.paid)}, earn about {usd(top.best.value if top.best else 0)} back in points, "
                             f"**{top.total_savings_pct:.1f}% total savings**."))
        st.dataframe(
            pd.DataFrame([{
                "Where": o.venue,
                "Discount": o.discount_pct,
                "You pay": o.paid,
                "Best card to use": f"{o.best.card_name} ({o.best.rate:g}x)" if o.best else "Add cards",
                "Points value": o.best.value if o.best else 0.0,
                "Net cost": o.net_cost,
                "Total savings": o.total_savings_pct,
                "Notes": "; ".join(o.notes),
            } for o in opts]),
            hide_index=True, width="stretch",
            column_config={
                "Discount": st.column_config.NumberColumn(format="%.1f%%"),
                "You pay": st.column_config.NumberColumn(format="dollar"),
                "Points value": st.column_config.NumberColumn(format="dollar"),
                "Net cost": st.column_config.NumberColumn(format="dollar"),
                "Total savings": st.column_config.ProgressColumn(format="%.1f%%", min_value=0, max_value=30),
            },
        )
        conditional = [s for s in brand.sellers if s.conditional]
        if conditional:
            st.caption("Needs a membership: " + "; ".join(f"{s.name} {s.discount_pct:g}% ({', '.join(s.notes)})" for s in conditional))
        st.caption(theme.md(
            "Online sellers earn your card's everyday rate. Some issuers don't give bonus points on gift card purchases, even at "
            "grocery or office supply stores, so check your card's terms. "
            f"Seller prices from the {snap.as_of} snapshot; [check live rates ↗]({brand.live_url})."))
        if brand.category in CATEGORY_TO_BOOKING and st.button("Use this deal in a comparison", key="gc_buy_compare"):
            for k, v in DEFAULTS.items():
                SS.setdefault(k, v)
            SS.f_type = CATEGORY_TO_BOOKING[brand.category]
            SS.f_merchant = brand.merchant or ""
            best_seller = brand.best_seller
            SS.f_gc_pct = best_seller.discount_pct if best_seller else brand.discount_pct
            SS.f_gc_cat = "other"
            st.switch_page(compare_page())


def render() -> None:
    snap = load_gift_cards()
    theme.page_header(
        "Gift cards", "Gift card deals",
        "Buy a brand's gift card below face value, then pay for the trip with it. See who sells it cheapest and which of "
        "your cards to buy it with.", key="gift-cards",
    )
    st.write("")
    st.info(f"Snapshot from [{snap.source_name}]({snap.source_url}) on {snap.as_of}. {snap.source_note}")

    usable = [b for b in snap.brands if b.category in CATEGORY_TO_BOOKING][:4]
    for i, (col, b) in enumerate(zip(st.columns(len(usable)), usable)):
        with col.container(border=True, key=f"card-gift-{i}"):
            st.metric(b.name, f"{b.discount_pct:g}% off", help=CATEGORY_NAMES[b.category])
            st.caption(f"at {_seller_label(b)}")

    c1, c2 = st.columns([2, 3])
    query = c1.text_input("Search brands", placeholder=f"Search {len(snap.brands)} brands")
    choice = c2.pills("Category", list(FILTERS), default="All travel", label_visibility="hidden") or "All travel"
    rows = [b for b in snap.brands if (query.lower() in b.name.lower() if query else FILTERS[choice](b))]

    st.dataframe(
        pd.DataFrame(
            [{"Brand": b.name, "Type": CATEGORY_NAMES[b.category], "Best discount": b.discount_pct,
              "Best seller": _seller_label(b), "Sellers": len(b.sellers) or None,
              "Save on $500": round(500 * b.discount_pct / 100), "Live rates": b.live_url} for b in rows]
        ),
        hide_index=True,
        width="stretch",
        column_config={
            "Best discount": st.column_config.ProgressColumn(format="%.1f%%", min_value=0, max_value=50),
            "Save on $500": st.column_config.NumberColumn(format="dollar"),
            "Live rates": st.column_config.LinkColumn(display_text="Check live ↗"),
        },
    )

    _buy_smart(snap, rows)

    with st.expander("How to stack a gift card deal"):
        st.markdown(theme.md(
            "1. Check the live rate and the seller's guarantee before buying. Discounts move daily and stock sells out.\n"
            "2. Pay for the gift card with the card the table above recommends: often your best everyday card online, or a "
            "5x office-supply / 4x grocery card when a store sells the brand at face value.\n"
            "3. Book directly with the airline or hotel and pay with the gift card. Direct bookings usually still earn loyalty points.\n"
            "4. Confirm the merchant accepts gift cards for that rate type. Some prepaid or third-party rates don't."
        ))
