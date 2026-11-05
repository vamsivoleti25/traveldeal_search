"""TravelDeal Search: Streamlit entry point.

    streamlit run app/main.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:  # let `streamlit run app/main.py` import the app and traveldeal packages
    sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402

from app import pages, state, theme  # noqa: E402
from app.views import account, benefits, catalog, compare, gift_cards, landing, points  # noqa: E402

st.set_page_config(page_title="TravelDeal Search", page_icon=":material/travel_explore:", layout="wide")
theme.apply()
state.flush_cookie()

registry = {
    "compare": st.Page(compare.render, title="Compare", icon=":material/compare_arrows:", default=True),
    "points": st.Page(points.render, title="Points vs cash", icon=":material/swap_horiz:", url_path="points"),
    "benefits": st.Page(benefits.render, title="Benefits", icon=":material/workspace_premium:", url_path="benefits"),
    "gift_cards": st.Page(gift_cards.render, title="Gift card deals", icon=":material/redeem:", url_path="gift-cards"),
    "catalog": st.Page(catalog.render, title="Card catalog", icon=":material/credit_card:", url_path="cards"),
    "account": st.Page(account.render, title="Account", icon=":material/person:", url_path="account"),
}
pages.register(registry)

blocked = state.blocked_identity()
if blocked:
    # Signed in, but not on ALLOWED_EMAILS. Nothing about them is stored.
    theme.brand_bar()
    st.title("This TravelDeal Search is private")
    st.write(f"**{blocked.get('email') or 'This account'}** isn't on the invite list for this server.")
    st.caption("Ask the owner to add your email to ALLOWED_EMAILS, or sign out and use another account.")
    st.button("Sign out", on_click=state.sign_out, type="primary")
    st.stop()

user = state.current_user()
if not user and not state.is_guest():
    landing.render()
    st.stop()

with st.sidebar:
    theme.brand_bar()
    if user:
        st.caption(f"Signed in as **{user['name']}**")
        st.button("Sign out", on_click=state.sign_out, width="stretch", disabled=user.get("kind") == "dev")
    else:
        st.caption("You're trying TravelDeal as a guest. Nothing is saved.")
        st.button("Create a free account", on_click=state.sign_out, type="primary", width="stretch")
    n = len(state.wallet())
    st.caption(f"{n} card{'' if n == 1 else 's'} in your wallet")
    st.divider()
    st.caption("Card terms change often; check the issuer's site before you book. Not financial advice.")

st.navigation(list(registry.values()), position="top").run()
