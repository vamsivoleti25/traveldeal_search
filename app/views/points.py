"""Points vs cash: should you pay for this booking with points?"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app import state, theme
from app.booking_form import DEFAULTS, build_booking, direct_price_usd
from traveldeal.catalog import PORTAL_LABELS
from traveldeal.engine import compare_options
from traveldeal.formatting import usd
from traveldeal.redeem import certificate_matches, redemption_options

SS = st.session_state


def _num(col, label, key, default, **kw):
    return col.number_input(label, key=state.persist(key, default), on_change=state.keep, args=(key,), **kw)


def render() -> None:
    cat = state.catalog()
    for k, v in DEFAULTS.items():
        SS.setdefault(k, v)
    theme.page_header("Points vs cash", "Should you use points?",
                      "Enter the award price next to the cash price. Every way your cards can pay with points is priced at "
                      "your own point values and compared with the best way to pay cash.", key="points")
    st.write("")

    my_cards = [c for c in (cat.card(cid) for cid in state.wallet()) if c]
    if not my_cards:
        st.info("Add your cards on the Compare page first.")
        return
    settings = state.settings()

    with st.container(border=True, key="card-points-1"):
        st.subheader("The booking")
        programs = [p for p in cat.loyalty if p.kind in ("hotel", "airline")]
        ids = [p.id for p in programs]
        if SS.f_merchant not in ids:
            SS.f_merchant = ids[0]
        c1, c2, c3 = st.columns(3)
        c1.selectbox("Hotel or airline program", ids, format_func=lambda i: cat.program(i).name,
                     key=state.persist("f_merchant", ids[0]), on_change=state.keep, args=("f_merchant",))
        program = cat.program(SS.f_merchant)
        SS.f_type = "flight" if program.kind == "airline" else "hotel"
        _num(c2, f"Cash price, {SS.get('f_ccy', 'USD')} (direct site)", "f_direct", 420.0, min_value=0.0, step=10.0, format="%.2f",
             help="Shared with the Compare page.")
        if program.kind == "hotel":
            _num(c3, "Nights", "f_nights", 2, min_value=1, max_value=60, step=1)
        a1, a2, _ = st.columns(3)
        _num(a1, f"Award price ({program.name} points, whole stay or trip)", "p_award", 0, min_value=0, step=1000)
        _num(a2, "Taxes and fees on the award ($)", "p_taxes", 0.0, min_value=0.0, step=5.0)
        if program.kind == "hotel" and SS.f_nights >= 5 and program.id in ("marriott", "hilton"):
            st.caption("Marriott and Hilton give the 5th night free on many award stays (Hilton: for elite members). "
                       "Enter the award price you actually see.")
        loyalty_currencies = set(cat.transfers.program_currencies.values())
        portal_currencies = {c.currency: PORTAL_LABELS[c.portal] for c in my_cards
                             if c.portal and c.currency != "cash_back" and c.currency not in loyalty_currencies}
        overrides = {}
        if portal_currencies:
            with st.expander("Portal redemption values"):
                st.caption("Some cards get more than the default per point in their portal (for example points boosts on "
                           "select bookings). Set what you'd actually get.")
                cols = st.columns(max(1, len(portal_currencies)))
                for col, (cur, label) in zip(cols, portal_currencies.items()):
                    c = cat.currency(cur)
                    overrides[cur] = _num(col, f"{label}: ¢ per point", f"p_portal_{cur}", float(c.cash_cpp if c else 1.0),
                                          min_value=0.1, max_value=3.0, step=0.05)

    cash_price = direct_price_usd() if SS.get("f_ccy", "USD") != "USD" else float(SS.f_direct or 0)
    award = int(SS.get("p_award", 0) or 0)
    taxes = float(SS.get("p_taxes", 0) or 0)

    # Best way to pay cash, from the same engine as the Compare page (cash earns points, so it isn't the sticker price).
    portals = list(dict.fromkeys(c.portal for c in my_cards if c.portal))
    booking = build_booking(portals, program.name)
    cash_opts = compare_options(booking, my_cards, cat, settings)
    best_cash = cash_opts[0] if cash_opts else None

    with st.container(border=True, key="card-points-2"):
        if best_cash is None:
            st.info("Enter a cash price to compare.")
            return
        opts = redemption_options(program.id, cash_price, award, taxes, my_cards, cat, settings, overrides)
        st.markdown("##### Verdict")
        best_points = opts[0] if opts else None
        if best_points and best_points.cost < best_cash.effective_cost:
            st.subheader(f"Use points: {best_points.label}")
            st.markdown(theme.md(f"Costs you about **{usd(best_points.cost)}** in point value versus "
                                 f"**{usd(best_cash.effective_cost)}** paying cash ({best_cash.channel_label} with {best_cash.card_name})."))
        elif best_points:
            st.subheader(f"Pay cash: {best_cash.channel_label} with {best_cash.card_name}")
            st.markdown(theme.md(f"Paying cash costs **{usd(best_cash.effective_cost)}** after rewards. The best points option "
                                 f"({best_points.label}) uses about **{usd(best_points.cost)}** of point value. Save your points."))
        else:
            st.subheader(f"Pay cash: {best_cash.channel_label} with {best_cash.card_name}")
            st.write("None of your cards' points can pay for this program. Enter an award price, or add a card that "
                     "earns or transfers to it.")
        m1, m2, m3 = st.columns(3)
        m1.metric("Best cash option", usd(best_cash.effective_cost), help="Effective cost after points, credits and savings.")
        if best_points:
            m2.metric("Best points option", usd(best_points.cost), help="Points at your valuation, plus taxes and fees.")
        if best_cash.credits_applied > 0:
            st.caption(theme.md(f"The cash figure includes {usd(best_cash.credits_applied)} of card credits and savings. If you'd "
                                "rather keep a credit for another trip, mark it used on the Benefits page."))
        if best_points:
            m3.metric("Value per point", f"{best_points.value_cpp:g}¢", delta=f"{best_points.value_cpp - best_points.your_cpp:+.2f}¢ vs your value",
                      delta_color="normal")

        if opts:
            st.dataframe(
                pd.DataFrame([{
                    "Option": o.label,
                    "Points": o.points,
                    "Cash": o.cash,
                    "You get (¢/pt)": o.value_cpp,
                    "Your value (¢/pt)": o.your_cpp,
                    "Real cost": o.cost,
                } for o in opts]),
                hide_index=True, width="stretch",
                column_config={
                    "Points": st.column_config.NumberColumn(format="localized"),
                    "Cash": st.column_config.NumberColumn(format="dollar"),
                    "Real cost": st.column_config.NumberColumn(format="dollar"),
                },
            )
            with st.expander("Notes on each option"):
                for o in opts:
                    st.markdown(f"**{o.label}**" + "".join(f"\n- {n}" for n in o.notes))
        if award == 0 and program:
            st.caption(f"Enter the {program.name} award price to see transfer and program options. Portal options don't need it.")

        certs = certificate_matches(program.id, cash_price, SS.get("f_nights", 1) if program.kind == "hotel" else 1, award, my_cards)
        if certs:
            st.markdown("##### Free-night certificates you hold")
            for m in certs:
                if m.covers is True:
                    st.success(theme.md(f"**{m.card_name}**: {m.description}. Covers a night here, worth about {usd(m.saves)}."))
                elif m.covers is False:
                    st.warning(f"**{m.card_name}**: {m.description}. This hotel costs more points per night than the certificate covers.")
                else:
                    st.info(f"**{m.card_name}**: {m.description}. Check the hotel's category or award price to see if it fits.")
        if cat.transfers.as_of:
            st.caption(f"Transfer partners and ratios checked {cat.transfers.as_of}. Bonuses and partners change; confirm before transferring.")
