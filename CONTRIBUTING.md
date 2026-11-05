# Contributing

## Local setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
AUTH_DEV_USER=you@example.com streamlit run app/main.py     # signed in as a local test user, data in ./local.db
pytest -q
python scripts/validate_data.py
```

`AUTH_DEV_USER` only works when `APP_ENV` isn't `production`.

## Card data

Every card is one JSON file in `data/cards/`; the schema is `schema/card.schema.json`.

1. Copy a similar card file and rename it to the card's id (the `id` field must match the file name).
2. Fill in the fields:

| Field | Meaning |
|---|---|
| `issuer`, `network`, `type`, `annualFee` | Basics; `type` is `personal` or `business` |
| `currency` | Points currency id from `data/currencies.json` |
| `baseRate` | Earn rate on everything else |
| `portal` | `chase_travel`, `amex_travel`, `capital_one_travel`, `citi_travel`, `us_bank_travel`, `bilt_travel` |
| `earn[]` | `categories`, `channel` (`any`, `direct`, `portal`, `ota` or a list), `rate`, optional `merchant`, `prepaidOnly`, `cap` + `capPeriod`, `validFrom` / `validUntil`, `condition` |
| `credits[]` | `amount`, `period`, `categories`, `channel`, optional `minSpend`, `requiresTag`, `merchant`, plus `creditedAmountEarnsPoints` |
| `lastVerified`, `needsVerification`, `sources` | When and where you checked the terms |

Booking categories: `flight`, `hotel`, `car_rental`, `vacation_rental`, `cruise`, `attraction` (`travel` matches all). `everything` matches any purchase. Spend categories: `dining`, `grocery`, `gas`, `online_retail`, `office_supply`, `drugstore`, `wholesale_club`, `home_improvement`, `transit`, `rideshare`, `streaming`, `entertainment`, `phone_internet`, `advertising`, `shipping`, `fitness`, `rent`, `foreign`, `other`.

3. Run `python scripts/validate_data.py && pytest -q` before opening a pull request. CI runs both.

### Quarterly chores

Rotating categories (Chase Freedom Flex, Discover it) change every quarter. When the monthly **Card data needs review** issue lists an expired rule, replace it with the new quarter's categories and dates, update `lastVerified`, and add the source.

## Code layout

| Path | What it is |
|---|---|
| `traveldeal/engine.py` | The comparison engine (pure functions, no I/O) |
| `traveldeal/models.py`, `catalog.py`, `giftcards.py` | Data types and loaders for `data/` |
| `traveldeal/db.py`, `repository.py` | Database schema and every read/write of user data |
| `traveldeal/backup.py` | Nightly backup and restore |
| `app/` | Streamlit UI (`main.py` entry point, `views/` pages) |
| `scripts/` | Data validator and gift card refresher |
| `deploy/` | Docker, Caddy, VM setup, systemd timers |
