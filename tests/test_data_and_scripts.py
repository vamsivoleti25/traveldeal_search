import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from giftcard_parse import html_to_text, parse_discount_page  # noqa: E402
from validate_data import check, report  # noqa: E402

from traveldeal.giftcards import best_gift_card_for, load_gift_cards  # noqa: E402

PAGE = """
<html><head><meta name="description" content="Marriott gift cards up to 9% off from 5 sellers"></head>
<body>
  <script>var x = "current discount 99%";</script>
  <section><h2>Current discount</h2><p class="big">9<span>%</span></p></section>
  <dl><dt>12-month average</dt><dd>8.2%</dd><dt>Highest recorded</dt><dd>12%</dd></dl>
</body></html>"""


def test_card_data_is_valid():
    result = check(today="2026-11-05")
    assert result["errors"] == []
    assert int(result["count"][0]) >= 90


def test_report_flags_expired_rules_later():
    result = check(today="2027-01-15")
    assert any("Freedom Flex" in e for e in result["expired"])
    assert "Expired dated rules" in report(result, "2027-01-15")


def test_parser_reads_labels_and_ignores_scripts():
    p = parse_discount_page(PAGE)
    assert (p.discount_pct, p.avg_12m_pct, p.high_12m_pct) == (9, 8.2, 12)


def test_parser_meta_fallback_and_no_guessing():
    assert parse_discount_page('<meta name="description" content="Save up to 6.5% on Airbnb">').discount_pct == 6.5
    assert parse_discount_page("<body>Out of stock</body>").discount_pct is None
    assert parse_discount_page("<p>Current discount 95%</p>").discount_pct is None


def test_html_to_text():
    assert html_to_text("<b>A&amp;B</b>&nbsp;10&#37;") == "A&B 10%"


def test_gift_card_snapshot_is_sane():
    snap = load_gift_cards()
    assert snap.as_of and len(snap.brands) > 20
    assert all(0 < b.discount_pct <= 60 and b.live_url.startswith("https://") for b in snap.brands)
    assert best_gift_card_for("marriott").name == "Marriott"
    assert best_gift_card_for("nope") is None
