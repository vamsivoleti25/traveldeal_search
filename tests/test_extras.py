"""v0.5 features: stacking extras, travel benefits, foreign currency, and points vs cash."""

import pytest

from traveldeal.catalog import load_catalog
from traveldeal.engine import compare_options, evaluate
from traveldeal.models import Booking, CardOffer, Channel, UserSettings
from traveldeal.redeem import best_transfer_ratio, certificate_matches, redemption_options

catalog = load_catalog()
TODAY = "2026-11-15"
S = UserSettings(valuation_mode="cash", apply_credits=False, today=TODAY)


def card(cid):
    c = catalog.card(cid)
    assert c is not None, cid
    return c


def line(option, startswith):
    return next(i.amount for i in option.breakdown if i.label.startswith(startswith))


# ---------------------------------------------------------------- foreign currency
def test_foreign_transaction_fee_added_only_for_cards_that_charge_one():
    b = Booking("hotel", [Channel("direct", "direct", "Hotel site", 500, foreign_currency="EUR", foreign_price=460)])
    dc = evaluate(b, b.channels[0], card("citi-double-cash"), catalog, S)
    csr = evaluate(b, b.channels[0], card("chase-sapphire-reserve"), catalog, S)
    assert line(dc, "Foreign transaction fee") == 15.0  # 3% of $500
    assert not any(i.label.startswith("Foreign transaction fee") for i in csr.breakdown)
    assert "460.00 EUR" in dc.breakdown[0].label


def test_unverified_foreign_fee_warns_instead_of_guessing():
    b = Booking("hotel", [Channel("direct", "direct", "Hotel site", 200, foreign_currency="GBP", foreign_price=150)])
    o = evaluate(b, b.channels[0], card("citi-strata"), catalog, S)
    assert any("foreign transaction fee" in w for w in o.warnings)


def test_portal_prices_in_usd_never_get_a_foreign_fee():
    ch = Channel("chase", "portal", "Chase Travel", 300, portal="chase_travel", foreign_currency="EUR")
    o = evaluate(Booking("hotel", [ch]), ch, card("chase-freedom-flex"), catalog, S)
    assert not any(i.label.startswith("Foreign") for i in o.breakdown)


# ---------------------------------------------------------------- stacking
def test_shopping_portal_cashback_on_direct_and_ota_only():
    direct = Channel("direct", "direct", "Hilton.com", 400, cashback_pct=5)
    o = evaluate(Booking("hotel", [direct], merchant="hilton"), direct, card("citi-double-cash"), catalog, S)
    assert line(o, "Shopping portal cashback") == -20.0
    base = evaluate(Booking("hotel", [Channel("direct", "direct", "Hilton.com", 400)], merchant="hilton"),
                    Channel("direct", "direct", "Hilton.com", 400), card("citi-double-cash"), catalog, S)
    assert o.effective_cost == pytest.approx(base.effective_cost - 20)


def test_card_linked_offer_needs_matching_card_direct_channel_and_min_spend():
    direct = Channel("direct", "direct", "Hilton.com", 300)
    b = Booking("hotel", [direct], merchant="hilton", offers=[CardOffer("amex-gold", 50, 250)])
    gold = evaluate(b, direct, card("amex-gold"), catalog, S)
    assert line(gold, "Card offer") == -50.0
    other = evaluate(b, direct, card("chase-sapphire-reserve"), catalog, S)
    assert not any(i.label.startswith("Card offer") for i in other.breakdown)
    small = Booking("hotel", [Channel("direct", "direct", "Hilton.com", 200)], merchant="hilton", offers=[CardOffer("amex-gold", 50, 250)])
    assert not any(i.label.startswith("Card offer") for i in evaluate(small, small.channels[0], card("amex-gold"), catalog, S).breakdown)


# ---------------------------------------------------------------- benefits
def test_delta_card_bags_apply_to_any_card_paying_but_united_needs_its_card():
    delta = Booking("flight", [Channel("direct", "direct", "delta.com", 600)], merchant="delta",
                    travelers=3, checked_bags=1, bag_fee=40, flight_legs=2)
    wallet = [card("delta-skymiles-gold"), card("chase-sapphire-reserve")]
    by_csr = evaluate(delta, delta.channels[0], card("chase-sapphire-reserve"), catalog, S, wallet=wallet)
    assert line(by_csr, "Free checked bags") == -240.0  # 3 people x 1 bag x $40 x 2 directions

    united = Booking("flight", [Channel("direct", "direct", "united.com", 600)], merchant="united",
                     travelers=2, checked_bags=1, bag_fee=40, flight_legs=2)
    wallet = [card("united-explorer"), card("chase-sapphire-reserve")]
    with_explorer = evaluate(united, united.channels[0], card("united-explorer"), catalog, S, wallet=wallet)
    with_csr = evaluate(united, united.channels[0], card("chase-sapphire-reserve"), catalog, S, wallet=wallet)
    assert line(with_explorer, "Free checked bags") == -160.0  # you + 1 companion
    assert not any(i.label.startswith("Free checked bags") for i in with_csr.breakdown)


