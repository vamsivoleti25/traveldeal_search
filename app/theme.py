"""Look and feel: deep evergreen hero bands, serif display type, soft white cards.

Colors and fonts live in .streamlit/config.toml. This module adds what the theme can't:
the dark hero bands, card tiles, the brand mark and small HTML helpers. Streamlit gives a
container with key="x" the CSS class `st-key-x`, which is how the bands are styled.
"""

from __future__ import annotations

import base64
from html import escape

import streamlit as st

INK = "#0e211d"
EVERGREEN = "#0b5a4a"
MINT = "#86cdb6"

# Original brand mark: a mint arrow climbing past a price line, inside a rounded tile.
LOGO_SVG = """<svg width="30" height="30" viewBox="0 0 32 32" aria-hidden="true">
<rect x="1" y="1" width="30" height="30" rx="9" fill="#0b5a4a"/>
<path d="M7 21.5h18" stroke="#c9eadf" stroke-width="1.6" stroke-linecap="round" opacity=".55"/>
<path d="M8 18.5l5.2-4.8 3.6 3 7.2-7.2" fill="none" stroke="#86cdb6" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>
<path d="M19.6 9.5H24v4.4" fill="none" stroke="#86cdb6" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>
</svg>"""

CSS = """
<style>
/* ---------- base ---------- */
.block-container { padding-top: 4.6rem; padding-bottom: 4rem; max-width: 1180px; }
h1, h2, h3 { letter-spacing: -0.015em; }
[data-testid="stHeader"] { background: rgba(247, 249, 248, 0.86); backdrop-filter: saturate(160%) blur(10px);
  border-bottom: 1px solid #e3ebe8; }
[data-testid="stCaptionContainer"] { color: #4f625d; }

/* ---------- buttons ---------- */
[data-testid^="stBaseButton-primary"] { background: #0b5a4a; border: 1px solid #0b5a4a; font-weight: 600;
  box-shadow: 0 1px 0 rgba(255,255,255,.12) inset, 0 6px 16px -8px rgba(11,90,74,.55); }
[data-testid^="stBaseButton-primary"]:hover { background: #0d6b58; border-color: #0d6b58; }
[data-testid^="stBaseButton-secondary"] { background: #fff; font-weight: 600; }
[data-testid^="stBaseButton-secondary"]:hover { border-color: #0b5a4a; color: #0b5a4a; }

/* ---------- bordered containers (key="card-...") become soft white cards ---------- */
div[class*="st-key-card-"] { background: #fff; border-radius: 18px !important; border-color: #e0eae6 !important;
  box-shadow: 0 1px 2px rgba(14,33,29,.04), 0 12px 32px -20px rgba(14,33,29,.28); }
div[class*="st-key-card-"] h3 { font-size: 1.45rem; }

/* ---------- alerts in brand colors ---------- */
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentInfo"]) { background: #e6f4ef; color: #0b4a3d; }
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentInfo"]) a { color: #0b5a4a; }
[data-testid="stAlertContentInfo"] p { color: #0b4a3d; }

/* ---------- metrics ---------- */
[data-testid="stMetric"] { background: #f2f7f5; border: 1px solid #e0eae6; border-radius: 14px; padding: 14px 16px; }
[data-testid="stMetricValue"] { font-family: Fraunces, serif; font-weight: 600; color: #0b5a4a; }

/* ---------- hero bands (page headers and the landing page) ---------- */
div[class*="st-key-hero"], div.st-key-landing-hero {
  position: relative; overflow: hidden; border-radius: 26px; padding: 34px 36px 30px;
  background:
    radial-gradient(900px 340px at 88% -30%, rgba(134,205,182,.30), transparent 70%),
    radial-gradient(600px 300px at -10% 120%, rgba(134,205,182,.12), transparent 70%),
    linear-gradient(160deg, #0d3c34 0%, #0a2b27 55%, #071d1b 100%);
  box-shadow: 0 30px 60px -40px rgba(7,29,27,.75);
}
div[class*="st-key-hero"] h1, div.st-key-landing-hero h1 { color: #f6fffb; font-size: 2.6rem; line-height: 1.08; }
div[class*="st-key-hero"] p, div[class*="st-key-hero"] [data-testid="stCaptionContainer"],
div.st-key-landing-hero p, div.st-key-landing-hero li { color: rgba(222, 242, 235, .86); }
div[class*="st-key-hero"] [data-testid="stCaptionContainer"], div[class*="st-key-hero"] [data-testid="stCaptionContainer"] p {
  color: rgba(222, 242, 235, .84) !important; font-size: 1rem; opacity: 1 !important; }
div[class*="st-key-hero"] a { color: #86cdb6 !important; }
div.st-key-landing-hero { padding: 54px 48px 48px; }
div.st-key-landing-hero h1 { font-size: 3.5rem; }
@media (max-width: 760px) {
  div[class*="st-key-hero"] { padding: 26px 22px 22px; border-radius: 20px; }
  div[class*="st-key-hero"] h1 { font-size: 2rem; }
  div.st-key-landing-hero { padding: 32px 20px 24px; }
  div.st-key-landing-hero h1 { font-size: 2.4rem; }
}
.td-eyebrow { font-size: .78rem; letter-spacing: .16em; text-transform: uppercase; font-weight: 700; color: #86cdb6 !important; margin-bottom: .2rem; }
.td-ticks { list-style: none; padding: 0; margin: 1rem 0 0; }
.td-ticks li { padding-left: 1.7rem; position: relative; margin: .45rem 0; }
.td-ticks li::before { content: ""; position: absolute; left: 0; top: .3rem; width: 1.05rem; height: 1.05rem; border-radius: 50%;
  background: rgba(134,205,182,.22) url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E%3Cpath d='M4 8.3l2.6 2.5L12 5.5' fill='none' stroke='%2386cdb6' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E") center/70% no-repeat; }
.td-chips { display: flex; flex-wrap: wrap; gap: .5rem; margin-top: 1.4rem; }
.td-chip { border: 1px solid rgba(134,205,182,.35); color: #dff3ec; border-radius: 999px; padding: .32rem .8rem; font-size: .85rem; }
.td-chip b { color: #fff; }

/* ---------- auth card on the landing page ---------- */
div.st-key-auth-card { background: #fff; border-radius: 22px; padding: 26px 26px 18px;
  box-shadow: 0 40px 80px -40px rgba(0,0,0,.6); }
div.st-key-auth-card p, div.st-key-auth-card label, div.st-key-auth-card [data-testid="stCaptionContainer"] { color: #33463f !important; }
div.st-key-auth-card h3 { color: #0e211d; margin-bottom: 0; }
div.st-key-auth-card [data-testid^="stBaseButton-primary"] p { color: #fff !important; }
div.st-key-auth-card [data-testid="stBaseButton-tertiary"] p { color: #0b5a4a !important; font-weight: 600; }

/* ---------- brand bar ---------- */
.td-brand { display: flex; align-items: center; gap: .6rem; font-family: Fraunces, serif; font-weight: 650;
  font-size: 1.35rem; color: #0e211d; letter-spacing: -.01em; }
.td-brand span em { font-style: normal; color: #0b5a4a; }

/* ---------- feature tiles ---------- */
.td-feature { background: #fff; border: 1px solid #e0eae6; border-radius: 20px; padding: 22px 22px 18px; height: 100%; }
.td-feature .num { font-family: Fraunces, serif; font-size: 1.9rem; color: #0b5a4a; line-height: 1; }
.td-feature h4 { font-family: Fraunces, serif; font-size: 1.2rem; margin: .7rem 0 .35rem; color: #0e211d; }
.td-feature p { color: #4f625d; margin: 0; font-size: .95rem; }
.td-section-title { font-family: Fraunces, serif; font-size: 2rem; color: #0e211d; margin: 2.6rem 0 1rem; letter-spacing: -.015em; }

/* ---------- card art in the catalog ---------- */
.td-cardart { position: relative; aspect-ratio: 1.586; border-radius: 14px; padding: 12px 14px; color: #fff;
  overflow: hidden; margin-bottom: .6rem; box-shadow: 0 12px 24px -16px rgba(0,0,0,.6); }
.td-cardart::after { content: ""; position: absolute; inset: 0;
  background: radial-gradient(120% 80% at 100% 0%, rgba(255,255,255,.28), transparent 55%); }
.td-cardart .issuer { font-size: .66rem; letter-spacing: .14em; text-transform: uppercase; opacity: .85; font-weight: 700; }
.td-cardart .name { position: absolute; left: 14px; right: 14px; bottom: 11px; font-family: Fraunces, serif;
  font-size: 1rem; line-height: 1.15; font-weight: 600; }
.td-cardart .chip { position: absolute; left: 14px; top: 38%; width: 28px; height: 21px; border-radius: 5px;
  background: linear-gradient(135deg, #f4e3b0, #c9a95b); opacity: .9; }
.td-badge { display: inline-block; background: #e3f3ed; color: #0b5a4a; border-radius: 999px; padding: .12rem .55rem;
  font-size: .75rem; font-weight: 700; }

.td-footer { margin-top: 3rem; padding-top: 1.2rem; border-top: 1px solid #e3ebe8; color: #6b7d78; font-size: .85rem; }
</style>
"""

