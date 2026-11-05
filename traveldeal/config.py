"""Runtime configuration, read from environment variables.

Local development needs nothing: the app uses SQLite at ./local.db.
Personal mode (the OCI VM, see docs/PERSONAL_SETUP.md) sets DATABASE_URL to a SQLite file
on a Docker volume. Setting ORACLE_* instead switches to the Always Free Autonomous Database.

ALLOWED_EMAILS (comma-separated) limits who can sign in. Leave it empty to let anyone in.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    app_env: str
    database_url: str | None
    oracle_user: str | None
    oracle_password: str | None
    oracle_dsn: str | None
    dev_user_email: str | None
    backup_bucket: str | None
    backup_prefix: str
    admin_emails: tuple[str, ...]
    allowed_emails: tuple[str, ...] = ()

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    def email_allowed(self, email: str | None) -> bool:
        """True when sign-in is open to everyone, or this email is on the allow-list."""
        if not self.allowed_emails:
            return True
        return bool(email) and email.strip().lower() in self.allowed_emails

    @property
    def uses_oracle(self) -> bool:
        return bool(self.oracle_user and self.oracle_password and self.oracle_dsn)


def get_settings() -> Settings:
    env = os.environ.get
    return Settings(
        app_env=env("APP_ENV", "development"),
        database_url=env("DATABASE_URL"),
        oracle_user=env("ORACLE_USER"),
        oracle_password=env("ORACLE_PASSWORD"),
        oracle_dsn=env("ORACLE_DSN"),
        dev_user_email=env("AUTH_DEV_USER"),
        backup_bucket=env("BACKUP_BUCKET"),
        backup_prefix=env("BACKUP_PREFIX", "traveldeal"),
        admin_emails=_email_list(env("ADMIN_EMAILS", "")),
        allowed_emails=_email_list(env("ALLOWED_EMAILS", "")),
    )


def _email_list(raw: str) -> tuple[str, ...]:
    return tuple(e.strip().lower() for e in raw.split(",") if e.strip())