def test_bags_capped_at_card_companions():
    b = Booking("flight", [Channel("direct", "direct", "united.com", 900)], merchant="united",
                travelers=5, checked_bags=2, bag_fee=40, flight_legs=1)
    o = evaluate(b, b.channels[0], card("united-quest"), catalog, S, wallet=[card("united-quest")])
    assert line(o, "Free checked bags") == -160.0  # 2 people x 2 bags x $40 x 1 direction


def test_primary_rental_coverage_saves_the_counter_waiver_within_limits():
    b = Booking("car_rental", [Channel("direct", "direct", "Hertz", 350)], rental_days=5, rental_cdw_per_day=25)
    csr = evaluate(b, b.channels[0], card("chase-sapphire-reserve"), catalog, S)
    amex = evaluate(b, b.channels[0], card("amex-platinum"), catalog, S)
    assert line(csr, "Skip the counter's collision waiver") == -125.0
    assert not any("collision waiver" in i.label for i in amex.breakdown)
    long = Booking("car_rental", [Channel("direct", "direct", "Hertz", 900)], rental_days=20, rental_cdw_per_day=25)
    vx = evaluate(long, long.channels[0], card("capital-one-venture-x"), catalog, S)
    assert not any("collision waiver" in i.label for i in vx.breakdown)
    assert any("up to 15 days" in w for w in vx.warnings)


def test_the_edit_credit_is_250_per_booking_and_needs_two_nights():
    s = UserSettings(valuation_mode="cash", apply_credits=True, today=TODAY,
                     credits_used={"chase-sapphire-reserve:travel-credit": 300})
    edit = Channel("chase", "portal", "Chase Travel", 900, portal="chase_travel", prepaid=True, tags=("chase_edit",))
    two = evaluate(Booking("hotel", [edit], nights=2), edit, card("chase-sapphire-reserve"), catalog, s)
    one = evaluate(Booking("hotel", [edit], nights=1), edit, card("chase-sapphire-reserve"), catalog, s)
    assert line(two, "The Edit") == -250.0
    assert not any(i.label.startswith("The Edit") for i in one.breakdown)


# ---------------------------------------------------------------- points vs cash
def test_transfer_ratio_depends_on_cards_held_and_bonuses():
    csr, csp, flex = card("chase-sapphire-reserve"), card("chase-sapphire-preferred"), card("chase-freedom-flex")
    assert best_transfer_ratio("chase_ur", "hyatt", [csr], catalog, TODAY)[0] == 1.0
    assert best_transfer_ratio("chase_ur", "hyatt", [csp], catalog, TODAY)[0] == 0.75
    assert best_transfer_ratio("chase_ur", "hyatt", [flex], catalog, TODAY)[0] == 0.0  # Freedom alone can't transfer
    ratio, note = best_transfer_ratio("chase_ur", "ihg", [csr], catalog, TODAY)
    assert ratio == pytest.approx(1.8) and "80%" in note
    assert best_transfer_ratio("chase_ur", "ihg", [csr], catalog, "2026-12-04")[0] == 1.0  # bonus over


def test_redemption_options_price_points_at_your_valuation():
    wallet = [card("chase-sapphire-reserve"), card("world-of-hyatt")]
    opts = redemption_options("hyatt", cash_price=450, award_points=25000, award_taxes=0, wallet=wallet,
                              data=catalog, settings=S)
    kinds = {o.kind: o for o in opts}
    t = kinds["transfer"]
    assert t.points == 25000 and t.value_cpp == 1.8  # $450 / 25,000
    assert t.cost == pytest.approx(25000 * t.your_cpp / 100)
    assert kinds["program"].points == 25000
    p = kinds["portal"]
    assert p.points == 45000 and p.value_cpp == 1.0  # Chase points at 1 cent in the portal
    assert opts == sorted(opts, key=lambda o: o.cost)


def test_transfer_rounds_up_to_the_issuers_increment():
    wallet = [card("amex-gold")]
    opts = redemption_options("jetblue", 300, 12500, 5.6, wallet, catalog, S)
    t = next(o for o in opts if o.kind == "transfer")
    assert t.points == 16000  # 12,500 / 0.8 = 15,625, rounded up to 1,000s


def test_free_night_certificates_check_the_points_cap():
    wallet = [card("marriott-bonvoy-boundless"), card("world-of-hyatt")]
    fits = certificate_matches("marriott", cash_price=600, nights=2, award_points=60000, wallet=wallet)
    assert fits[0].covers is True and fits[0].saves == 300.0
    too_pricey = certificate_matches("marriott", 600, 2, 100000, wallet)
    assert too_pricey[0].covers is False
    hyatt = certificate_matches("hyatt", 400, 1, 0, wallet)
    assert len(hyatt) == 2 and hyatt[0].covers is None  # category-based; we can't check it