# Gradient per issuer for the generated card art (no real card images are used).
ISSUER_GRADIENTS = {
    "chase": ("#123a6b", "#1d5fa8"),
    "amex": ("#1f4d63", "#4f8aa3"),
    "capital_one": ("#1b2a3a", "#3c5468"),
    "citi": ("#0f3d63", "#2a7bb8"),
    "bilt": ("#141414", "#3a3a3a"),
    "wells_fargo": ("#5c1a1a", "#a33a2a"),
    "bank_of_america": ("#3b1020", "#8a2134"),
    "us_bank": ("#1c2c4d", "#3d5a8f"),
    "discover": ("#5a2a06", "#d06a1f"),
    "barclays": ("#0b3a52", "#2a8fb8"),
    "apple": ("#8e8e93", "#d1d1d6"),
}


def md(text: str) -> str:
    """Escape dollar signs so Markdown doesn't read "$250 ... $50" as math."""
    return text.replace("$", "\\$")


def apply() -> None:
    st.html(CSS)


LOGO_IMG = "data:image/svg+xml;base64," + base64.b64encode(
    LOGO_SVG.replace("<svg ", '<svg xmlns="http://www.w3.org/2000/svg" ', 1).encode()).decode()


def brand_bar() -> None:
    # st.html strips inline <svg>, so the mark goes in as an image.
    st.html(f'<div class="td-brand"><img src="{LOGO_IMG}" width="30" height="30" alt=""><span>Travel<em>Deal</em></span></div>')


def page_header(eyebrow: str, title: str, subtitle: str, key: str) -> None:
    """Dark hero band with a serif title. `key` must be unique per page."""
    with st.container(key=f"hero-{key}"):
        st.markdown(f'<div class="td-eyebrow">{escape(eyebrow)}</div>', unsafe_allow_html=True)
        st.title(title)
        st.caption(subtitle)


def card_art(name: str, issuer_key: str, issuer_label: str) -> str:
    a, b = ISSUER_GRADIENTS.get(issuer_key, ("#0b3f36", "#1b7a66"))
    return (
        f'<div class="td-cardart" style="background:linear-gradient(135deg,{a},{b})">'
        f'<div class="issuer">{escape(issuer_label)}</div><div class="chip"></div>'
        f'<div class="name">{escape(name)}</div></div>'
    )


def footer() -> None:
    st.html(
        '<div class="td-footer">TravelDeal Search · Card terms change often; confirm on the issuer\'s site before you book. '
        "Not financial advice.</div>"
    )
