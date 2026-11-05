"""Shared app state: services, the signed-in user, their wallet and settings.

Signed-in users' data lives in the database. Sign-in is email + password (accounts in our
own database, remembered by a cookie) or Google (Streamlit's OIDC). Guests ("try without an
account") keep their wallet in the URL (?cards=...) so it survives a refresh.
"""

from __future__ import annotations

from typing import Any

import streamlit as st

from traveldeal.catalog import load_catalog
from traveldeal.config import get_settings
from traveldeal.db import init_db, make_engine, session_factory
from traveldeal.models import CatalogData, UserSettings
from traveldeal.repository import Repository

SS = st.session_state


@st.cache_resource(show_spinner=False)
def repository() -> Repository:
    engine = make_engine(get_settings())
    init_db(engine)
    return Repository(session_factory(engine))


@st.cache_resource(show_spinner=False)
def catalog() -> CatalogData:
    return load_catalog()


# ---------------------------------------------------------------- auth
def _secrets_auth() -> dict[str, Any]:
    try:
        return dict(st.secrets.get("auth", {}))
    except Exception:  # no secrets.toml at all
        return {}


def login_providers() -> list[str]:
    """Providers configured under [auth.<name>] in .streamlit/secrets.toml."""
    return [k for k, v in _secrets_auth().items() if isinstance(v, dict) or hasattr(v, "keys")]


def auth_configured() -> bool:
    return bool(login_providers())


COOKIE = "td_session"


def _oidc_signed_in() -> bool:
    return auth_configured() and bool(st.user.get("is_logged_in", False))


def _password_identity() -> dict[str, Any] | None:
    """Email/password user for this browser: from this session, or from the remember-me cookie."""
    if SS.get("td_pw_user"):
        return SS.td_pw_user
    if not SS.get("td_cookie_checked"):
        SS.td_cookie_checked = True  # once per browser session; after sign-out the old cookie is ignored
        token = st.context.cookies.get(COOKIE) if st.context.cookies else None
        if token:
            user = repository().user_for_session(token)
            if user:
                SS.td_pw_user, SS.td_session_token = {**user, "kind": "password"}, token
                return SS.td_pw_user
            SS.td_cookie_op = ("clear", "")  # expired or unknown token
    return None


def _identity() -> dict[str, Any] | None:
    """Who is signed in: Google (OIDC), an email/password account, or the local dev stand-in."""
    if _oidc_signed_in():
        issuer = st.user.get("iss", "oidc")
        return {
            "subject": f"{issuer}|{st.user.get('sub')}",
            "email": st.user.get("email"),
            "email_verified": st.user.get("email_verified", True) is not False,
            "name": st.user.get("name") or st.user.get("given_name") or st.user.get("email"),
            "kind": "oidc",
        }
    pw = _password_identity()
    if pw:
        return pw
    settings = get_settings()
    if settings.dev_user_email and not settings.is_production and not auth_configured():
        return {"subject": f"dev|{settings.dev_user_email}", "email": settings.dev_user_email, "name": "Local developer", "kind": "dev"}
    return None


# ---------------------------------------------------------------- email/password sign-in
def registration_allowed(email: str) -> bool:
    return get_settings().email_allowed(email)


def _start_password_session(user_id: int) -> None:
    repo = repository()
    token = repo.create_login_session(user_id)
    user = repo.user_for_session(token)
    SS.td_pw_user, SS.td_session_token = {**user, "kind": "password"}, token
    SS.td_cookie_op = ("set", token)
    SS.pop("td_guest", None)


def sign_in_with_password(email: str, password: str) -> None:
    """Raises AuthError with a message to show. On success the next run is signed in."""
    _start_password_session(repository().authenticate(email, password))


def register_account(name: str, email: str, password: str, confirm: str) -> None:
    from traveldeal.auth import AuthError, normalize_email

    email = normalize_email(email)
    if not registration_allowed(email):
        raise AuthError("Sign-up is invite-only on this server. Ask the owner to add your email.")
    if password != confirm:
        raise AuthError("The two passwords don't match.")
    _start_password_session(repository().register(email, password, name))


