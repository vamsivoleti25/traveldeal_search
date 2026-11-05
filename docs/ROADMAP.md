# Roadmap

## v0.1 — MVP (this repo)
- [x] Card catalog with schema validation (10 seed cards)
- [x] Comparison engine: portals, direct, OTA, gift cards, credits, caps, loyalty, elite perks
- [x] Card picker dropdown, booking form, ranked results with breakdowns
- [x] Settings: cash vs. transfer valuation, cents-per-point overrides, credits used, elite status
- [x] CI + GitHub Pages deploy

## v0.2 — Catalog depth and gift cards (done)
- [x] 97 U.S. rewards cards across Chase, Amex, Capital One, Citi, Bank of America, Wells Fargo, U.S. Bank, Barclays, Bilt, Discover and Apple, including airline, hotel and business cards
- [x] Quarterly / monthly / billing-cycle caps, dated rotating and limited-time rules, conditions shown as warnings
- [x] Card catalog page with every multiplier, credit, verification date and source
- [x] Gift card deals page with a dated discount snapshot and "use in comparison"
- [x] Monthly card-data health issue; weekly gift card refresh workflow (opt-in)
- [ ] Verify the 4 cards still marked `needsVerification`
- [ ] Ask CardBear about permission or an API before enabling the weekly refresh
- [ ] Model co-brand portals (Delta Stays, AAdvantage Hotels, Renowned Hotels) as channels

## v0.3 — Smarter inputs
- [ ] Natural-language input: "Delta BOS-HNL $480 direct, $510 Chase portal" → form fields (LLM only parses; the engine does the math)
- [ ] Shareable URL with booking + cards encoded in the query string
- [ ] Welcome-bonus mode: weight cards where you're working toward minimum spend
- [ ] Taxes vs. base fare split for more accurate loyalty earn

## v0.4 — Live data
- [ ] Flight / hotel price APIs (e.g. Duffel, Amadeus) for direct prices
- [ ] Browser extension that reads the price on the booking page you're already on
- [ ] Contributor tool: draft a card JSON from an issuer terms page for human review

## Later
- [ ] Shared card-data package with the rewards-tracking app
- [ ] Transfer-partner award search (points vs. cash for the same flight)
