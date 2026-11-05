from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from app import state, theme
from app.booking_form import load_booking
from app.pages import compare_page
from traveldeal.engine import cpp_for
from traveldeal.formatting import usd
from traveldeal.models import UserSettings

def guest_panel() -> None:
    theme.page_header("Account", "Save your trips", "You're trying TravelDeal as a guest, so nothing is saved yet.", key="account")
    st.write("")
    st.write("Create a free account to keep your cards, settings and saved trips, and see them on any device.")
    st.button("Create an account or sign in", type="primary", on_click=state.sign_out)


def _password_tab(user_id: int) -> None:
    from traveldeal.auth import MIN_PASSWORD_LEN, AuthError

    with st.form("change_password", clear_on_submit=True):
        current = st.text_input("Current password", type="password", autocomplete="current-password")
        new = st.text_input(f"New password · at least {MIN_PASSWORD_LEN} characters", type="password", autocomplete="new-password")
        again = st.text_input("Confirm new password", type="password", autocomplete="new-password")
        if st.form_submit_button("Change password", type="primary"):
            try:
                if new != again:
                    raise AuthError("The two new passwords don't match.")
                state.repository().change_password(user_id, current, new)
                st.success("Password changed.")
            except AuthError as e:
                st.error(str(e))


@st.dialog("Delete your account?")
def confirm_delete(user_id: int) -> None:
    st.write("This permanently deletes your wallet, settings and saved trips. It can't be undone.")
    typed = st.text_input('Type DELETE to confirm')
    if st.button("Delete everything", type="primary", disabled=typed != "DELETE"):
        state.repository().delete_user(user_id)
        state.sign_out()
        st.rerun()


def render() -> None:
    user = state.current_user()
    if not user:
        guest_panel()
        return

    repo = state.repository()
    cat = state.catalog()
    theme.page_header("Account", "Your account", f"Signed in as {user['name']} ({user['email'] or 'no email shared'})", key="account")
    st.write("")

    has_password = user.get("kind") == "password" or repo.has_password(user["id"])
    names = ["Saved trips", "Settings", "Your data"] + (["Password"] if has_password else [])
    tabs = st.tabs(names)
    tab_trips, tab_settings, tab_data = tabs[:3]
    if has_password:
        with tabs[3]:
            _password_tab(user["id"])

    with tab_trips:
        trips = repo.list_comparisons(user["id"])
        if not trips:
            st.info("No saved trips yet. Run a comparison and press **Save trip**.")
        for t in trips:
            with st.container(border=True, key=f"card-trip-{t['id']}"):
                a, b, c = st.columns([4, 1, 1])
                a.markdown(f"**{t['name']}** · {t['created_at']:%b %d, %Y}")
                a.caption(f"Best: {t['best_summary']} · {usd(t['best_effective_cost'])} effective cost")
                if b.button("Open", key=f"open_{t['id']}", width="stretch"):
                    load_booking(t["booking"])
                    st.switch_page(compare_page())
                if c.button("Delete", key=f"del_{t['id']}", width="stretch"):
                    repo.delete_comparison(user["id"], t["id"])
                    st.rerun()

    with tab_settings:
        s = state.settings()
        my_cards = [c for c in (cat.card(cid) for cid in state.wallet()) if c]
        with st.form("settings_form"):
            mode = st.radio("Value points at", ["cash", "transfer"], index=0 if s.valuation_mode == "cash" else 1, horizontal=True,
                            format_func={"cash": "Cash value (conservative)", "transfer": "Transfer-partner value"}.get)
            st.markdown("**Cents per point** · leave at 0 to use the default")
            cpp = {}
            for cur_id in dict.fromkeys(c.currency for c in my_cards):
                cur = next(x for x in cat.currencies if x.id == cur_id)
                default = cpp_for(cur_id, cat, UserSettings(valuation_mode=mode))
                cpp[cur_id] = st.number_input(f"{cur.name} (default {default:g}¢)", min_value=0.0, step=0.05,
                                              value=float(s.cpp_overrides.get(cur_id, 0.0)), key=f"cpp_{cur_id}")
            st.markdown("**Credits already used this period**")
            used = {}
            for card in my_cards:
                for credit in card.credits:
                    key = f"{card.id}:{credit.id}"
                    used[key] = st.number_input(f"{credit.name} · {card.name} (of ${credit.amount:,.0f})", min_value=0.0,
                                                max_value=float(credit.amount), value=float(s.credits_used.get(key, 0.0)), key=f"used_{key}")
            st.markdown("**Elite status**")
            status = {}
            for p in cat.loyalty:
                levels = list(p.elite_bonus)
                current = s.elite_status.get(p.id, "member")
                status[p.id] = st.selectbox(p.name, levels, index=levels.index(current) if current in levels else 0,
                                            format_func=lambda x: x.replace("_", " ").title(), key=f"elite_{p.id}")
            if st.form_submit_button("Save settings", type="primary"):
                s.valuation_mode = mode
                s.cpp_overrides = {k: v for k, v in cpp.items() if v > 0}
                s.credits_used = {k: v for k, v in used.items() if v > 0}
                s.elite_status = {k: v for k, v in status.items() if v != "member"}
                state.save_settings(s)
                st.toast("Settings saved.")

    with tab_data:
        st.markdown(f"**Wallet:** {len(state.wallet())} cards")
        if state.wallet():
            st.dataframe(pd.DataFrame({"Card": [cat.card(c).name for c in state.wallet() if cat.card(c)]}), hide_index=True, width="stretch")
        st.download_button("Download my data (JSON)", json.dumps(repo.export_user(user["id"]), indent=2),
                           file_name="traveldeal_my_data.json", mime="application/json")
        st.divider()
        if st.button("Delete my account", type="secondary"):
            confirm_delete(user["id"])
