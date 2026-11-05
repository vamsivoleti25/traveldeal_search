"""Shared app state: services, the signed-in user, their wallet and settings.

Signed-in users' data lives in the database. Anonymous visitors keep their
wallet in the URL (?cards=...) so it survives a refresh and can be bookmarked.
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


def _identity() -> dict[str, str] | None:
    """Who is signed in, according to the identity provider (or the local dev stand-in)."""
    if auth_configured():
        if not st.user.get("is_logged_in", False):
            return None
        issuer = st.user.get("iss", "oidc")
        return {
            "subject": f"{issuer}|{st.user.get('sub')}",
            "email": st.user.get("email"),
            "email_verified": st.user.get("email_verified", True) is not False,
            "name": st.user.get("name") or st.user.get("given_name") or st.user.get("email"),
        }
    settings = get_settings()
    if settings.dev_user_email and not settings.is_production:
        return {"subject": f"dev|{settings.dev_user_email}", "email": settings.dev_user_email, "name": "Local developer"}
    return None


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
            for k in ("td_user", "td_wallet", "td_settings"):
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
