# TravelDeal Search — Step-by-step build guide

This guide has three parts:

- **Part A** gets the repo running on your machine and live on GitHub Pages (~20 minutes).
- **Part B** walks through how the MVP is built, phase by phase, so you can rebuild or extend any piece.
- **Part C** is the plan for what to build next.
- **Part D** covers the v0.2 update: the 97-card catalog, gift card deals and the data-refresh workflows.

---

## Part A — Run it and publish it

### Step 1. Install the prerequisites

| Tool | Check | Install |
|---|---|---|
| Node.js 20+ (22 recommended) | `node -v` | https://nodejs.org or `brew install node` |
| Git | `git --version` | `brew install git` |
| GitHub account | — | https://github.com |
| GitHub CLI (optional, makes Step 4 one command) | `gh --version` | `brew install gh`, then `gh auth login` |

### Step 2. Unzip and install

```bash
unzip traveldeal_search.zip
cd traveldeal_search
npm install
```

### Step 3. Run it locally

```bash
npm run dev          # opens http://localhost:5173 with hot reload
npm test             # engine and parser tests
npm run validate     # checks every card file against the schema
npm run check        # validate + test + production build (what CI runs)
```

Try it: add Chase Sapphire Reserve and Capital One Venture X, pick a Marriott hotel, enter a direct price and a portal price, and expand rows in the results table to see each breakdown.

### Step 4. Create the GitHub repo and push

The zip already contains a git repository with one commit on `main`.

**Option A — GitHub CLI (fastest):**

```bash
gh repo create traveldeal_search --public --source=. --remote=origin --push
```

**Option B — GitHub website:**

1. Go to https://github.com/new, name it `traveldeal_search`, leave "Add a README" **unchecked**, create it.
2. Then:

```bash
git remote add origin https://github.com/vamsivoleti25/traveldeal_search.git
git push -u origin main
```

### Step 5. Turn on GitHub Pages

1. In the repo, open **Settings → Pages**.
2. Under **Build and deployment → Source**, choose **GitHub Actions**.
3. Open the **Actions** tab. The "Deploy to GitHub Pages" workflow runs on every push to `main`. If it ran before you switched the source, click it and choose **Re-run all jobs**.
4. Your site will be at `https://vamsivoleti25.github.io/traveldeal_search/`.

The Vite config uses `base: './'`, so the site works under that sub-path without changes.

### Step 6. Protect `main` (optional, recommended once others contribute)

**Settings → Branches → Add rule** for `main`: require a pull request and require the **CI / check** status to pass. Then a broken card file can never reach the live site.

### Day-to-day workflow

```bash
git checkout -b add-hilton-cards
# edit data/cards/..., run npm run check
git commit -am "Add Hilton Surpass and Aspire"
git push -u origin add-hilton-cards
gh pr create --fill        # or open the PR on github.com
```

---

## Part B — How the MVP is built

### Phase 1. Scaffold

Rather than a generator, the project is a minimal hand-written Vite + React + TypeScript setup:

- `package.json` — scripts `dev`, `build`, `test`, `validate`, `check`
- `vite.config.ts` — React plugin, `base: './'` for GitHub Pages, Vitest config
- `tsconfig.json` — strict mode, JSON imports enabled
- `index.html` + `src/main.tsx` — the entry point

Why this stack: everything runs in the browser, so hosting is free and static, and there is no backend to secure. TypeScript catches mistakes in the card-rule logic at compile time.

### Phase 2. Model the domain (`src/engine/types.ts`)

Before any code, decide what a "card" and a "booking" are. The key types:

- **`Card`** — issuer, fee, points currency, `baseRate`, `earn[]` rules, `credits[]`, and which `portal` it unlocks.
- **`EarnRule`** — `categories` × `channel` × `rate`, with optional `prepaidOnly`, `merchant` (co-brands) and `capPerYear`.
- **`Credit`** — amount, period, where it applies, optional `minSpend` / `requiresTag`, and whether the credited dollars still earn points.
- **`Channel`** — one place you could book: `direct`, `portal`, `ota` or `giftcard`, with its price.
- **`Booking`** — what you're buying (`hotel`, `flight`, ...), the merchant's loyalty program, and the channels you priced.
- **`UserSettings`** — valuation mode, cents-per-point overrides, credits already used, cap spend used, elite status.
- **`Option`** — one result row: channel × card with a full line-item breakdown and warnings.

The most important design choice is the **channel** concept. "Booked direct", "through the issuer portal" and "through Expedia" earn very differently on the same card, so every earn rule and credit says which channels it covers.

