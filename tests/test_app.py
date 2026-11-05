"""Smoke tests: the Streamlit app renders without errors and shows the right answer."""

from streamlit.testing.v1 import AppTest


def run_app(monkeypatch, tmp_path, dev_user: str | None = None) -> AppTest:
    monkeypatch.chdir(tmp_path)  # local.db lands in a temp folder
    if dev_user:
        monkeypatch.setenv("AUTH_DEV_USER", dev_user)
    else:
        monkeypatch.delenv("AUTH_DEV_USER", raising=False)
    at = AppTest.from_file(str(__import__("pathlib").Path(__file__).resolve().parent.parent / "app/main.py"), default_timeout=30)
    at.run()
    return at


def test_compare_page_renders_worked_example(monkeypatch, tmp_path):
    at = run_app(monkeypatch, tmp_path)
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
    at = AppTest.from_file(str(__import__("pathlib").Path(__file__).resolve().parent.parent / "app/main.py"), default_timeout=30)
    at.secrets["auth"] = {
        "redirect_uri": "http://localhost:8501/oauth2callback",
        "cookie_secret": "x" * 40,
        "google": {"client_id": "a", "client_secret": "b", "server_metadata_url": "https://accounts.google.com/.well-known/openid-configuration"},
    }
    at.run()
    assert not at.exception
    assert "td_user" not in at.session_state
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
    at = run_app(monkeypatch, tmp_path)
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