def sign_out() -> None:
    """Sign out of whichever method is in use. Safe to use as a button callback."""
    if SS.get("td_pw_user"):
        repository().end_login_session(SS.get("td_session_token", ""))
        SS.td_cookie_op = ("clear", "")
    for k in ("td_pw_user", "td_session_token", "td_user", "td_wallet", "td_settings", "td_guest"):
        SS.pop(k, None)
    SS.td_cookie_checked = True
    if _oidc_signed_in():
        st.logout()


def flush_cookie() -> None:
    """Write or clear the remember-me cookie. Streamlit can't set cookies from Python, so a tiny
    script does it in the browser; the server reads it back on the next visit."""
    op = SS.pop("td_cookie_op", None)
    if not op:
        return
    action, token = op
    max_age = 60 * 60 * 24 * 30 if action == "set" else 0
    st.html(
        "<script>document.cookie = '" + COOKIE + "=" + token + "; Max-Age=" + str(max_age)
        + "; Path=/; SameSite=Strict' + (location.protocol === 'https:' ? '; Secure' : '');</script>",
        unsafe_allow_javascript=True,
    )


def enter_guest_mode() -> None:
    SS.td_guest = True


def is_guest() -> bool:
    return bool(SS.get("td_guest"))


def _allowed(ident: dict[str, Any]) -> bool:
    settings = get_settings()
    if not settings.allowed_emails:
        return True
    return ident.get("email_verified", True) and settings.email_allowed(ident.get("email"))


def blocked_identity() -> dict[str, Any] | None:
    """Someone who signed in with the provider but isn't on ALLOWED_EMAILS. Never stored."""
    ident = _identity()
    return ident if ident is not None and not _allowed(ident) else None


def current_user() -> dict[str, Any] | None:
    """Signed-in user with their database id. Loads wallet and settings once per session."""
    ident = _identity()
    if ident is not None and not _allowed(ident):
        ident = None  # not invited: treat as signed out and write nothing to the database
    if ident is None:
        if SS.get("td_user"):
            # Signed out since the last run: drop personal data from the session.
            for k in ("td_user", "td_wallet", "td_settings", "td_pw_user", "td_session_token"):
                SS.pop(k, None)
        return None
    if SS.get("td_user", {}).get("subject") != ident["subject"]:
        repo = repository()
        uid = repo.upsert_user(ident["subject"], ident["email"], ident["name"])
        anon_wallet = wallet()
        stored = repo.get_wallet(uid)
        merged = list(dict.fromkeys(stored + anon_wallet))
        if merged != stored:
            repo.set_wallet(uid, merged)
        SS.td_user = {**ident, "id": uid}
        SS.td_wallet = merged
        SS.td_settings = repo.get_settings(uid)
        st.query_params.pop("cards", None)
    return SS.td_user


# ---------------------------------------------------------------- wallet
def wallet() -> list[str]:
    if "td_wallet" not in SS:
        param = st.query_params.get("cards", "")
        known = {c.id for c in catalog().cards}
        SS.td_wallet = [c for c in param.split(",") if c in known] if param else ["chase-sapphire-reserve"]
    return SS.td_wallet


def set_wallet(card_ids: list[str]) -> None:
    SS.td_wallet = list(dict.fromkeys(card_ids))
    user = SS.get("td_user")
    if user:
        repository().set_wallet(user["id"], SS.td_wallet)
    elif SS.td_wallet:
        st.query_params["cards"] = ",".join(SS.td_wallet)
    else:
        st.query_params.pop("cards", None)


def toggle_card(card_id: str) -> None:
    w = wallet()
    set_wallet([c for c in w if c != card_id] if card_id in w else [*w, card_id])


# ---------------------------------------------------------------- settings
def settings() -> UserSettings:
    if "td_settings" not in SS:
        SS.td_settings = UserSettings()
    return SS.td_settings


def save_settings(new: UserSettings) -> None:
    SS.td_settings = new
    user = SS.get("td_user")
    if user:
        repository().save_settings(user["id"], new)


# ---------------------------------------------------------------- widgets that survive page switches
def persist(key: str, default: Any) -> str:
    """Streamlit drops widget state when you leave a page. Keep a copy under `key`
    and hand the widget its own key, restored from that copy on every run."""
    if key not in SS:
        SS[key] = default
    widget_key = f"_w_{key}"
    SS[widget_key] = SS[key]
    return widget_key


def keep(key: str) -> None:
    SS[key] = SS[f"_w_{key}"]
