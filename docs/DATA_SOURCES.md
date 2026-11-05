# Data sources

## Credit cards (`data/cards/`)

The 97-card catalog was compiled on 2026-11-05 from:

- Issuer pages where linked in each card's `sources`
- The Point Calculator program pages (card summaries with fees, multipliers and caps)
- Frequent Miler's category bonus list, for limited-time rates
- Individual 2026 reviews for recent refreshes (Sapphire Preferred, Amex Gold, Chase Aeroplan, Atmos Rewards)

Four cards are marked `needsVerification` because the sources only summarized their rates: Capital One Spark Cash Plus, Marriott Bonvoy Bevy, Marriott Bonvoy Bountiful, and Southwest Rapid Rewards Plus (cap period).

Not modeled on purpose: secured and no-rewards cards, closed-to-new-applicant cards (Citi Prestige, U.S. Bank Altitude Reserve), welcome bonuses, and credits that don't change where you book (dining, streaming, lounge access).

### Card benefits (added 2026-11-05)

| Field | What it holds | Source |
|---|---|---|
| `foreignTransactionFee` | Percent added to foreign-currency charges. `null` = not verified (the app warns instead of guessing): Citi Strata, Ink Business Premier | Issuer pricing pages |
| `checkedBags` | Free first (or first two) checked bags, companions covered, whether the ticket must be bought with the card (United, JetBlue, Atmos) | [The Points Guy, Oct 2026](https://thepointsguy.com/guide/credit-cards-with-free-checked-baggage/) |
| `rentalCoverage` | Primary collision coverage and rental-length limits | [Your Mileage May Vary, Jul 2026](https://yourmileagemayvary.com/2026/07/28/credit-cards-primary-rental-car-coverage/) |
| `freeNight` | Annual and spend-based free-night certificates and their caps | [One Mile at a Time, updated Jan 2026](https://onemileatatime.com/guides/credit-cards-free-hotel-nights/) |
| New credits | Sapphire Reserve The Edit ($250 twice a year, 2+ prepaid nights); Hilton Aspire resort credit ($200 per half-year) | [Doctor of Credit](https://doctorofcredit.com/chase-sapphire-reserve-enhances-500-the-edit-credit-adds-one-time-250-hotel-credit), issuer pages |

The Sapphire Reserve's one-time 2026 $250 credit for select hotel brands isn't modeled.

## Transfer partners (`data/transfers.json`)

Partners and ratios for the 12 loyalty programs TravelDeal models, checked 2026-11-05 against [AwardWallet's transfer tables](https://awardwallet.com/mile-transfer-times?program=Chase) (Chase, Amex, Capital One, Citi) and [point.me](https://www.point.me/insights/bilt-transfer-partners/) (Bilt).

- Some ratios depend on the card you hold: Chase to Hyatt is 1:1 only with a Sapphire Reserve (0.75 otherwise). Citi to American, JetBlue and Wyndham is 1:1 with Strata Premier or Elite (0.7 otherwise).
- `transferCards` lists the cards that can transfer at all (a Chase Freedom alone can't).
- `bonuses` are limited-time and dated; `scripts/validate_data.py` flags them as they expire.
- Transfers round up to each bank's increment (1,000 for Chase, Amex and Citi; 100 for Capital One).

## Exchange rates

[Frankfurter](https://frankfurter.dev): free, no key, European Central Bank reference rates, cached for 6 hours. If it can't be reached, the Compare page asks for the rate.

## Gift card discounts (`data/giftcards.json`)

The snapshot comes from [CardBear](https://www.cardbear.com/gift-cards/travel), which compares resale gift card prices across marketplaces. Each brand links to its live CardBear page.

Since 2026-11-05 each travel brand also lists its **in-stock sellers** (Cardcenter, Carddepot, Raise, CardCash and so on) with their discount and buyer guarantee. Out-of-stock sellers are left out. Offers that need a membership (for example DoorDash with DashPass) are kept but marked conditional, and like CardBear's own headline discount they don't count as the "best seller". The Gift card deals page uses the sellers to show where to buy each card and which of your cards to pay with: online sellers earn your card's everyday rate, and a store selling the card at face value is shown only when your card's bonus there beats the best online deal.

What CardBear's [terms](https://www.cardbear.com/terms) say, in short:

- Reasonable automated access and data reuse are allowed; scraping at unreasonable volume is not.
- Use is for personal, non-commercial comparison and shopping research.
- Don't present CardBear data as guaranteed, real-time or endorsed.
- CardBear's page design, text and organization belong to CardBear.

How this project respects that:

- The gift card page is an original design built from standard Streamlit components. It does not copy CardBear's layout or styling.
- Every discount is labeled as a dated snapshot with attribution and a link to the live page.
- The weekly refresh is **off by default**, fetches one page every 2.5 seconds, travel brands only, and opens a pull request instead of publishing directly.

### Before enabling the weekly refresh

A public GitHub Pages site is not strictly "personal" use. Email CardBear (https://www.cardbear.com/contact) to ask whether a weekly refresh with attribution is OK, or ask whether they offer an API or feed. Then:

1. Repo **Settings → Secrets and variables → Actions → Variables → New repository variable**: `GIFTCARD_SOURCE` = `cardbear`.
2. **Actions → Refresh gift card discounts → Run workflow** to test it.
3. Review the pull request. Large moves (10+ points) are called out in its description.

The page parser (`scripts/giftcard_parse.py`) is tested against seller rows copied from a real CardBear page (Nov 2026): it reads the current discount, twelve-month average, highest discount and the in-stock seller rows. If CardBear changes its layout and every brand fails, the workflow stops with an error and nothing changes; adjust the parser and re-run.
