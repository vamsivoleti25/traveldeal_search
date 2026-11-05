from __future__ import annotations

import pandas as pd
import streamlit as st

from app import state
from app.booking_form import DEFAULTS, build_booking, portal_price_key, prepaid_key
from traveldeal.catalog import ISSUER_LABELS, PORTAL_LABELS
from traveldeal.engine import best_per_channel, compare_options
from traveldeal.formatting import usd
from traveldeal.giftcards import best_gift_card_for, load_gift_cards
from traveldeal.models import BOOKING_TYPES, Option

SS = st.session_state
TYPE_LABELS = {
    "hotel": "Hotel",
    "flight": "Flight",
    "car_rental": "Rental car",
    "vacation_rental": "Vacation rental",
    "cruise": "Cruise",
    "attraction": "Attraction",
}
GIFT_CATEGORIES = {
    "grocery": "Grocery store",
    "office_supply": "Office supply store",
    "drugstore": "Drugstore",
    "gas": "Gas station",
    "online_retail": "Online retailer",
    "other": "Other / marketplace",
}


def _breakdown(option: Option) -> None:
    rows = [{"Item": li.label, "Amount": usd(li.amount)} for li in option.breakdown]
    rows.append({"Item": "Effective cost", "Amount": usd(option.effective_cost)})
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    for w in option.warnings:
        st.caption(f"⚠️ {w}")