def test_compare_options_passes_the_wallet_for_bag_benefits():
    b = Booking("flight", [Channel("direct", "direct", "delta.com", 500)], merchant="delta",
                travelers=2, checked_bags=1, bag_fee=45, flight_legs=2)
    opts = compare_options(b, [card("delta-skymiles-platinum"), card("citi-double-cash")], catalog, S)
    assert all(any(i.label.startswith("Free checked bags") for i in o.breakdown) for o in opts)


# ---------------------------------------------------------------- benefit reset dates
from datetime import date  # noqa: E402

from traveldeal.benefits import credit_statuses, period_end  # noqa: E402


def test_period_end_dates():
    d = date(2026, 11, 15)
    assert period_end("calendar_year", d) == date(2026, 12, 31)
    assert period_end("semiannual", date(2026, 3, 1)) == date(2026, 6, 30)
    assert period_end("semiannual", d) == date(2026, 12, 31)
    assert period_end("quarterly", d) == date(2026, 12, 31)
    assert period_end("quarterly", date(2026, 2, 10)) == date(2026, 3, 31)
    assert period_end("anniversary_year", d) is None
    assert period_end("anniversary_year", d, anniversary_month=3) == date(2027, 2, 28)
    assert period_end("anniversary_year", date(2026, 1, 5), anniversary_month=3) == date(2026, 2, 28)


def test_credit_statuses_track_used_and_sort_by_urgency():
    s = UserSettings(credits_used={"chase-sapphire-reserve:the-edit": 250, "hilton-honors-aspire:resort-credit": 200})
    st_ = credit_statuses([card("chase-sapphire-reserve"), card("hilton-honors-aspire")], s, date(2026, 11, 15))
    edit = next(x for x in st_ if x.credit.id == "the-edit")
    assert edit.remaining == 250 and edit.days_left == 46
    assert st_[-1].remaining == 0  # used-up credits go last


def test_hotel_points_are_never_offered_as_portal_redemptions():
    opts = redemption_options("hyatt", 500, 25000, 0, [card("hilton-honors-aspire"), card("chase-sapphire-reserve")], catalog, S)
    assert [o.currency_id for o in opts if o.kind == "portal"] == ["chase_ur"]


# ---------------------------------------------------------------- gift cards: where to buy, which card
from traveldeal.giftcard_buy import best_card, buy_options  # noqa: E402
from traveldeal.giftcards import GiftCardBrand, GiftCardSeller, load_gift_cards  # noqa: E402


def test_snapshot_names_the_top_seller_for_travel_brands():
    snap = load_gift_cards()
    for b in (x for x in snap.brands if x.travel):
        assert b.sellers, b.name
        assert b.best_seller.discount_pct == b.discount_pct, b.name


def test_buy_options_pick_your_best_card_per_venue():
    brand = GiftCardBrand("x", "Example Air", "airline", True, 10, "https://example.com",
                          sellers=(GiftCardSeller("Seller A", "a", 10.0, ("100-Day Guarantee",)),
                                   GiftCardSeller("Seller B", "b", 4.0)))
    wallet = [card("citi-double-cash"), card("amex-gold")]
    opts = buy_options(brand, 500, wallet, catalog, S)
    a = next(o for o in opts if o.venue == "Seller A")
    assert a.paid == 450.0
    assert a.best.card_id == "citi-double-cash"  # 2% beats the Gold's 1x online
    assert a.net_cost == pytest.approx(450 - 9.0)  # 2% of $450
    assert a.total_savings_pct == pytest.approx(11.8)
    # The Amex Gold earns 4x at grocery stores: worth listing only if it beats the best online deal.
    grocery = [o for o in opts if o.venue == "Grocery store"]
    assert not grocery  # 4x at 0.6 cents (cash value) = 2.4% < 11.8%
    rich = UserSettings(valuation_mode="cash", apply_credits=False, today=TODAY, cpp_overrides={"amex_mr": 4.0})
    rich_opts = buy_options(brand, 500, wallet, catalog, rich)
    grocery = [o for o in rich_opts if o.venue == "Grocery store"]
    assert grocery and grocery[0].best.card_id == "amex-gold"
    assert grocery[0].total_savings_pct == pytest.approx(16.0)  # 4x at 4 cents on $500, no discount
    assert rich_opts[0].venue == "Grocery store"  # beats Seller A's 10% + Gold 1x online (13.6%)


def test_best_card_uses_store_category():
    b = best_card("office_supply", 500, [card("chase-ink-business-cash"), card("citi-double-cash")], catalog, S)
    assert b.card_id == "chase-ink-business-cash" and b.rate == 5
