from __future__ import annotations

import pandas as pd
import streamlit as st

from app import state, theme
from app.booking_form import DEFAULTS, build_booking, direct_price_usd, portal_price_key, prepaid_key
from traveldeal.catalog import ISSUER_LABELS, PORTAL_LABELS
from traveldeal.engine import best_per_channel, compare_options
from traveldeal.formatting import usd
from traveldeal.fx import CURRENCIES, usd_rate
from traveldeal.giftcard_buy import best_card
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


WALLET_WIDGET = "_w_wallet"
CREDITS_WIDGET = "_w_apply_credits"
VALUATION_WIDGET = "_w_valuation_mode"


def _on_wallet_change() -> None:
    state.set_wallet(SS[WALLET_WIDGET])


def _on_settings_change() -> None:
    s = state.settings()
    s.apply_credits = bool(SS[CREDITS_WIDGET])
    s.valuation_mode = SS[VALUATION_WIDGET] or s.valuation_mode  # clicking the selected segment deselects it
    state.save_settings(s)


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def _fx(ccy: str) -> tuple[float, str] | None:
    return usd_rate(ccy)


def _num(col, label: str, key: str, default, **kw):
    """A number input that keeps its value when you switch pages."""
    return col.number_input(label, key=state.persist(key, default), on_change=state.keep, args=(key,), **kw)


