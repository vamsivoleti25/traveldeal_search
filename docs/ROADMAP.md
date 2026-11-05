# Roadmap

## Done
- v0.1: React MVP with 10 cards and the comparison engine
- v0.2: 97-card catalog, gift card deals, data-health workflows
- v0.3: Python rewrite on Streamlit; sign-in (Google, optional OCI Identity Domain); saved wallet, settings and trips in Autonomous Database; nightly backups; pull-based deploys on OCI Always Free

## Next
- [ ] Verify the 4 cards marked `needsVerification`
- [ ] Ask CardBear about permission or an API before enabling the weekly gift card refresh
- [ ] Alembic migrations once the schema changes
- [ ] Move secrets from files to OCI Vault
- [ ] Shareable comparison links
- [ ] Natural-language trip input (an LLM fills the form; the engine still does the math)
- [ ] Co-brand portals as channels (Delta Stays, AAdvantage Hotels, Renowned Hotels)
- [ ] Live price feeds or a browser extension
