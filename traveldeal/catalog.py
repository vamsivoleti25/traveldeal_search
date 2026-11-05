"""Loads the card catalog, currencies, loyalty programs and gift card snapshot from data/."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from .models import Card, CatalogData, Currency, LoyaltyProgram

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

PORTAL_LABELS = {
    "chase_travel": "Chase Travel",
    "amex_travel": "Amex Travel",
    "capital_one_travel": "Capital One Travel",
    "citi_travel": "Citi Travel",
    "us_bank_travel": "U.S. Bank Altitude Rewards Center",
    "bilt_travel": "Bilt Travel",
}

ISSUER_LABELS = {
    "chase": "Chase",
    "amex": "American Express",
    "capital_one": "Capital One",
    "citi": "Citi",
    "bank_of_america": "Bank of America",
    "wells_fargo": "Wells Fargo",
    "us_bank": "U.S. Bank",
    "barclays": "Barclays",
    "discover": "Discover",
    "bilt": "Bilt",
    "apple": "Apple",
    "other": "Other",
}


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_catalog(data_dir: Path = DATA_DIR) -> CatalogData:
    cards = sorted(
        (Card.from_dict(_read(p)) for p in (data_dir / "cards").glob("*.json")),
        key=lambda c: (c.issuer, c.name),
    )
    return CatalogData(
        cards=tuple(cards),
        currencies=tuple(Currency.from_dict(d) for d in _read(data_dir / "currencies.json")),
        loyalty=tuple(LoyaltyProgram.from_dict(d) for d in _read(data_dir / "loyalty.json")),
    )
