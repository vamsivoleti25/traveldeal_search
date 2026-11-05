"""Database schema and connection.

One schema, two backends:
  * Oracle Autonomous Database (Always Free) in production, via python-oracledb thin mode
    (no Oracle client install, works on Arm).
  * SQLite for local development and tests.

Table names avoid Oracle reserved words (e.g. USER), every string has a length
(Oracle VARCHAR2 needs one), and JSON is stored as text for portability.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    Engine,
    ForeignKey,
    Identity,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    event,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

from .config import Settings, get_settings

SCHEMA_VERSION = 1


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class AppUser(Base):
    __tablename__ = "td_users"

    id: Mapped[int] = mapped_column(Integer, Identity(start=1), primary_key=True)
    # Stable identifier from the identity provider ("google:1234..." / "oci:abcd...").
    auth_subject: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    email: Mapped[str | None] = mapped_column(String(320))
    display_name: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    last_login_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    wallet: Mapped[list[WalletCard]] = relationship(back_populates="user", cascade="all, delete-orphan")
    settings: Mapped[UserSettingsRow | None] = relationship(back_populates="user", cascade="all, delete-orphan")
    comparisons: Mapped[list[SavedComparison]] = relationship(back_populates="user", cascade="all, delete-orphan")


class WalletCard(Base):
    __tablename__ = "td_wallet_cards"
    __table_args__ = (UniqueConstraint("user_id", "card_id", name="uq_wallet_user_card"),)

    id: Mapped[int] = mapped_column(Integer, Identity(start=1), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("td_users.id", ondelete="CASCADE"), nullable=False, index=True)
    card_id: Mapped[str] = mapped_column(String(100), nullable=False)
    added_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    user: Mapped[AppUser] = relationship(back_populates="wallet")


class UserSettingsRow(Base):
    __tablename__ = "td_user_settings"

    user_id: Mapped[int] = mapped_column(ForeignKey("td_users.id", ondelete="CASCADE"), primary_key=True)
    settings_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    user: Mapped[AppUser] = relationship(back_populates="settings")


class SavedComparison(Base):
    __tablename__ = "td_saved_comparisons"

    id: Mapped[int] = mapped_column(Integer, Identity(start=1), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("td_users.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    booking_json: Mapped[str] = mapped_column(Text, nullable=False)
    best_summary: Mapped[str] = mapped_column(String(500), nullable=False)
    best_effective_cost: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    user: Mapped[AppUser] = relationship(back_populates="comparisons")


class SchemaVersion(Base):
    __tablename__ = "td_schema_version"

    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    applied_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


def make_engine(settings: Settings | None = None, url: str | None = None) -> Engine:
    """Build the SQLAlchemy engine for this environment."""
    settings = settings or get_settings()
    if url is None and settings.uses_oracle:
        # Walletless TLS to Autonomous Database. Connections are short-lived and pooled;
        # the Always Free tier allows ~30 sessions, so keep the pool small.
        return create_engine(
            "oracle+oracledb://",
            connect_args={"user": settings.oracle_user, "password": settings.oracle_password, "dsn": settings.oracle_dsn},
            pool_size=4,
            max_overflow=2,
            pool_pre_ping=True,
            pool_recycle=1800,
        )
    if settings.is_production and url is None and not settings.database_url:
        raise RuntimeError("APP_ENV=production but no ORACLE_* or DATABASE_URL settings were provided.")
    engine = create_engine(url or settings.database_url or "sqlite:///local.db", pool_pre_ping=True)
    if engine.dialect.name == "sqlite":
        @event.listens_for(engine, "connect")
        def _fk_on(dbapi_conn, _):  # SQLite ignores foreign keys unless asked
            dbapi_conn.execute("PRAGMA foreign_keys=ON")
    return engine


def init_db(engine: Engine) -> None:
    """Create tables if missing and record the schema version. Safe to run on every start."""
    Base.metadata.create_all(engine)
    with sessionmaker(engine)() as s:
        if s.get(SchemaVersion, SCHEMA_VERSION) is None:
            s.add(SchemaVersion(version=SCHEMA_VERSION))
            s.commit()


def session_factory(engine: Engine) -> sessionmaker:
    return sessionmaker(engine, expire_on_commit=False)
