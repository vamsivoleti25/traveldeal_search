import gzip
import json

import pytest

from traveldeal.backup import restore, snapshot
from traveldeal.db import init_db, make_engine, session_factory
from traveldeal.models import Booking, Channel, UserSettings
from traveldeal.repository import Repository


@pytest.fixture
def repo(tmp_path):
    engine = make_engine(url=f"sqlite:///{tmp_path / 'test.db'}")
    init_db(engine)
    return Repository(session_factory(engine)), engine


def sample_booking() -> Booking:
    return Booking("hotel", [Channel("direct", "direct", "Marriott.com", 420), Channel("chase", "portal", "Chase Travel", 405, portal="chase_travel")], merchant="marriott")


def test_upsert_user_is_idempotent(repo):
    r, _ = repo
    a = r.upsert_user("google:1", "a@example.com", "A")
    b = r.upsert_user("google:1", "a2@example.com", None)
    assert a == b
    assert r.export_user(a)["profile"]["email"] == "a2@example.com"


def test_wallet_round_trip_and_dedupe(repo):
    r, _ = repo
    uid = r.upsert_user("google:1", None, None)
    r.set_wallet(uid, ["amex-gold", "chase-sapphire-reserve", "amex-gold"])
    assert sorted(r.get_wallet(uid)) == ["amex-gold", "chase-sapphire-reserve"]
    r.set_wallet(uid, ["amex-gold"])
    assert r.get_wallet(uid) == ["amex-gold"]


def test_settings_round_trip(repo):
    r, _ = repo
    uid = r.upsert_user("google:1", None, None)
    assert r.get_settings(uid).valuation_mode == "cash"
    r.save_settings(uid, UserSettings(valuation_mode="transfer", elite_status={"marriott": "gold"}))
    s = r.get_settings(uid)
    assert s.valuation_mode == "transfer" and s.elite_status == {"marriott": "gold"}


def test_users_cannot_see_each_others_data(repo):
    r, _ = repo
    alice = r.upsert_user("google:alice", None, None)
    bob = r.upsert_user("google:bob", None, None)
    cid = r.save_comparison(alice, "Maui", sample_booking(), "Direct with CSR", 85.8)
    assert r.list_comparisons(bob) == []
    r.delete_comparison(bob, cid)  # Bob can't delete Alice's row
    assert len(r.list_comparisons(alice)) == 1


def test_saved_comparison_restores_booking(repo):
    r, _ = repo
    uid = r.upsert_user("google:1", None, None)
    r.save_comparison(uid, "Maui", sample_booking(), "Direct with CSR", 85.8)
    saved = r.list_comparisons(uid)[0]
    assert saved["booking"] == sample_booking()
    assert saved["best_effective_cost"] == 85.8


def test_delete_user_removes_everything(repo):
    r, engine = repo
    uid = r.upsert_user("google:1", "a@example.com", None)
    r.set_wallet(uid, ["amex-gold"])
    r.save_settings(uid, UserSettings(valuation_mode="transfer"))
    r.save_comparison(uid, "Trip", sample_booking(), "x", 1)
    r.delete_user(uid)
    data = snapshot(engine)
    assert all(rows == [] for rows in data["tables"].values())


def test_backup_restore_round_trip(repo, tmp_path):
    r, engine = repo
    uid = r.upsert_user("google:1", "a@example.com", "A")
    r.set_wallet(uid, ["amex-gold", "bilt-obsidian"])
    r.save_settings(uid, UserSettings(valuation_mode="transfer"))
    r.save_comparison(uid, "Trip", sample_booking(), "Direct", 85.8)
    payload = gzip.compress(json.dumps(snapshot(engine)).encode())

    fresh = make_engine(url=f"sqlite:///{tmp_path / 'restored.db'}")
    counts = restore(fresh, json.loads(gzip.decompress(payload)))
    assert counts == {"td_users": 1, "td_wallet_cards": 2, "td_user_settings": 1, "td_saved_comparisons": 1}
    r2 = Repository(session_factory(fresh))
    assert sorted(r2.get_wallet(uid)) == ["amex-gold", "bilt-obsidian"]
    assert r2.get_settings(uid).valuation_mode == "transfer"


def test_restore_refuses_non_empty_database(repo):
    r, engine = repo
    r.upsert_user("google:1", None, None)
    with pytest.raises(RuntimeError):
        restore(engine, snapshot(engine))


def test_file_sqlite_uses_wal_and_busy_timeout(tmp_path):
    from sqlalchemy import text

    from traveldeal.db import make_engine

    engine = make_engine(url=f"sqlite:///{tmp_path / 'td.db'}")
    with engine.connect() as conn:
        assert conn.execute(text("PRAGMA journal_mode")).scalar() == "wal"
        assert conn.execute(text("PRAGMA busy_timeout")).scalar() == 5000
        assert conn.execute(text("PRAGMA foreign_keys")).scalar() == 1


def test_email_allow_list():
    from traveldeal.config import Settings

    base = dict(app_env="production", database_url=None, oracle_user=None, oracle_password=None, oracle_dsn=None,
                dev_user_email=None, backup_bucket=None, backup_prefix="x", admin_emails=())
    assert Settings(**base).email_allowed("anyone@example.com")  # empty list = open sign-up
    s = Settings(**base, allowed_emails=("me@example.com",))
    assert s.email_allowed(" ME@example.com ")
    assert not s.email_allowed("someone@example.com")
    assert not s.email_allowed(None)
