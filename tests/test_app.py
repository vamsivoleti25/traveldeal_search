"""Smoke tests: the Streamlit app renders without errors and shows the right answer."""

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest


@pytest.fixture(autouse=True)
def _fresh_cached_resources():
    # The repository (and its pooled SQLite connection) is an st.cache_resource shared by every
    # AppTest in this process. Clear it so each test talks to its own temp database.
    st.cache_resource.clear()
    yield
    st.cache_resource.clear()


APP = str(__import__("pathlib").Path(__file__).resolve().parent.parent / "app/main.py")


def run_app(monkeypatch, tmp_path, dev_user: str | None = None, guest: bool = False) -> AppTest:
    monkeypatch.chdir(tmp_path)  # local.db lands in a temp folder
    if dev_user:
        monkeypatch.setenv("AUTH_DEV_USER", dev_user)
    else:
        monkeypatch.delenv("AUTH_DEV_USER", raising=False)
    at = AppTest.from_file(APP, default_timeout=30)
    if guest:
        at.session_state["td_guest"] = True
    at.run()
    return at


def test_signed_out_visitor_sees_sign_in_screen(monkeypatch, tmp_path):
    at = run_app(monkeypatch, tmp_path)
    assert not at.exception
    assert at.title[0].value == "Book every trip the cheapest way your cards allow."
    assert [t.label for t in at.tabs] == ["Sign in", "Create account"]


def test_compare_page_renders_worked_example(monkeypatch, tmp_path):
    at = run_app(monkeypatch, tmp_path, guest=True)
    assert not at.exception
    assert at.title[0].value == "Compare a booking"
    assert at.metric[0].value == "$85.80"


def test_signed_in_dev_user_gets_account(monkeypatch, tmp_path):
    at = run_app(monkeypatch, tmp_path, dev_user="dev@example.com")
    assert not at.exception
    assert at.session_state["td_user"]["email"] == "dev@example.com"