def _offers_editor(my_cards) -> None:
    """Card-linked offers (Amex Offers, Chase Offers...) for the merchant's own site."""
    by_name = {c.name: c.id for c in my_cards}
    by_id = {v: k for k, v in by_name.items()}
    if "_offers_base" not in SS:  # fixed per session so the editor keeps its identity while you type
        SS._offers_base = pd.DataFrame(
            [{"Card": by_id.get(o["card_id"]), "$ back": o["amount_back"], "Min. spend $": o["min_spend"]} for o in SS.f_offers],
            columns=["Card", "$ back", "Min. spend $"],
        )
    edited = st.data_editor(
        SS._offers_base, key="offers_editor", num_rows="dynamic", hide_index=True, width="stretch",
        column_config={
            "Card": st.column_config.SelectboxColumn("Card", options=list(by_name), required=True),
            "$ back": st.column_config.NumberColumn("$ back", min_value=0, step=5, format="$%d"),
            "Min. spend $": st.column_config.NumberColumn("Min. spend $", min_value=0, step=25, format="$%d"),
        },
    )
    SS.f_offers = [{"card_id": by_name[r["Card"]], "amount_back": float(r["$ back"] or 0), "min_spend": float(r["Min. spend $"] or 0)}
                   for r in edited.to_dict("records") if r.get("Card") in by_name and (r.get("$ back") or 0) > 0]


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

    theme.page_header("Compare", "Compare a booking",
                      "Book direct, through a card portal, or with discounted gift cards? "
                      "Find the cheapest way to pay with the cards you hold.", key="compare")
    st.write("")

    # ---- Wallet
    with st.container(border=True, key="card-compare-1"):
        options = [c.id for c in cat.cards]
        names = {c.id: f"{c.name} · {ISSUER_LABELS[c.issuer]}" for c in cat.cards}
        # A stable key plus an on_change callback. Passing the wallet as `default` with no key
        # gave the widget a new identity every time the wallet changed, so the *next* pick was
        # silently dropped (pick a card, page refreshes, nothing happens, pick it again).
        SS[WALLET_WIDGET] = [c for c in state.wallet() if c in names]
        st.multiselect(
            "Your cards",
            options,
            key=WALLET_WIDGET,
            on_change=_on_wallet_change,
            format_func=names.get,
            placeholder="Search cards, e.g. Sapphire, Amex Gold, Venture X",
        )
        if not user:
            st.caption("You're a guest: create a free account (left sidebar) to keep your cards, settings and saved trips.")

    my_cards = [c for c in (cat.card(cid) for cid in state.wallet()) if c]
    portals = list(dict.fromkeys(c.portal for c in my_cards if c.portal))

    # ---- Trip
    with st.container(border=True, key="card-compare-2"):
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

        if SS.f_type == "flight":
            d1, d2, d3, d4 = st.columns(4)
            _num(d1, "Travelers", "f_travelers", 1, min_value=1, max_value=9, step=1)
            _num(d2, "Checked bags each", "f_bags", 0, min_value=0, max_value=2, step=1)
            d3.selectbox("Trip", [2, 1], format_func={2: "Round trip", 1: "One way"}.get,
                         key=state.persist("f_legs", 2), on_change=state.keep, args=("f_legs",))
            _num(d4, "Bag fee, one way ($)", "f_bag_fee", 40.0, min_value=0.0, step=5.0,
                 help="First checked bag on most U.S. airlines.")
        elif SS.f_type in ("hotel", "vacation_rental"):
            _num(st.columns(4)[0], "Nights", "f_nights", 2, min_value=1, max_value=60, step=1)
        elif SS.f_type == "car_rental":
            r1, r2, _ = st.columns([1, 1, 2])
            _num(r1, "Rental days", "f_rental_days", 0, min_value=0, max_value=60, step=1)
            _num(r2, "Counter collision waiver ($/day)", "f_cdw", 0.0, min_value=0.0, step=5.0,
                 help="What the rental company charges per day for its collision damage waiver (CDW/LDW). "
                      "Cards with primary coverage let you decline it.")

        st.markdown("**Prices you found** · leave a channel at 0 to skip it")
        cols = st.columns(3)
        ccy = SS.get("f_ccy", "USD")
        cols[0].number_input(f"Direct (airline / hotel site), {ccy}", min_value=0.0, step=10.0, format="%.2f",
                             key=state.persist("f_direct", 0.0), on_change=state.keep, args=("f_direct",))
        cols[0].selectbox("Charged in", list(CURRENCIES), format_func=lambda c: f"{c} · {CURRENCIES[c]}",
                          key=state.persist("f_ccy", "USD"), on_change=state.keep, args=("f_ccy",),
                          help="Pick the currency the hotel or airline will charge your card in. "
                               "Cards with a foreign transaction fee add it on top.")
        if SS.get("f_ccy", "USD") != "USD":
            rate = _fx(SS.f_ccy)
            if rate:
                SS.f_fx_rate = rate[0]
                cols[0].caption(f"≈ {usd(direct_price_usd())} at 1 {SS.f_ccy} = ${rate[0]:.4f} (ECB, {rate[1]})")
            else:
                _num(cols[0], f"US$ per 1 {SS.f_ccy}", "f_fx_rate", 1.0, min_value=0.0, step=0.01, format="%.4f",
                     help="Couldn't reach the exchange-rate service; enter the rate yourself.")
        if SS.f_type == "hotel" and SS.f_merchant == "hilton" and any(c.id == "hilton-honors-aspire" for c in my_cards):
            cols[0].checkbox("Participating Hilton resort", key=state.persist("f_hilton_resort", False),
                             on_change=state.keep, args=("f_hilton_resort",), help="For the Aspire card's resort credit.")
        for i, p in enumerate(portals, start=1):
            col = cols[i % 3]
            col.number_input(PORTAL_LABELS[p], min_value=0.0, step=10.0, format="%.2f",
                             key=state.persist(portal_price_key(p), 0.0), on_change=state.keep, args=(portal_price_key(p),))
            if SS.f_type == "hotel":
                col.checkbox("Prepaid rate", key=state.persist(prepaid_key(p), True), on_change=state.keep, args=(prepaid_key(p),))
            if p == "amex_travel" and SS.f_type == "hotel":
                col.checkbox("Fine Hotels + Resorts / Hotel Collection", key=state.persist("f_fhr", False),
                             on_change=state.keep, args=("f_fhr",))
            if p == "chase_travel" and SS.f_type == "hotel" and any(c.id.startswith("chase-sapphire-reserve") for c in my_cards):
                col.checkbox("The Edit hotel (prepaid, 2+ nights)", key=state.persist("f_edit", False),
                             on_change=state.keep, args=("f_edit",))
        cols[(len(portals) + 1) % 3].number_input("Online travel agency (Expedia etc.)", min_value=0.0, step=10.0, format="%.2f",
                                                  key=state.persist("f_ota", 0.0), on_change=state.keep, args=("f_ota",))
        if not portals:
            st.caption("Add a card with a travel portal to compare portal prices.")

        deal = best_gift_card_for(SS.f_merchant)
        if deal and SS.f_gc_pct != deal.discount_pct:
            snap = load_gift_cards()
            d1, d2 = st.columns([4, 1])
            seller = deal.best_seller
            where = f" at {seller.name}" if seller else ""
            buy_with = ""
            if my_cards and direct_price_usd() > 0:
                pick = best_card("other", direct_price_usd() * (1 - deal.discount_pct / 100), my_cards, cat, state.settings())
                if pick:
                    buy_with = f" Buy them with your {pick.card_name} ({pick.rate:g}x)."
            d1.info(theme.md(f"**{deal.name} gift cards** were up to {deal.discount_pct:g}% off{where} on {snap.as_of}.{buy_with} "
                             f"[Check live rate ↗]({deal.live_url})"))
            if d2.button("Add to comparison", key="use_deal"):
                SS.f_gc_pct = deal.discount_pct
                SS.f_gc_cat = "other"
                st.rerun()

        with st.expander("Stack extra savings: shopping portals and card offers",
                         expanded=bool(SS.f_cb_direct or SS.f_cb_ota or SS.f_offers)):
            st.caption("Start the booking from a cashback shopping portal (Rakuten, TopCashback, an airline's shopping mall) "
                       "and you earn its cashback on top of your card's points.")
            x1, x2, _ = st.columns(3)
            _num(x1, "Cashback portal % on the direct site", "f_cb_direct", 0.0, min_value=0.0, max_value=30.0, step=0.5)
            _num(x2, "Cashback portal % on the travel agency", "f_cb_ota", 0.0, min_value=0.0, max_value=30.0, step=0.5)
            st.markdown("**Card-linked offers** · e.g. Amex Offers \"Spend \\$250 at Hilton, get \\$50 back\" (direct bookings)")
            if my_cards:
                _offers_editor(my_cards)
            else:
                st.caption("Add cards first.")

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
    with st.container(border=True, key="card-compare-3"):
        t1, t2 = st.columns([3, 2])
        # Same fix as the card picker: stable keys, values seeded from settings, saved in callbacks.
        SS[CREDITS_WIDGET] = settings.apply_credits
        SS[VALUATION_WIDGET] = settings.valuation_mode
        t1.toggle("Apply my unused card credits to this booking", key=CREDITS_WIDGET, on_change=_on_settings_change)
        t2.segmented_control("Value points at", ["cash", "transfer"], key=VALUATION_WIDGET, on_change=_on_settings_change,
                             format_func={"cash": "Cash value", "transfer": "Transfer partners"}.get)

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
        m3.metric("Rewards + savings", usd(best.total_value))
        if len(per_channel) > 1:
            st.caption(f"Beats {per_channel[1].channel_label} by {usd(per_channel[1].effective_cost - best.effective_cost)}. "
                       "Annual fees are ignored: you pay them either way.")
        _breakdown(best)

        show_all = st.toggle(f"Show all {len(options)} combinations", value=False)
        rows = options if show_all else per_channel
        st.dataframe(
            pd.DataFrame(
                [{"Channel": o.channel_label, "Card": o.card_name, "Charged": o.amount_charged,
                  "Rewards + savings": o.total_value, "Effective cost": o.effective_cost} for o in rows]
            ),
            hide_index=True,
            width="stretch",
            column_config={k: st.column_config.NumberColumn(format="dollar") for k in ("Charged", "Rewards + savings", "Effective cost")},
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
        else:
            st.caption("Create a free account to save this comparison.")
