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
