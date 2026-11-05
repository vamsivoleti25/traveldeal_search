"""Runtime configuration, read from environment variables.

Local development needs nothing: the app uses SQLite at ./local.db.
Production (the OCI VM) sets ORACLE_* variables to use the Always Free Autonomous Database.
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

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

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
        admin_emails=tuple(e.strip().lower() for e in env("ADMIN_EMAILS", "").split(",") if e.strip()),
    )