def test_renders_signed_out_when_login_is_configured(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("AUTH_DEV_USER", raising=False)
    at = AppTest.from_file(APP, default_timeout=30)
    at.secrets["auth"] = {
        "redirect_uri": "http://localhost:8501/oauth2callback",
        "cookie_secret": "x" * 40,
        "google": {"client_id": "a", "client_secret": "b", "server_metadata_url": "https://accounts.google.com/.well-known/openid-configuration"},
    }
    at.run()
    assert not at.exception
    assert "td_user" not in at.session_state
    assert at.button(key="login_google").label == "Continue with Google"
    at.button(key="guest").click().run()
    assert at.metric[0].value == "$85.80"


# Regression: picking cards one after another used to drop every other pick, because the
# multiselect had no key and its default changed with the wallet (new widget identity).
CARDS_TO_ADD = ["amex-green", "capital-one-venture-x", "citi-double-cash", "chase-freedom-flex"]


def _add_cards_one_by_one(at: AppTest) -> None:
    for card in CARDS_TO_ADD:
        at.multiselect(key="_w_wallet").select(card).run()
        assert not at.exception
        assert card in at.session_state["td_wallet"], f"{card} was dropped"


def test_picking_cards_one_by_one_keeps_every_pick(monkeypatch, tmp_path):
    at = run_app(monkeypatch, tmp_path, guest=True)
    _add_cards_one_by_one(at)
    assert at.session_state["td_wallet"] == ["chase-sapphire-reserve", *CARDS_TO_ADD]
    at.multiselect(key="_w_wallet").unselect("amex-green").run()
    at.multiselect(key="_w_wallet").unselect("citi-double-cash").run()
    assert at.session_state["td_wallet"] == ["chase-sapphire-reserve", "capital-one-venture-x", "chase-freedom-flex"]


def test_picked_cards_are_saved_for_signed_in_user(monkeypatch, tmp_path):
    at = run_app(monkeypatch, tmp_path, dev_user="dev@example.com")
    _add_cards_one_by_one(at)
    # A brand-new session (new browser tab, or after a restart) loads the wallet from the database.
    fresh = run_app(monkeypatch, tmp_path, dev_user="dev@example.com")
    assert fresh.session_state["td_wallet"] == ["chase-sapphire-reserve", *CARDS_TO_ADD]


def test_settings_toggles_respond_to_every_click(monkeypatch, tmp_path):
    at = run_app(monkeypatch, tmp_path, dev_user="dev@example.com")
    start = at.session_state["td_settings"].apply_credits
    for i in range(1, 5):
        at.toggle(key="_w_apply_credits").set_value(not at.toggle(key="_w_apply_credits").value).run()
        assert at.session_state["td_settings"].apply_credits == (start if i % 2 == 0 else not start)
    for mode in ["transfer", "cash", "transfer"]:
        at.button_group(key="_w_valuation_mode").set_value(mode).run()
        assert at.session_state["td_settings"].valuation_mode == mode


# Personal mode: only emails on ALLOWED_EMAILS may sign in, and nobody else is written to the database.
def test_allow_list_blocks_uninvited_user_and_stores_nothing(monkeypatch, tmp_path):
    monkeypatch.setenv("ALLOWED_EMAILS", "Me@Example.com, partner@example.com")
    at = run_app(monkeypatch, tmp_path, dev_user="stranger@example.com")
    assert not at.exception
    assert at.title[0].value == "This TravelDeal Search is private"
    assert "td_user" not in at.session_state
    import sqlite3
    db = tmp_path / "local.db"
    if db.exists():
        assert sqlite3.connect(db).execute("select count(*) from td_users").fetchone()[0] == 0


def test_allow_list_lets_invited_user_in_case_insensitively(monkeypatch, tmp_path):
    monkeypatch.setenv("ALLOWED_EMAILS", "Me@Example.com, partner@example.com")
    at = run_app(monkeypatch, tmp_path, dev_user="me@example.com")
    assert not at.exception
    assert at.title[0].value == "Compare a booking"
    assert at.session_state["td_user"]["email"] == "me@example.com"


# Email + password accounts --------------------------------------------------------------
def _register(at: AppTest, email="vamsi@example.com", password="correct horse", confirm=None, name="Vamsi") -> AppTest:
    at.text_input(key="reg_email").input(email)
    at.text_input(key="reg_pw").input(password)
    at.text_input(key="reg_pw2").input(confirm if confirm is not None else password)
    at.text_input(key="reg_name").input(name)
    at.button(key="FormSubmitter:register-Create account").click().run()
    return at


def _sign_in(at: AppTest, email, password) -> AppTest:
    at.text_input(key="login_email").input(email)
    at.text_input(key="login_pw").input(password)
    at.button(key="FormSubmitter:sign_in-Sign in").click().run()
    return at


def test_register_signs_you_in_and_saves_your_wallet(monkeypatch, tmp_path):
    at = _register(run_app(monkeypatch, tmp_path))
    assert not at.exception
    assert at.session_state["td_user"]["email"] == "vamsi@example.com"
    assert at.title[0].value == "Compare a booking"
    at.multiselect(key="_w_wallet").select("amex-green").run()
    # Sign out, then back in from a fresh browser session: the wallet is still there.
    fresh = _sign_in(run_app(monkeypatch, tmp_path), "VAMSI@example.com ", "correct horse")
    assert not fresh.exception
    assert fresh.session_state["td_user"]["name"] == "Vamsi"
    assert "amex-green" in fresh.session_state["td_wallet"]


def test_register_rejects_bad_input(monkeypatch, tmp_path):
    at = _register(run_app(monkeypatch, tmp_path), password="short")
    assert "at least 8 characters" in at.error[0].value
    at = _register(run_app(monkeypatch, tmp_path), confirm="something else")
    assert "don't match" in at.error[0].value
    _register(run_app(monkeypatch, tmp_path))
    at = _register(run_app(monkeypatch, tmp_path))
    assert "already exists" in at.error[0].value
    assert "td_user" not in at.session_state


def test_wrong_password_is_rejected(monkeypatch, tmp_path):
    _register(run_app(monkeypatch, tmp_path))
    at = _sign_in(run_app(monkeypatch, tmp_path), "vamsi@example.com", "wrong password")
    assert "don't match" in at.error[0].value
    assert "td_user" not in at.session_state
    at = _sign_in(run_app(monkeypatch, tmp_path), "nobody@example.com", "correct horse")
    assert "don't match" in at.error[0].value  # same message for an unknown email


def test_registration_respects_allow_list(monkeypatch, tmp_path):
    monkeypatch.setenv("ALLOWED_EMAILS", "vamsi@example.com")
    at = _register(run_app(monkeypatch, tmp_path), email="stranger@example.com")
    assert "invite-only" in at.error[0].value
    at = _register(run_app(monkeypatch, tmp_path))
    assert at.session_state["td_user"]["email"] == "vamsi@example.com"


def test_remember_me_cookie_restores_the_session(monkeypatch, tmp_path):
    at = _register(run_app(monkeypatch, tmp_path))
    token = at.session_state["td_session_token"]
    # A new browser session that sends the cookie is signed in without typing anything.
    from unittest.mock import patch

    import streamlit as st

    with patch.object(type(st.context), "cookies", new={"td_session": token}):
        again = run_app(monkeypatch, tmp_path)
        assert again.session_state["td_user"]["email"] == "vamsi@example.com"
        # Signing out ends that session in the database, so the old cookie stops working.
        again.sidebar.button[0].click().run()
        assert "td_user" not in again.session_state
        assert run_app(monkeypatch, tmp_path).session_state.get("td_user") is None


def test_guest_can_use_the_app_without_saving(monkeypatch, tmp_path):
    at = run_app(monkeypatch, tmp_path)
    at.button(key="guest").click().run()
    assert not at.exception
    assert at.title[0].value == "Compare a booking"
    assert "td_user" not in at.session_state
