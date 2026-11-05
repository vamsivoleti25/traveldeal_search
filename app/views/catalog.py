from __future__ import annotations

import streamlit as st

from app import state, theme
from traveldeal.catalog import ISSUER_LABELS, PORTAL_LABELS
from traveldeal.engine import rule_is_active, today_iso
from traveldeal.formatting import describe_credit, describe_rule, rule_details


def render() -> None:
    cat = state.catalog()
    wallet = state.wallet()
    theme.page_header("Cards", "Card catalog",
                      f"{len(cat.cards)} U.S. rewards cards with every earning multiplier, cap and travel credit we track. "
                      f"{len(wallet)} in your wallet.", key="catalog")
    st.write("")

    f1, f2, f3, f4 = st.columns([3, 2, 2, 2])
    query = f1.text_input("Search cards", placeholder="Search cards")
    issuers = sorted({c.issuer for c in cat.cards}, key=lambda i: ISSUER_LABELS[i])
    issuer = f2.selectbox("Issuer", ["all", *issuers], format_func=lambda i: "All issuers" if i == "all" else ISSUER_LABELS[i])
    kind = f3.selectbox("Type", ["all", "personal", "business"], format_func={"all": "Personal & business", "personal": "Personal", "business": "Business"}.get)
    portal_only = f4.checkbox("Has a travel portal")

    q = query.strip().lower()
    cards = [
        c for c in cat.cards
        if (issuer == "all" or c.issuer == issuer)
        and (kind == "all" or c.type == kind)
        and (not portal_only or c.portal)
        and (not q or q in c.name.lower() or q in ISSUER_LABELS[c.issuer].lower())
    ]
    if not cards:
        st.info("No cards match those filters.")
        return

    today = today_iso()
    cols = st.columns(3)
    for i, card in enumerate(cards):
        with cols[i % 3].container(border=True, key=f"card-cat-{card.id}"):
            mine = card.id in wallet
            st.html(theme.card_art(card.name, card.issuer,
                                   f"{ISSUER_LABELS[card.issuer]}{' · Business' if card.type == 'business' else ''}"))
            if mine:
                st.html('<span class="td-badge">In your wallet</span>')
            base = f"{card.base_rate:g}%" if card.currency == "cash_back" else f"{card.base_rate:g}x"
            portal = f" · {PORTAL_LABELS[card.portal]}" if card.portal else ""
            st.caption(f"${card.annual_fee:,.0f}/yr · base {base}{portal}")
            lines = []
            for rule in sorted(card.earn, key=lambda r: -r.rate):
                details = rule_details(rule)
                text = f"**{describe_rule(rule, card)}**" + (f" · {' · '.join(details)}" if details else "")
                if not rule_is_active(rule, today):
                    text = f"~~{describe_rule(rule, card)}~~ · not active today"
                lines.append(f"- {text}")
            st.markdown("\n".join(lines) if lines else "- Flat rate on everything")
            if card.credits:
                st.caption("Credits: " + "; ".join(describe_credit(c) for c in card.credits))
            src = " · ".join(f"[Source {n}]({u})" for n, u in enumerate(card.sources[:2], start=1))
            st.caption(("⚠️ Unverified" if card.needs_verification else f"Checked {card.last_verified}") + f" · {src}")
            st.button("In wallet ✓" if mine else "Add to wallet", key=f"toggle_{card.id}",
                      type="secondary" if mine else "primary", on_click=state.toggle_card, args=(card.id,), width="stretch")
