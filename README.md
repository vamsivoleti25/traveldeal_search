# TravelDeal Search

Should you book that hotel or flight **direct**, through your **card's travel portal**, through an **online travel agency**, or with **discounted gift cards**? TravelDeal Search picks the cheapest way to pay using the credit cards you already hold.

The app has three pages:

- **Compare a booking:** pick your cards, enter the price on each site, and get every channel × card combination ranked by **effective cost**.
- **Gift card deals:** discounted travel gift cards (hotels, airlines, cruises, Airbnb, Uber, Amtrak, ...) with a one-click "use in comparison".
- **Card catalog:** 97 U.S. rewards cards with every multiplier, cap, date and travel credit, filterable by issuer, type and portal.

No bank login, no account, nothing leaves your browser.

```
effective cost = amount charged
               − statement credits applied
               − value of card points earned
               − value of airline / hotel points earned
               − value of elite perks (when they apply)
```

## Quick start

```bash
npm install
npm run dev        # http://localhost:5173
npm run check      # validate card data + run tests + production build
```

## What's modeled

| Rule | Example |
|---|---|
| Portal multipliers only work with that issuer's cards | 8x Chase Travel needs a Chase card; Bilt Travel needs a Bilt card |
| Direct vs. portal vs. OTA earn rates | Sapphire Reserve: 8x portal, 4x direct, 1x Expedia |
| Prepaid-only rules | Amex Gold 5x on *prepaid* Amex Travel hotels |
| Co-brand merchant rules | Marriott Bonvoy Boundless 6x at Marriott only |
| Caps by year, quarter, month or billing cycle | Citi Custom Cash 5% on $500 per billing cycle |
| Rotating and limited-time categories, by date | Freedom Flex Q4 2026; Aeroplan 3x dining through 12/31/26, then 2x |
| Conditions you must meet, shown as warnings | "Your top spend category this cycle", "Active Prime membership" |
| Statement credits: min spend, tags, merchants, partial use | Citi Strata Premier $100 off a $500+ stay; Hilton Surpass $50/quarter at Hilton |
| Credited amounts that earn no points | Sapphire Preferred hotel credit |
| Hotel portal bookings don't earn hotel points | Marriott via Chase Travel earns no Bonvoy points |
| Airline tickets in portals still earn miles | Delta via Amex Travel earns SkyMiles |
| Elite status bonuses | Marriott Gold +25% |
| Gift cards | 9% off Marriott, bought at an office supply store with a 5x card |
| Point valuation | Cash value vs. transfer-partner value, or your own cents per point |

## Keeping data current

| What | How it stays fresh |
|---|---|
| Rotating / limited-time rates | Stored with `validFrom` / `validUntil`; the engine ignores them outside their dates |
| Card terms | **Card data health** workflow runs monthly and opens an issue listing expired rules, rules ending within 21 days, and cards not re-verified in 180 days |
| Gift card discounts | **Refresh gift card discounts** workflow runs weekly and opens a pull request with the new snapshot. Off by default; see [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md) before enabling |

## Project layout

```
data/cards/*.json      one file per card (the catalog, 97 cards)
data/currencies.json   points currencies and default cents-per-point
data/loyalty.json      airline + hotel programs, elite bonuses, portal rules
data/giftcards.json    dated gift card discount snapshot
schema/                JSON Schema every card file must pass
scripts/               data validator + health report, gift card refresher
src/engine/            the pure comparison engine (no UI, fully tested)
src/app/               React UI (compare, gift cards, catalog)
tests/                 engine and parser unit tests
docs/                  build guide, data sources, roadmap
```

## Card data

Each card has `lastVerified`, `needsVerification` and `sources`. Cards marked unverified are labeled in the catalog. See [CONTRIBUTING.md](CONTRIBUTING.md) to add or fix a card and [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md) for where the data comes from.

## Limitations

- Prices are entered by hand; there are no live price feeds yet.
- Loyalty points are estimated on the total price. Airlines and hotels actually earn on base fare / eligible room spend, so treat those numbers as approximate.
- Gift card discounts are a dated snapshot, not live prices.
- Not financial advice. Always confirm terms on the issuer's site.

See [docs/ROADMAP.md](docs/ROADMAP.md) for what's next.

## License

MIT
