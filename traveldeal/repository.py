"""All reads and writes of user data. The UI never touches SQL directly.

Every function takes the signed-in user's id, so one user can never read or
change another user's rows.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from datetime import timedelta

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from . import auth
from .auth import AuthError
from .db import AppUser, Credential, LoginSession, SavedComparison, UserSettingsRow, WalletCard, utcnow
from .models import Booking, CardOffer, Channel, UserSettings

MAX_WALLET_CARDS = 60
MAX_SAVED_COMPARISONS = 200


class Repository:
    def __init__(self, sessions: sessionmaker):
        self._sessions = sessions

    def _session(self) -> Session:
        return self._sessions()

    # Users -------------------------------------------------------------------
    def upsert_user(self, auth_subject: str, email: str | None, display_name: str | None) -> int:
        """Create the user on first login; update email/name and last login otherwise."""
        with self._session() as s:
            user = s.scalar(select(AppUser).where(AppUser.auth_subject == auth_subject))
            if user is None:
                user = AppUser(auth_subject=auth_subject, email=email, display_name=display_name)
                s.add(user)
            else:
                user.email = email or user.email
                user.display_name = display_name or user.display_name
                user.last_login_at = utcnow()
            s.commit()
            return user.id

    def delete_user(self, user_id: int) -> None:
        """Permanently delete the user and everything they saved."""
        with self._session() as s:
            for model in (WalletCard, UserSettingsRow, SavedComparison, Credential, LoginSession):
                s.execute(delete(model).where(model.user_id == user_id))
            s.execute(delete(AppUser).where(AppUser.id == user_id))
            s.commit()

    # Email + password accounts ---------------------------------------------------
    def register(self, email: str, password: str, display_name: str | None = None) -> int:
        """Create an email/password account. Raises AuthError with a user-facing message."""
        email = auth.normalize_email(email)
        auth.check_password_rules(password)
        name = (display_name or "").strip()[:200] or email.split("@")[0]
        with self._session() as s:
            if s.scalar(select(Credential.user_id).where(Credential.email == email)) is not None:
                raise AuthError("An account with that email already exists. Sign in instead.")
            user = AppUser(auth_subject=auth.subject_for(email), email=email, display_name=name)
            s.add(user)
            s.flush()
            s.add(Credential(user_id=user.id, email=email, password_hash=auth.hash_password(password)))
            try:
                s.commit()
            except IntegrityError:  # two sign-ups for the same email at once
                s.rollback()
                raise AuthError("An account with that email already exists. Sign in instead.") from None
            return user.id

    def authenticate(self, email: str, password: str) -> int:
        """Check an email and password. Returns the user id, or raises AuthError.

        Wrong email and wrong password give the same message. After MAX_FAILED_LOGINS
        wrong passwords the account is locked for LOCKOUT_MINUTES.
        """
        generic = AuthError("That email and password don't match.")
        try:
            email = auth.normalize_email(email)
        except AuthError:
            auth.burn_time(password)
            raise generic from None
        with self._session() as s:
            cred = s.scalar(select(Credential).where(Credential.email == email))
            if cred is None:
                auth.burn_time(password)
                raise generic
            now = utcnow()
            if cred.locked_until and cred.locked_until > now:
                minutes = max(1, int((cred.locked_until - now).total_seconds() // 60) + 1)
                raise AuthError(f"Too many attempts. Try again in {minutes} minute{'s' if minutes > 1 else ''}.")
            if not auth.verify_password(password or "", cred.password_hash):
                cred.failed_attempts += 1
                if cred.failed_attempts >= auth.MAX_FAILED_LOGINS:
                    cred.failed_attempts = 0
                    cred.locked_until = now + timedelta(minutes=auth.LOCKOUT_MINUTES)
                s.commit()
                raise generic
            cred.failed_attempts = 0
            cred.locked_until = None
            user = s.get(AppUser, cred.user_id)
            user.last_login_at = now
            s.commit()
            return cred.user_id

    def has_password(self, user_id: int) -> bool:
        with self._session() as s:
            return s.get(Credential, user_id) is not None

    def change_password(self, user_id: int, current: str, new: str) -> None:
        with self._session() as s:
            cred = s.get(Credential, user_id)
            if cred is None or not auth.verify_password(current or "", cred.password_hash):
                raise AuthError("Your current password isn't right.")
            auth.check_password_rules(new)
            cred.password_hash = auth.hash_password(new)
            cred.password_changed_at = utcnow()
            s.commit()

    def reset_password(self, email: str, new: str) -> None:
        """Server-side reset (CLI). Also signs the account out of every browser."""
        email = auth.normalize_email(email)
        auth.check_password_rules(new)
        with self._session() as s:
            cred = s.scalar(select(Credential).where(Credential.email == email))
            if cred is None:
                raise AuthError(f"No email/password account for {email}.")
            cred.password_hash = auth.hash_password(new)
            cred.password_changed_at = utcnow()
            cred.failed_attempts, cred.locked_until = 0, None
            s.execute(delete(LoginSession).where(LoginSession.user_id == cred.user_id))
            s.commit()

    # Browser sessions (the "remember me" cookie) --------------------------------
    def create_login_session(self, user_id: int) -> str:
        token = auth.new_session_token()
        now = utcnow()
        with self._session() as s:
            s.execute(delete(LoginSession).where(LoginSession.user_id == user_id, LoginSession.expires_at < now))
            s.add(LoginSession(user_id=user_id, token_hash=auth.token_hash(token),
                               expires_at=now + timedelta(days=auth.SESSION_DAYS)))
            s.commit()
        return token

    def user_for_session(self, token: str) -> dict[str, Any] | None:
        if not token:
            return None
        with self._session() as s:
            row = s.scalar(select(LoginSession).where(LoginSession.token_hash == auth.token_hash(token)))
            if row is None or row.expires_at < utcnow():
                return None
            user = s.get(AppUser, row.user_id)
            if user is None:
                return None
            return {"id": user.id, "subject": user.auth_subject, "email": user.email, "name": user.display_name}

    def end_login_session(self, token: str) -> None:
        if not token:
            return
        with self._session() as s:
            s.execute(delete(LoginSession).where(LoginSession.token_hash == auth.token_hash(token)))
            s.commit()

    # Wallet ------------------------------------------------------------------
    def get_wallet(self, user_id: int) -> list[str]:
        with self._session() as s:
            rows = s.scalars(select(WalletCard.card_id).where(WalletCard.user_id == user_id).order_by(WalletCard.added_at))
            return list(rows)

    def set_wallet(self, user_id: int, card_ids: list[str]) -> None:
        wanted = list(dict.fromkeys(card_ids))[:MAX_WALLET_CARDS]
        with self._session() as s:
            current = set(s.scalars(select(WalletCard.card_id).where(WalletCard.user_id == user_id)))
            for card_id in current - set(wanted):
                s.execute(delete(WalletCard).where(WalletCard.user_id == user_id, WalletCard.card_id == card_id))
            for card_id in wanted:
                if card_id not in current:
                    s.add(WalletCard(user_id=user_id, card_id=card_id))
            s.commit()

    # Settings ----------------------------------------------------------------
    def get_settings(self, user_id: int) -> UserSettings:
        with self._session() as s:
            row = s.get(UserSettingsRow, user_id)
            return UserSettings.from_dict(json.loads(row.settings_json)) if row else UserSettings()

    def save_settings(self, user_id: int, settings: UserSettings) -> None:
        payload = json.dumps(settings.to_dict(), sort_keys=True)
        with self._session() as s:
            row = s.get(UserSettingsRow, user_id)
            if row is None:
                s.add(UserSettingsRow(user_id=user_id, settings_json=payload))
            else:
                row.settings_json = payload
                row.updated_at = utcnow()
            s.commit()

    # Saved comparisons -------------------------------------------------------
    def save_comparison(self, user_id: int, name: str, booking: Booking, best_summary: str, best_cost: float) -> int:
        with self._session() as s:
            count = len(list(s.scalars(select(SavedComparison.id).where(SavedComparison.user_id == user_id))))
            if count >= MAX_SAVED_COMPARISONS:
                raise ValueError(f"You can save up to {MAX_SAVED_COMPARISONS} comparisons. Delete some first.")
            row = SavedComparison(
                user_id=user_id,
                name=name.strip()[:200] or "Untitled trip",
                booking_json=json.dumps(booking_to_dict(booking)),
                best_summary=best_summary[:500],
                best_effective_cost=round(best_cost, 2),
            )
            s.add(row)
            s.commit()
            return row.id

    def list_comparisons(self, user_id: int) -> list[dict[str, Any]]:
        with self._session() as s:
            rows = s.scalars(
                select(SavedComparison).where(SavedComparison.user_id == user_id).order_by(SavedComparison.created_at.desc())
            )
            return [
                {
                    "id": r.id,
                    "name": r.name,
                    "best_summary": r.best_summary,
                    "best_effective_cost": float(r.best_effective_cost),
                    "created_at": r.created_at,
                    "booking": booking_from_dict(json.loads(r.booking_json)),
                }
                for r in rows
            ]

    def delete_comparison(self, user_id: int, comparison_id: int) -> None:
        with self._session() as s:
            s.execute(delete(SavedComparison).where(SavedComparison.id == comparison_id, SavedComparison.user_id == user_id))
            s.commit()

    # Export ------------------------------------------------------------------
    def export_user(self, user_id: int) -> dict[str, Any]:
        with self._session() as s:
            user = s.get(AppUser, user_id)
            if user is None:
                return {}
            return {
                "profile": {"email": user.email, "name": user.display_name, "created_at": user.created_at.isoformat()},
                "wallet": self.get_wallet(user_id),
                "settings": self.get_settings(user_id).to_dict(),
                "saved_comparisons": [
                    {**c, "created_at": c["created_at"].isoformat(), "booking": booking_to_dict(c["booking"])}
                    for c in self.list_comparisons(user_id)
                ],
            }


def booking_to_dict(booking: Booking) -> dict[str, Any]:
    d = asdict(booking)
    for ch in d["channels"]:
        ch["tags"] = list(ch["tags"])
    return d


def booking_from_dict(d: dict[str, Any]) -> Booking:
    """Saved trips from older versions lack the newer fields; dataclass defaults fill them in."""
    known_channel = set(Channel.__dataclass_fields__)
    channels = [Channel(**{**{k: v for k, v in c.items() if k in known_channel}, "tags": tuple(c.get("tags", ()))})
                for c in d["channels"]]
    extras = {k: d[k] for k in ("nights", "travelers", "checked_bags", "bag_fee", "flight_legs", "rental_days",
                                 "rental_cdw_per_day") if k in d}
    offers = [CardOffer(**o) for o in d.get("offers", [])]
    return Booking(type=d["type"], channels=channels, merchant=d.get("merchant"),
                   direct_perks_value=d.get("direct_perks_value", 0.0), offers=offers, **extras)
