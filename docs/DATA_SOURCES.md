# Data sources

## Credit cards (`data/cards/`)

The 97-card catalog was compiled on 2026-11-05 from:

- Issuer pages where linked in each card's `sources`
- The Point Calculator program pages (card summaries with fees, multipliers and caps)
- Frequent Miler's category bonus list, for limited-time rates
- Individual 2026 reviews for recent refreshes (Sapphire Preferred, Amex Gold, Chase Aeroplan, Atmos Rewards)

Four cards are marked `needsVerification` because the sources only summarized their rates: Capital One Spark Cash Plus, Marriott Bonvoy Bevy, Marriott Bonvoy Bountiful, and Southwest Rapid Rewards Plus (cap period).

Not modeled on purpose: secured and no-rewards cards, closed-to-new-applicant cards (Citi Prestige, U.S. Bank Altitude Reserve), welcome bonuses, and credits that don't change where you book (dining, streaming, lounge access).

## Gift card discounts (`data/giftcards.json`)

The snapshot comes from [CardBear](https://www.cardbear.com/gift-cards/travel), which compares resale gift card prices across marketplaces. Each brand links to its live CardBear page.

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

The page parser (`scripts/giftcard_parse.py`) was written without access to CardBear's raw HTML, so the first run may not find discounts. If every brand fails, the workflow stops with an error and nothing changes; adjust the labels the parser looks for and re-run.
