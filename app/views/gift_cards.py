from __future__ import annotations

import pandas as pd
import streamlit as st

from app.booking_form import DEFAULTS
from app.pages import compare_page
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


def render() -> None:
    snap = load_gift_cards()
    st.title("Gift card deals")
    st.caption(
        "Buy a brand's gift card below face value, then pay for the trip with it. Pay for the gift card with a card that earns "
        "well where you buy it, and you usually still earn the airline or hotel's own points."
    )
    st.info(f"Snapshot from [{snap.source_name}]({snap.source_url}) on {snap.as_of}. {snap.source_note}")

    usable = [b for b in snap.brands if b.category in CATEGORY_TO_BOOKING][:4]
    for col, b in zip(st.columns(len(usable)), usable):
        with col.container(border=True):
            st.metric(b.name, f"{b.discount_pct:g}% off", help=CATEGORY_NAMES[b.category])

    c1, c2 = st.columns([2, 3])
    query = c1.text_input("Search brands", placeholder=f"Search {len(snap.brands)} brands")
    choice = c2.pills("Category", list(FILTERS), default="All travel", label_visibility="hidden") or "All travel"
    rows = [b for b in snap.brands if (query.lower() in b.name.lower() if query else FILTERS[choice](b))]

    st.dataframe(
        pd.DataFrame(
            [{"Brand": b.name, "Type": CATEGORY_NAMES[b.category], "Best discount": b.discount_pct,
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

    usable_rows = [b for b in rows if b.category in CATEGORY_TO_BOOKING]
    if usable_rows:
        u1, u2 = st.columns([3, 1])
        pick = u1.selectbox("Use a gift card in a comparison", usable_rows, format_func=lambda b: f"{b.name} ({b.discount_pct:g}% off)")
        if u2.button("Compare a booking", type="primary", width="stretch"):
            for k, v in DEFAULTS.items():
                SS.setdefault(k, v)
            SS.f_type = CATEGORY_TO_BOOKING[pick.category]
            SS.f_merchant = pick.merchant or ""
            SS.f_gc_pct = pick.discount_pct
            st.switch_page(compare_page())

    with st.expander("How to stack a gift card deal"):
        st.markdown(
            "1. Check the live rate and the seller's guarantee before buying. Discounts move daily and stock sells out.\n"
            "2. Pay for the gift card with a card that earns well *where you buy it*: a 5x office-supply card at Staples, "
            "a 4x grocery card at the supermarket, or your best everyday card online.\n"
            "3. Book directly with the airline or hotel and pay with the gift card. Direct bookings usually still earn loyalty points.\n"
            "4. Confirm the merchant accepts gift cards for that rate type. Some prepaid or third-party rates don't."
        )
