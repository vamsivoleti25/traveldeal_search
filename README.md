# TravelDeal Search

Should you book that hotel or flight **direct**, through your **card's travel portal**, through an **online travel agency**, or with **discounted gift cards**? TravelDeal Search picks the cheapest way to pay with the credit cards you already hold.

- **Compare a booking:** pick your cards, enter the price on each site, and get every channel × card combination ranked by effective cost.
- **Stack the extras:** shopping-portal cashback, card-linked offers (Amex Offers, Chase Offers), foreign-currency prices with each card's foreign transaction fee, free checked bags and primary rental-car coverage all count in the ranking.
- **Points vs cash:** enter the award price and see every way your cards can pay with points (the program's own points, transfers from Chase, Amex, Capital One, Citi or Bilt, or the bank portal), priced at your point values against the best way to pay cash. It also checks your free-night certificates.
- **Benefits:** statement credits left to use and when each resets, free nights you hold, and which card to use for bags, rentals and foreign currency.
- **Gift card deals:** discounted travel gift cards with the seller offering each top discount, and which of your cards to buy it with (seller discount + points earned). One click to use the deal in a comparison.
- **Card catalog:** 97 U.S. rewards cards with every multiplier, cap, date and travel credit.
- **Accounts:** create an account with email and password (or sign in with Google) to keep your wallet, settings and saved trips. Or try it as a guest. Download or delete your data any time.

```
effective cost = amount charged
               + foreign transaction fee (foreign-currency charges)
               − statement credits and card-linked offers
               − shopping-portal cashback
               − value of card points earned
               − value of airline / hotel points earned
               − value of elite perks (when they apply)
               − checked bags and rental-car waiver you don't have to buy
```

## Run it locally

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
streamlit run app/main.py
```

Run it from the repo root so the theme in `.streamlit/` loads, then open http://localhost:8501. Locally the app uses SQLite (`local.db`). Create an account on the home screen, or set `AUTH_DEV_USER=you@example.com` to skip sign-in while developing.

Tests (engine, database, accounts, backup/restore, app) and card-data checks:

```bash
pytest -q
python scripts/validate_data.py
```

## Run it on Oracle Cloud (personal mode)

For trying it out yourself: one Always Free VM, Google sign-in limited to emails you list, SQLite on the VM with nightly backups to Object Storage, reached through an SSH tunnel (or HTTPS on your domain when you want it). **Start with [docs/PERSONAL_SETUP.md](docs/PERSONAL_SETUP.md).**

## Production

The full design also runs on **Oracle Cloud Always Free** for $0/month:

- Compute VM (Ampere A1) running Docker, Caddy (free HTTPS) and the Streamlit app
- Autonomous Database (Always Free) for user data
- Object Storage for nightly backups
- GitHub Actions for CI, a monthly data-health issue and an hourly uptime check

| Doc | What's in it |
|---|---|
| [docs/PERSONAL_SETUP.md](docs/PERSONAL_SETUP.md) | Personal mode: login and data design, and a ~45-minute setup |
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
