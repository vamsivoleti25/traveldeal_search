from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from app import state
from app.booking_form import load_booking
from app.pages import compare_page
from traveldeal.engine import cpp_for
from traveldeal.formatting import usd
from traveldeal.models import UserSettings

PROVIDER_LABELS = {"google": "Continue with Google", "oci": "Sign in with email and password"}


def sign_in_panel() -> None:
    st.title("Your account")
    providers = state.login_providers()
    if not providers:
        st.info(
            "Sign-in isn't configured on this server yet. Locally, set AUTH_DEV_USER=you@example.com to try accounts, "
            "or add an [auth] section to .streamlit/secrets.toml (see docs/DEPLOY_OCI.md)."
        )
        return
    st.write("Sign in to keep your cards, settings and saved trips across devices.")
    for p in providers:
        st.button(PROVIDER_LABELS.get(p, f"Sign in with {p.title()}"), key=f"login_{p}", on_click=st.login, args=(p,), type="primary")
    st.caption("We never see or store your password. Sign-in is handled by the provider you choose.")


@st.dialog("Delete your account?")
def confirm_delete(user_id: int) -> None:
    st.write("This permanently deletes your wallet, settings and saved trips. It can't be undone.")
    typed = st.text_input('Type DELETE to confirm')
    if st.button("Delete everything", type="primary", disabled=typed != "DELETE"):
        state.repository().delete_user(user_id)
        for k in ("td_user", "td_wallet", "td_settings"):
            st.session_state.pop(k, None)
        if state.auth_configured():
            st.logout()
        st.rerun()


def render() -> None:
    user = state.current_user()
    if not user:
        sign_in_panel()
        return

    repo = state.repository()
    cat = state.catalog()
    st.title("Your account")
    st.caption(f"Signed in as {user['name']} ({user['email'] or 'no email shared'})")

    tab_trips, tab_settings, tab_data = st.tabs(["Saved trips", "Settings", "Your data"])

    with tab_trips:
        trips = repo.list_comparisons(user["id"])
        if not trips:
            st.info("No saved trips yet. Run a comparison and press **Save trip**.")
        for t in trips:
            with st.container(border=True):
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
