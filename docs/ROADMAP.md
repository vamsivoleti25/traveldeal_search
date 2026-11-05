# Roadmap

## Done
- v0.1: React MVP with 10 cards and the comparison engine
- v0.2: 97-card catalog, gift card deals, data-health workflows
- v0.3: Python rewrite on Streamlit; sign-in (Google, optional OCI Identity Domain); saved wallet, settings and trips in Autonomous Database; nightly backups; pull-based deploys on OCI Always Free

- v0.3.1: fixed card picker and settings toggles dropping every other click; personal mode (SQLite on the VM, `ALLOWED_EMAILS` invite list, SSH-tunnel access, optional public HTTPS profile)
- v0.4: email/password accounts (sign up, sign in, remember-me cookie, lockout, change/reset password), guest mode, redesigned UI (evergreen hero bands, serif headings, card art in the catalog)
- v0.5: points vs cash (transfer partners with card-dependent ratios and bonuses, portal redemptions, free-night certificates); shopping-portal cashback and card-linked offers; foreign currency with live rates and foreign transaction fees; free checked bags; primary rental coverage; The Edit and Hilton resort credits; benefits tracker with reset dates
- v0.5.1: gift card sellers (who has the top discount, guarantees, membership-only offers) and the best card to buy each gift card with

## Next
- [ ] Trips with several parts: flight + hotel + car with a card per part and a trip total
- [ ] Point balances and expiration warnings; elite status progress
- [ ] Paste a booking page, confirmation email or screenshot to fill the form (LLM fills, engine calculates)
- [ ] Alerts: transfer bonuses, credits about to reset, re-check refundable bookings for price drops
- [ ] Hotel taxes and resort fees; earn airline miles on base fare only; value of refundable vs prepaid
- [ ] Annual card review: fee vs credits actually used, keep / cancel / downgrade
- [ ] Email verification and emailed password reset (needs an email service)
- [ ] Verify the 4 cards marked `needsVerification`
- [ ] Ask CardBear about permission or an API before enabling the weekly gift card refresh
- [ ] Alembic migrations once the schema changes
- [ ] Move secrets from files to OCI Vault
- [ ] Shareable comparison links
- [ ] Natural-language trip input (an LLM fills the form; the engine still does the math)
- [ ] Co-brand portals as channels (Delta Stays, AAdvantage Hotels, Renowned Hotels)
- [ ] Live price feeds or a browser extension
