"""My benefits: credits left to use and when they reset, free nights, bags, rental cover, foreign fees."""

from __future__ import annotations

import calendar
from datetime import date

import streamlit as st

from app import state, theme
from traveldeal.benefits import PERIOD_LABELS, credit_statuses
from traveldeal.formatting import usd

SS = st.session_state
MONTHS = [0] + list(range(1, 13))


def _program_name(cat, pid: str) -> str:
    p = cat.program(pid)
    return p.name if p else pid.replace("_", " ").title()


def render() -> None:
    cat = state.catalog()
    theme.page_header("Benefits", "Your card benefits",
                      "Credits left to use before they reset, free nights you've earned, and which card to reach for "
                      "with bags, rental cars and foreign currency.", key="benefits")
    st.write("")
    cards = [c for c in (cat.card(cid) for cid in state.wallet()) if c]
    if not cards:
        st.info("Add your cards on the Compare page first.")
        return
    settings = state.settings()
    today = date.fromisoformat(settings.today) if settings.today else date.today()
    statuses = credit_statuses(cards, settings, today)

    # ---- Summary
    unused = [s for s in statuses if s.remaining > 0]
    m1, m2, m3 = st.columns(3)
    m1.metric("Unused credits", usd(sum(s.remaining for s in unused)), help="Across every card in your wallet.")
    soon = next((s for s in unused if s.days_left is not None), None)
    m2.metric("Next to reset", f"{soon.days_left} days" if soon else "—",
              help=f"{soon.credit.name} on {soon.card.name}" if soon else None)
    m3.metric("Free-night certificates", sum(len(c.free_nights) for c in cards), help="Annual and spend-based.")

    # ---- Credits tracker
    with st.container(border=True, key="card-benefits-1"):
        st.subheader("Statement credits")
        if not statuses:
            st.caption("None of your cards have booking-related credits we track.")
        else:
            with st.form("credits_tracker", border=False):
                used_inputs, months = {}, {}
                for s in statuses:
                    a, b, c = st.columns([3, 1.2, 1.4], vertical_alignment="center")
                    resets = (f"resets in **{s.days_left} days** ({s.resets:%b %d})" if s.resets
                              else "set your card's anniversary month below")
                    a.markdown(theme.md(f"**{s.credit.name}** · {s.card.name}  \n"
                                        f"{usd(s.credit.amount)} {PERIOD_LABELS.get(s.credit.period, s.credit.period)} · {resets}"))
                    used_inputs[s.key] = b.number_input("Used so far", min_value=0.0, max_value=float(s.credit.amount),
                                                        value=float(s.used), step=10.0, key=f"bt_used_{s.key}")
                    c.progress(s.used / s.credit.amount if s.credit.amount else 0.0,
                               text=f"{usd(s.remaining)} left" if s.remaining > 0 else "Used up")
                anniversary_cards = sorted({s.card.id: s.card for s in statuses if s.credit.period == "anniversary_year"}.values(),
                                           key=lambda c: c.name)
                anniversary_cards += [c for c in cards if any(f.basis == "annual" for f in c.free_nights) and c not in anniversary_cards]
                if anniversary_cards:
                    st.markdown("**Card anniversary months** (when your annual fee posts)")
                    cols = st.columns(min(3, len(anniversary_cards)))
                    for i, card in enumerate(anniversary_cards):
                        current = settings.card_anniversary_month.get(card.id, 0)
                        months[card.id] = cols[i % len(cols)].selectbox(
                            card.name, MONTHS, index=MONTHS.index(current),
                            format_func=lambda m: "Not set" if m == 0 else calendar.month_name[m], key=f"bt_month_{card.id}")
                if st.form_submit_button("Save", type="primary"):
                    settings.credits_used = {**{k: v for k, v in settings.credits_used.items() if k not in used_inputs},
                                             **{k: v for k, v in used_inputs.items() if v > 0}}
                    settings.card_anniversary_month = {**{k: v for k, v in settings.card_anniversary_month.items() if k not in months},
                                                       **{k: v for k, v in months.items() if v}}
                    state.save_settings(settings)
                    st.toast("Saved. Comparisons now use what's left of each credit.")
                    st.rerun()
            st.caption("Reset your \"used\" amounts after each reset date. Comparisons only apply what's left.")

    # ---- Free nights
    certs = [(c, f) for c in cards for f in c.free_nights]
    with st.container(border=True, key="card-benefits-2"):
        st.subheader("Free-night certificates")
        if not certs:
            st.caption("No hotel card in your wallet earns a free night.")
        for card, f in certs:
            st.markdown(theme.md(f"- **{card.name}** · {_program_name(cat, f.program)}: {f.describe()}" + (f". {f.note}" if f.note else "")))
        if certs:
            st.caption("Check whether a certificate covers a stay on the Points vs cash page.")

    # ---- Travel benefits
    with st.container(border=True, key="card-benefits-3"):
        st.subheader("Which card to reach for")
        bags = [c for c in cards if c.checked_bags]
        rental = [c for c in cards if c.rental_coverage and c.rental_coverage.type == "primary"]
        fee_cards = [c for c in cards if c.foreign_transaction_fee]
        unknown_fee = [c for c in cards if c.foreign_transaction_fee is None]
        no_fee = [c for c in cards if c.foreign_transaction_fee == 0]

        st.markdown("**Free checked bags**")
        if bags:
            for c in bags:
                b = c.checked_bags
                need = " Buy the ticket with this card." if b.requires_purchase_with_card else ""
                st.markdown(f"- {c.name}: {b.bags} free checked bag{'s' if b.bags > 1 else ''} on {_program_name(cat, b.program)} "
                            f"for you and up to {b.companions} companion{'s' if b.companions != 1 else ''} on the same reservation.{need}")
        else:
            st.caption("None of your cards include free checked bags.")

        st.markdown("**Rental cars: primary collision coverage**")
        if rental:
            for c in rental:
                r = c.rental_coverage
                days = f" Up to {r.max_days_home} days at home" + (f", {r.max_days_abroad} abroad." if r.max_days_abroad else ".") if r.max_days_home else ""
                st.markdown(theme.md(f"- {c.name}: pay the whole rental with it and decline the counter's waiver.{days}" + (f" {r.note}" if r.note else "")))
        else:
            st.caption("No card in your wallet has primary rental coverage. Coverage on most other cards is secondary "
                       "to your own car insurance.")

        st.markdown("**Paying in a foreign currency**")
        if no_fee:
            st.markdown("- No foreign transaction fee: " + ", ".join(c.name for c in no_fee))
        if fee_cards:
            st.markdown("- Leave at home abroad: " + ", ".join(f"{c.name} ({c.foreign_transaction_fee:g}%)" for c in fee_cards))
        if unknown_fee:
            st.markdown("- Check the fee: " + ", ".join(c.name for c in unknown_fee))
