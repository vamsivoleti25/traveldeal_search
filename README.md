# TravelDeal Search

Should you book that hotel or flight **direct**, through your **card's travel portal**, through an **online travel agency**, or with **discounted gift cards**? TravelDeal Search picks the cheapest way to pay with the credit cards you already hold.

- **Compare a booking:** pick your cards, enter the price on each site, and get every channel × card combination ranked by effective cost.
- **Gift card deals:** discounted travel gift cards with one-click "compare a booking".
- **Card catalog:** 97 U.S. rewards cards with every multiplier, cap, date and travel credit.
- **Accounts:** sign in with Google (or invite-only email/password) to keep your wallet, settings and saved trips. Download or delete your data any time.

```
effective cost = amount charged
               − statement credits applied
               − value of card points earned
               − value of airline / hotel points earned
               − value of elite perks (when they apply)
```

## Run it locally

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
AUTH_DEV_USER=you@example.com streamlit run app/main.py
```

Open http://localhost:8501. Locally the app uses SQLite (`local.db`) and a stand-in signed-in user, so no cloud setup is needed.

```bash
pytest -q                          # engine, database, backup/restore and app smoke tests
python scripts/validate_data.py    # card data schema and health checks
```

## Production

Runs on **Oracle Cloud Always Free** for $0/month:

- Compute VM (Ampere A1) running Docker, Caddy (free HTTPS) and the Streamlit app
- Autonomous Database (Always Free) for user data
- Object Storage for nightly backups
- GitHub Actions for CI, a monthly data-health issue and an hourly uptime check

| Doc | What's in it |
|---|---|
| [docs/SYSTEM_DESIGN.md](docs/SYSTEM_DESIGN.md) | Architecture, data model, security, backups, free-tier limits and risks |
| [docs/DEPLOY_OCI.md](docs/DEPLOY_OCI.md) | Step-by-step console setup and first deploy |
| [docs/RUNBOOK.md](docs/RUNBOOK.md) | Logs, rollbacks, restores, rebuilding the VM, rotating secrets |
| [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md) | Where card and gift card data comes from, and its terms |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Local setup, card data format, code layout |

## Limitations

- Prices are entered by hand; there are no live price feeds yet.
- Airline and hotel points are estimated on the total price (programs actually earn on base fare or eligible room spend).
- Gift card discounts are a dated snapshot, not live prices.
- Not financial advice. Always confirm card terms on the issuer's site.

## License

Code is MIT-licensed. `data/giftcards.json` is a dated snapshot from CardBear and is subject to CardBear's terms; it is not covered by the MIT license.