def render() -> None:
    cat = state.catalog()
    user = state.current_user()
    for k, v in DEFAULTS.items():
        SS.setdefault(k, v)

    st.title("Compare a booking")
    st.caption("Book direct, through a card portal, or with discounted gift cards? Find the cheapest way to pay with the cards you hold.")

    # ---- Wallet
    with st.container(border=True):
        options = [c.id for c in cat.cards]
        names = {c.id: f"{c.name} · {ISSUER_LABELS[c.issuer]}" for c in cat.cards}
        chosen = st.multiselect(
            "Your cards",
            options,
            default=[c for c in state.wallet() if c in names],
            format_func=names.get,
            placeholder="Search cards, e.g. Sapphire, Amex Gold, Venture X",
        )
        if chosen != state.wallet():
            state.set_wallet(chosen)
        if not user:
            st.caption("Sign in (top right) to keep your cards, settings and saved trips across devices.")

    my_cards = [c for c in (cat.card(cid) for cid in state.wallet()) if c]
    portals = list(dict.fromkeys(c.portal for c in my_cards if c.portal))

    # ---- Trip
    with st.container(border=True):
        st.subheader("Your trip")
        c1, c2 = st.columns(2)
        c1.selectbox("What are you booking?", BOOKING_TYPES, format_func=TYPE_LABELS.get,
                     key=state.persist("f_type", "hotel"), on_change=state.keep, args=("f_type",))
        kind = {"flight": "airline", "hotel": "hotel"}.get(SS.f_type)
        programs = [p for p in cat.loyalty if p.kind == kind] if kind else []
        ids = [""] + [p.id for p in programs]
        if SS.f_merchant not in ids:
            SS.f_merchant = ""
        c2.selectbox({"airline": "Airline", "hotel": "Hotel brand"}.get(kind or "", "Merchant"), ids,
                     format_func=lambda i: next((p.name for p in programs if p.id == i), "Other / independent"),
                     key=state.persist("f_merchant", ""), on_change=state.keep, args=("f_merchant",), disabled=not kind)

        st.markdown("**Prices you found** · leave a channel at 0 to skip it")
        cols = st.columns(3)
        cols[0].number_input("Direct (airline / hotel site)", min_value=0.0, step=10.0, format="%.2f",
                             key=state.persist("f_direct", 0.0), on_change=state.keep, args=("f_direct",))
        for i, p in enumerate(portals, start=1):
            col = cols[i % 3]
            col.number_input(PORTAL_LABELS[p], min_value=0.0, step=10.0, format="%.2f",
                             key=state.persist(portal_price_key(p), 0.0), on_change=state.keep, args=(portal_price_key(p),))
            if SS.f_type == "hotel":
                col.checkbox("Prepaid rate", key=state.persist(prepaid_key(p), True), on_change=state.keep, args=(prepaid_key(p),))
            if p == "amex_travel" and SS.f_type == "hotel":
                col.checkbox("Fine Hotels + Resorts / Hotel Collection", key=state.persist("f_fhr", False),
                             on_change=state.keep, args=("f_fhr",))
        cols[(len(portals) + 1) % 3].number_input("Online travel agency (Expedia etc.)", min_value=0.0, step=10.0, format="%.2f",
                                                  key=state.persist("f_ota", 0.0), on_change=state.keep, args=("f_ota",))
        if not portals:
            st.caption("Add a card with a travel portal to compare portal prices.")

        deal = best_gift_card_for(SS.f_merchant)
        if deal and SS.f_gc_pct != deal.discount_pct:
            snap = load_gift_cards()
            d1, d2 = st.columns([4, 1])
            d1.info(f"**{deal.name} gift cards** were up to {deal.discount_pct:g}% off on {snap.as_of}. [Check live rate ↗]({deal.live_url})")
            if d2.button("Add to comparison", key="use_deal"):
                SS.f_gc_pct = deal.discount_pct
                st.rerun()

        with st.expander("Gift cards and elite perks", expanded=SS.f_gc_pct > 0):
            g1, g2, g3 = st.columns(3)
            g1.number_input("Gift card discount (%)", min_value=0.0, max_value=50.0, step=0.5,
                            key=state.persist("f_gc_pct", 0.0), on_change=state.keep, args=("f_gc_pct",))
            g2.selectbox("Where you'd buy the gift card", list(GIFT_CATEGORIES), format_func=GIFT_CATEGORIES.get,
                         key=state.persist("f_gc_cat", "grocery"), on_change=state.keep, args=("f_gc_cat",))
            g3.number_input("Value of elite perks when booking direct ($)", min_value=0.0, step=5.0,
                            key=state.persist("f_perks", 0.0), on_change=state.keep, args=("f_perks",),
                            help="Breakfast, upgrade, late checkout: your own estimate.")

    # ---- Results
    settings = state.settings()
    with st.container(border=True):
        t1, t2 = st.columns([3, 2])
        apply = t1.toggle("Apply my unused card credits to this booking", value=settings.apply_credits)
        mode = t2.segmented_control("Value points at", ["cash", "transfer"], default=settings.valuation_mode,
                                    format_func={"cash": "Cash value", "transfer": "Transfer partners"}.get)
        if apply != settings.apply_credits or (mode and mode != settings.valuation_mode):
            settings.apply_credits = apply
            settings.valuation_mode = mode or settings.valuation_mode
            state.save_settings(settings)

        merchant_name = cat.program(SS.f_merchant).name if cat.program(SS.f_merchant) else ""
        booking = build_booking(portals, merchant_name)
        options = compare_options(booking, my_cards, cat, settings)
        if not options:
            st.info("Add at least one card and one price to see a recommendation.")
            return

        best = options[0]
        per_channel = best_per_channel(options)
        st.markdown("##### Best option")
        st.subheader(f"{best.channel_label} with {best.card_name}")
        m1, m2, m3 = st.columns(3)
        m1.metric("Effective cost", usd(best.effective_cost))
        m2.metric("You pay", usd(best.amount_charged))
        m3.metric("Rewards + credits", usd(best.total_value))
        if len(per_channel) > 1:
            st.caption(f"Beats {per_channel[1].channel_label} by {usd(per_channel[1].effective_cost - best.effective_cost)}. "
                       "Annual fees are ignored: you pay them either way.")
        _breakdown(best)

        show_all = st.toggle(f"Show all {len(options)} combinations", value=False)
        rows = options if show_all else per_channel
        st.dataframe(
            pd.DataFrame(
                [{"Channel": o.channel_label, "Card": o.card_name, "Charged": o.amount_charged,
                  "Rewards + credits": o.total_value, "Effective cost": o.effective_cost} for o in rows]
            ),
            hide_index=True,
            width="stretch",
            column_config={k: st.column_config.NumberColumn(format="dollar") for k in ("Charged", "Rewards + credits", "Effective cost")},
        )
        with st.expander("Breakdown for every option"):
            for o in rows:
                st.markdown(f"**{o.channel_label} · {o.card_name}**")
                _breakdown(o)

        if user:
            s1, s2 = st.columns([3, 1])
            name = s1.text_input("Save this comparison as", placeholder="e.g. Maui, Jan 2027", label_visibility="collapsed")
            if s2.button("Save trip", type="primary", width="stretch"):
                try:
                    state.repository().save_comparison(
                        user["id"], name or f"{TYPE_LABELS[booking.type]} comparison", booking,
                        f"{best.channel_label} with {best.card_name}", best.effective_cost,
                    )
                    st.toast("Saved to your account.")
                except ValueError as e:
                    st.error(str(e))
        elif state.auth_configured():
            st.caption("Sign in to save this comparison.")