### Phase 3. Build the card catalog (`data/`, `schema/`, `scripts/`)

1. `data/cards/<id>.json` — one file per card, so pull requests stay small and reviewable.
2. `data/currencies.json` — each points currency with a **cash** value and a **transfer** value in cents per point.
3. `data/loyalty.json` — airline and hotel programs: points per dollar, elite bonuses, default point value, and two flags that drive the portal-vs-direct decision:
   - `earnsOnThirdPartyBookings` — airlines `true` (the ticket is still an airline ticket), hotels `false`
   - `elitePerksOnThirdPartyBookings` — same pattern
4. `schema/card.schema.json` — JSON Schema for a card file.
5. `scripts/validate-data.ts` — runs the schema plus cross-checks: id matches file name, currency exists, portal rules have a portal, unverified cards are flagged, stale cards (180+ days) warn.

Each card records `lastVerified`, `needsVerification` and `sources`. The 6 premium cards were checked against 2026 sources; 4 (Freedom Unlimited, Venture, Double Cash, Boundless) are marked unverified for you to confirm.

### Phase 4. Write the comparison engine (`src/engine/compare.ts`)

Pure functions only — no network, no UI, no dates — so it's easy to test and to reuse later (CLI, browser extension, API).

For each channel you priced, and each of your cards that can be used there:

1. **Filter.** A portal channel only pairs with cards from that issuer (`cardCanUseChannel`).
2. **Amount charged.** The price, or for gift cards, the price minus the discount.
3. **Credits** (`computeCredits`). Apply each matching credit up to what's left this period. Track credited dollars that earn no points.
4. **Card points** (`computeEarn`). Pick the highest-rate matching rule. If it has an annual cap, spend above the remaining cap earns the base rate. Gift cards earn in the category where you bought them.
5. **Card point value.** Points × cents per point (your override, or the cash/transfer default).
6. **Loyalty points.** Direct and gift-card bookings earn airline/hotel points with your elite bonus. Third-party bookings earn only if the program allows it.
7. **Perks.** Your estimate of elite perk value, only where the program honors status.
8. **Effective cost** = charged − credits − card points value − loyalty value − perks.
9. **Rank** all options by effective cost; `bestPerChannel` keeps the top card for each channel.

**Worked example** (Sapphire Reserve, Marriott, $420 direct, cash valuation, Marriott member):

| Line | Amount |
|---|---|
| Direct price | $420.00 |
| $300 travel credit (credited dollars earn no points) | −$300.00 |
| 120 × 4x = 480 UR points at 1¢ | −$4.80 |
| 420 × 10 = 4,200 Bonvoy points at 0.7¢ | −$29.40 |
| **Effective cost** | **$85.80** |

The same $405 stay through Chase Travel: −$300 credit, 105 × 8x = 840 points (−$8.40), and no Bonvoy points → $96.60. Direct wins by $10.80 because the Bonvoy points outweigh the portal multiplier. If you've already used the travel credit, uncheck "Apply my unused card credits" and compare again.

### Phase 5. Test the engine (`tests/compare.test.ts`)

19 tests, each pinned to a real rule:

- Sapphire Reserve 8x portal / 4x direct / 1x OTA
- Amex Gold 5x hotels only when prepaid in Amex Travel
- Boundless 6x only at Marriott
- Amex Gold grocery cap overflow
- Portal channels only pair with the right issuer
- Citi $100 benefit only on $500+ stays
- Venture X credit excluded from earning; partial credit use
- Amex Platinum hotel credit needs the FHR / Hotel Collection tag
- Hotel portal bookings earn no hotel points; airline portal tickets still earn miles
- Elite perk value only where honored
- Gift card discount + purchase category earning
- Ranking order, per-channel best, accounting identity, skipping empty prices, credit toggle

When you add a card with an unusual rule, add a test for it in the same PR.

### Phase 6. Build the UI (`src/app/`)

| File | Job |
|---|---|
| `App.tsx` | Holds state, works out which portals your cards unlock, calls the engine |
| `components/CardPicker.tsx` | Searchable dropdown grouped by issuer; Enter adds the top match |
| `components/BookingForm.tsx` | Booking type, airline/hotel brand, price per channel (portal rows appear only for portals your cards unlock), prepaid and FHR toggles, gift card discount, perk value |
| `components/SettingsPanel.tsx` | Cash vs. transfer valuation, cents-per-point overrides, credits used, elite status |
| `components/Results.tsx` | Winner summary, best-card-per-channel table, expandable breakdowns, "show all combinations" |
| `bookingForm.ts` | Converts the form into the engine's `Booking` |
| `storage.ts` | Saves cards, settings and the last booking in `localStorage` (wrapped in try/catch so private browsing still works) |
| `styles.css` | Design tokens with light and dark mode; responsive down to phone width |

