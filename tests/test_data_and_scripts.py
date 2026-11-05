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


# Two seller rows copied from a real CardBear brand page (Nov 2026): one in stock, one out of stock.
SELLER_ROWS = """
<div role="row" class="grid items-center bg-white"> <div role="cell" class="min-w-0"> <div class="flex min-h-5 min-w-0 items-center">
<img src="https://www.cardbear.com/img/gcstore/arbitrage.webp" alt="Arbitrage" width="72" height="28" loading="lazy"> </div>
<div class="min-w-0"> <div class="mt-1 text-xs leading-4 text-slate-500 min-[900px]:hidden"> 120-Day Guarantee </div>
<div class="mt-1 line-clamp-2 text-xs leading-4 text-slate-500 min-[900px]:hidden">Quick Delivery</div> </div> </div>
<div role="cell" class="text-center"> <span class="block whitespace-nowrap text-2xl font-bold"> 6<span>%</span> </span> </div>
<div role="cell" class="hidden text-sm leading-5 text-slate-600 min-[900px]:block"> <div>120-Day Guarantee</div> <div>Quick Delivery</div> </div>
<div role="cell" class="text-right md:text-center"> <a href="https://www.cardbear.com/r.php?storeid=2&amp;giftstore=arbitrage" target="_blank"
 aria-label="View Arbitrage offer"> <span>View Offer</span> </a> </div> </div>
<div role="row" class="grid grid-cols-[minmax(0,0.9fr)_4.5rem_auto] bg-white"> <div role="cell" class="min-w-0">
<img src="https://www.cardbear.com/img/gcstore/raise.webp" alt="Raise" width="72"> </div>
<div role="cell" class="text-center"> <span> 11.5<span>%</span> </span> </div>
<div role="cell" class="hidden text-sm"> <div>90-Day Guarantee</div> <div>Includes protection fee</div> </div>
<div role="cell" class="text-right"> <a href="https://www.cardbear.com/r.php?storeid=726&amp;giftstore=raise">View Offer</a> </div> </div>
<div role="row" class="grid bg-white" hidden="" id="unavailable-offer-row-0" data-unavailable-offer-row=""> <div role="cell" class="min-w-0">
<img src="https://www.cardbear.com/img/gcstore/bestbuy.webp" alt="BestBuy" width="72"> </div>
<div role="cell" class="text-center"> <span class="font-bold text-slate-400">—</span> </div>
<div role="cell" class="hidden text-sm"> <div>Official Retailer</div> </div>
<div role="cell" class="text-right"> <span> Out of Stock </span> </div> </div>
<p>Twelve-month average 6.8%. Highest recorded discount 12%.</p>
"""


def test_parser_reads_sellers_best_first_and_skips_out_of_stock():
    from giftcard_parse import parse_sellers

    sellers = parse_sellers(SELLER_ROWS)
    assert [(s.name, s.slug, s.discount_pct) for s in sellers] == [("Raise", "raise", 11.5), ("Arbitrage", "arbitrage", 6.0)]
    assert sellers[1].notes == ["120-Day Guarantee", "Quick Delivery"]
    p = parse_discount_page(SELLER_ROWS)
    assert (p.avg_12m_pct, p.high_12m_pct) == (6.8, 12)
