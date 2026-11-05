# Contributing card data

The catalog is the heart of this project. Every card is one JSON file in `data/cards/`.

## Add a card

1. Copy an existing file with a similar structure (e.g. `chase-sapphire-preferred.json`).
2. Rename it to the card's id, e.g. `wells-fargo-autograph.json`. The `id` field must match the file name.
3. Fill in the fields:

| Field | Meaning |
|---|---|
| `issuer`, `network`, `type`, `annualFee` | Basics. `type` is `personal` or `business` |
| `currency` | Points currency id from `data/currencies.json` (add one there if new) |
| `baseRate` | Earn rate on everything else |
| `portal` | Portal the card unlocks: `chase_travel`, `amex_travel`, `capital_one_travel`, `citi_travel`, `us_bank_travel`, `bilt_travel` |
| `earn[]` | Bonus rules (see below) |
| `credits[]` | Statement credits: `amount`, `period`, `categories`, `channel`, optional `minSpend`, `requiresTag`, `merchant`, and `creditedAmountEarnsPoints` |
| `lastVerified` | `YYYY-MM-DD` you checked the terms, or `null` |
| `needsVerification` | `true` if you couldn't confirm the full terms |
| `sources` | Links you used, issuer page first |

### Earn rules

| Field | Example |
|---|---|
| `categories` | `["dining", "grocery"]` |
| `channel` | `"any"`, `"direct"`, `"portal"`, `"ota"`, or a list like `["direct", "portal"]` |
| `rate` | `4` (points per dollar, or percent for `cash_back` cards) |
| `merchant` | `"marriott"`: only purchases with that program (must exist in `data/loyalty.json`) |
| `prepaidOnly` | `true` for rules like Amex prepaid hotels |
| `cap`, `capPeriod` | `25000`, `"calendar_year"`. Periods: `billing_cycle`, `month`, `quarter`, `calendar_year`, `anniversary_year` |
| `validFrom`, `validUntil` | `"2026-10-01"`, `"2026-12-31"` for rotating or limited-time rates |
| `condition` | `"Q4 bonus activated"`. Shown to the user as an assumption |
| `note` | Free text shown nowhere in the math |

### Channels

- `direct` — booked with the airline or hotel itself
- `portal` — the card issuer's own travel portal
- `ota` — Expedia, Booking.com and similar

Gift card purchases are matched as `direct` purchases in the category where the gift card was bought.

### Categories

Booking types: `flight`, `hotel`, `car_rental`, `vacation_rental`, `cruise`, `attraction`. `travel` matches all of them. `everything` matches any purchase (for capped flat rates).

Spend categories: `dining`, `grocery`, `gas`, `online_retail`, `office_supply`, `drugstore`, `wholesale_club`, `home_improvement`, `transit`, `rideshare`, `streaming`, `entertainment`, `phone_internet`, `advertising`, `shipping`, `fitness`, `rent`, `foreign`, `other`.

4. Run `npm run check`. CI runs the same validation, tests and build on every pull request.

## Quarterly chores

Rotating categories (Chase Freedom Flex, Discover it) change every quarter. When the monthly **Card data health** issue lists an expired rule:

1. Replace the expired rule with the new quarter's categories and dates.
2. Set `lastVerified` and add the source.
3. Run `npm run report` locally to confirm nothing else is flagged.

## Update a card

Change the fields, set `lastVerified` to today, add the source link, and open a PR. The validator warns when a card hasn't been verified for 180 days.

## Gift card snapshot

`data/giftcards.json` holds one entry per brand: `discountPct`, optional `avg12mPct` / `high12mPct`, `liveUrl`, and `merchant` when the gift card works across a whole loyalty program. Update `asOf` whenever you change discounts.