### Phase 7. CI and deploy (`.github/workflows/`)

- `ci.yml` — on every PR and push to `main`: `npm ci`, validate data, run tests, type-check and build.
- `deploy.yml` — on push to `main`: the same checks, then publishes `dist/` to GitHub Pages.

---

## Part C — What to build next

A suggested order; details are in [ROADMAP.md](ROADMAP.md).

**Week 1 — Trustworthy data**
1. Verify the 4 unverified cards against issuer pages; set `lastVerified`, flip `needsVerification` to `false`.
2. Add the June 2026 Sapphire Preferred categories.
3. Add 10-15 cards: airline co-brands (Delta, United, American), hotel co-brands (Hilton, Hyatt, IHG), Bilt, Citi Strata Elite, Wells Fargo Autograph, Venture X Business.
4. Show `lastVerified` and the source link next to each selected card.

**Week 2 — Usability**
5. Shareable URLs: encode the booking and selected card ids in the query string.
6. A "why this wins" sentence comparing the top two options line by line.
7. A gift-card reference table with typical discounts by brand and date seen.

**Week 3 — The AI layer**
8. Natural-language input ("Hyatt Maui 3 nights, $1,240 direct, $1,190 Chase Travel") parsed into form fields by an LLM. The engine still does all the math, so numbers stay auditable.
9. A static site can't hold an API key. Add a small serverless function (Cloudflare Workers or Vercel) that holds the key and forwards the parse request.

**Week 4 — Live prices**
10. A flight/hotel price API for direct prices, or a browser extension that reads the price on the page you're already viewing and opens TravelDeal with it pre-filled.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `npm run validate` fails | The message names the file and field. Most often: `id` doesn't match the file name, or an unknown `currency`. |
| Pages site is blank | Settings → Pages → Source must be **GitHub Actions**. Re-run the deploy workflow. |
| Pages URL 404s right after the first deploy | Wait a minute and hard-refresh; first deploys take a moment to propagate. |
| Old settings stick around while developing | Clear site data in the browser, or run `localStorage.clear()` in the console. |

---

## Part D — v0.2: full catalog, gift cards, refresh workflows

### Step 1. Get the update into your repo

The v0.2 zip is the same git repository with a second commit. The simplest path is to replace your local folder:

```bash
cd ~
mv traveldeal_search traveldeal_search-old
unzip ~/Downloads/traveldeal_search.zip
cd traveldeal_search
git remote add origin https://github.com/vamsivoleti25/traveldeal_search.git
git push origin main
npm install
npm run dev
```

If `git push` is rejected because GitHub has commits you don't have locally, run `git pull --rebase origin main` and push again.

### Step 2. What changed

| Area | Change |
|---|---|
| `data/cards/` | 10 → 97 cards, each with sources and a verification date |
| Schema | `type`, `cap` + `capPeriod` (replaces `capPerYear`), `validFrom` / `validUntil`, `condition`, credit `merchant`, quarterly credits, U.S. Bank and Bilt portals, more categories |
| Engine | Ignores rules outside their dates, labels caps by period, surfaces conditions, supports `everything` rules and merchant-only credits |
| `data/giftcards.json` | 47-brand dated discount snapshot (27 travel brands) |
| UI | Tabs for **Compare**, **Gift card deals** and **Card catalog**; gift card hint in the booking form |
| Workflows | `card-data-health.yml` (monthly issue), `refresh-giftcards.yml` (weekly PR, opt-in) |
| Docs | `docs/DATA_SOURCES.md`, updated `CONTRIBUTING.md` |

### Step 3. Turn on the monthly health check

Nothing to configure. It runs on the 1st of each month; to try it now, open **Actions → Card data health → Run workflow**. It opens an issue labeled `card-data` only when something needs attention.

### Step 4. Decide on the gift card refresh

Read `docs/DATA_SOURCES.md` first. If CardBear is fine with it, add the repository variable `GIFTCARD_SOURCE = cardbear` and run **Refresh gift card discounts** once by hand. Each run opens a pull request you merge after a quick look.

### Step 5. Each quarter

Update the rotating categories for Chase Freedom Flex and Discover it (the health issue will remind you), then `npm run check` and push.
