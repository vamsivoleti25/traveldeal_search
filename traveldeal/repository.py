"""All reads and writes of user data. The UI never touches SQL directly.

Every function takes the signed-in user's id, so one user can never read or
change another user's rows.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, sessionmaker

from .db import AppUser, SavedComparison, UserSettingsRow, WalletCard, utcnow
from .models import Booking, Channel, UserSettings

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
            for model in (WalletCard, UserSettingsRow, SavedComparison):
                s.execute(delete(model).where(model.user_id == user_id))
            s.execute(delete(AppUser).where(AppUser.id == user_id))
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
    channels = [Channel(**{**c, "tags": tuple(c.get("tags", ()))}) for c in d["channels"]]
    return Booking(type=d["type"], channels=channels, merchant=d.get("merchant"), direct_perks_value=d.get("direct_perks_value", 0.0))
