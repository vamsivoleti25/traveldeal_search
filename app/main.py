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

from app import pages, state  # noqa: E402
from app.views import account, catalog, compare, gift_cards  # noqa: E402

st.set_page_config(page_title="TravelDeal Search", page_icon="✈️", layout="wide")

registry = {
    "compare": st.Page(compare.render, title="Compare", icon=":material/compare_arrows:", default=True),
    "gift_cards": st.Page(gift_cards.render, title="Gift card deals", icon=":material/redeem:", url_path="gift-cards"),
    "catalog": st.Page(catalog.render, title="Card catalog", icon=":material/credit_card:", url_path="cards"),
    "account": st.Page(account.render, title="Account", icon=":material/person:", url_path="account"),
}
pages.register(registry)

user = state.current_user()
with st.sidebar:
    st.markdown("### ✈️ TravelDeal Search")
    if user:
        st.caption(f"Signed in as **{user['name']}**")
        if state.auth_configured():
            st.button("Sign out", on_click=st.logout, width="stretch")
    elif state.auth_configured():
        st.page_link(registry["account"], label="Sign in to save your data", icon=":material/login:")
    n = len(state.wallet())
    st.caption(f"{n} card{'' if n == 1 else 's'} in your wallet")
    st.divider()
    st.caption("Card terms change often; check the issuer's site before you book. Not financial advice.")

st.navigation(list(registry.values()), position="top").run()
