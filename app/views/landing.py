"""Signed-out home: what TravelDeal does, plus sign in / create account."""

from __future__ import annotations

import streamlit as st

from app import state, theme
from traveldeal.auth import MIN_PASSWORD_LEN, AuthError

PROVIDER_LABELS = {"google": "Continue with Google", "oci": "Continue with Oracle account"}


def _sign_in_form() -> None:
    with st.form("sign_in", border=False, enter_to_submit=True):
        email = st.text_input("Email", placeholder="you@example.com", autocomplete="email", key="login_email")
        password = st.text_input("Password", type="password", autocomplete="current-password", key="login_pw")
        if st.form_submit_button("Sign in", type="primary", width="stretch"):
            try:
                state.sign_in_with_password(email, password)
                st.rerun()
            except AuthError as e:
                st.error(str(e))
    st.caption("Forgot your password? The server owner can reset it with `python -m traveldeal.auth reset-password`.")


def _register_form() -> None:
    with st.form("register", border=False, enter_to_submit=True):
        name = st.text_input("Your name", placeholder="Optional", autocomplete="name", key="reg_name")
        email = st.text_input("Email", placeholder="you@example.com", autocomplete="email", key="reg_email")
        password = st.text_input(f"Password · at least {MIN_PASSWORD_LEN} characters", type="password",
                                 autocomplete="new-password", key="reg_pw")
        confirm = st.text_input("Confirm password", type="password", autocomplete="new-password", key="reg_pw2")
        if st.form_submit_button("Create account", type="primary", width="stretch"):
            try:
                state.register_account(name, email, password, confirm)
                st.rerun()
            except AuthError as e:
                st.error(str(e))
    st.caption("We store a salted hash of your password, never the password itself.")


def _auth_card() -> None:
    with st.container(key="auth-card"):
        st.subheader("Welcome")
        sign_in, register = st.tabs(["Sign in", "Create account"])
        with sign_in:
            _sign_in_form()
        with register:
            _register_form()
        providers = state.login_providers()
        if providers:
            st.caption("or")
            for p in providers:
                st.button(PROVIDER_LABELS.get(p, f"Continue with {p.title()}"), key=f"login_{p}",
                          on_click=st.login, args=(p,), width="stretch")
        st.button("Try it without an account →", key="guest", type="tertiary", on_click=state.enter_guest_mode,
                  width="stretch")


def render() -> None:
    theme.brand_bar()
    st.write("")
    with st.container(key="landing-hero"):
        left, right = st.columns([1.15, 1], gap="large", vertical_alignment="center")
        with left:
            st.markdown('<div class="td-eyebrow">TravelDeal Search</div>', unsafe_allow_html=True)
            st.title("Book every trip the cheapest way your cards allow.")
            st.markdown(
                "Direct, card portal, travel agency or discounted gift cards? Pick the cards in your wallet, "
                "enter the prices you see, and get every option ranked by what it really costs you."
            )
            st.markdown(
                '<ul class="td-ticks">'
                "<li>Points, statement credits and elite perks counted in dollars</li>"
                "<li>Card portals compared against booking direct</li>"
                "<li>Gift card discounts stacked on top</li>"
                "</ul>"
                '<div class="td-chips"><span class="td-chip"><b>97</b> U.S. cards tracked</span>'
                '<span class="td-chip"><b>Every</b> multiplier and cap</span>'
                '<span class="td-chip">No bank logins</span></div>',
                unsafe_allow_html=True,
            )
        with right:
            _auth_card()

    st.html('<div class="td-section-title">How it works</div>')
    steps = [
        ("1", "Add your cards", "Search 97 U.S. rewards cards and add the ones you hold. No account numbers, no bank links."),
        ("2", "Enter the prices you see", "Hotel or airline site, your card's travel portal, an online agency: type in each price."),
        ("3", "Pay the cheapest way", "See the effective cost of every channel and card, with the math behind each number."),
    ]
    for col, (num, title, body) in zip(st.columns(3, gap="medium"), steps):
        col.html(f'<div class="td-feature"><div class="num">{num}</div><h4>{title}</h4><p>{body}</p></div>')

    st.html('<div class="td-section-title">Why the numbers hold up</div>')
    points = [
        ("◆", "One formula for every option", "Amount charged, minus credits, minus the value of every point earned."),
        ("◆", "Your valuations, not ours", "Use cash value or transfer-partner value, or set your own cents per point."),
        ("◆", "Sources on every card", "Each card lists when its terms were last checked and where they came from."),
    ]
    for col, (num, title, body) in zip(st.columns(3, gap="medium"), points):
        col.html(f'<div class="td-feature"><div class="num">{num}</div><h4>{title}</h4><p>{body}</p></div>')
    theme.footer()
