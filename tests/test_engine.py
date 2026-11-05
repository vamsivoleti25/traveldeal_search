import pytest

from traveldeal.catalog import load_catalog
from traveldeal.engine import PurchaseContext, best_per_channel, compare_options, compute_earn, evaluate
from traveldeal.models import Booking, Card, Channel, UserSettings

catalog = load_catalog()
CASH = UserSettings(valuation_mode="cash")
NO_CREDITS = UserSettings(
    valuation_mode="cash",
    credits_used={
        "chase-sapphire-reserve:travel-credit": 300,
        "chase-sapphire-preferred:hotel-credit": 100,
        "capital-one-venture-x:travel-credit": 300,
        "citi-strata-premier:hotel-benefit": 100,
        "amex-platinum:hotel-credit": 300,
    },
)


def card(card_id: str) -> Card:
    c = catalog.card(card_id)
    assert c is not None, card_id
    return c


def ctx(category, kind, prepaid=False, merchant=None, today="2026-11-15"):
    return PurchaseContext(category, kind, prepaid, merchant, today)


def hotel(direct: float, extra: list[Channel] | None = None) -> Booking:
    return Booking("hotel", [Channel("direct", "direct", "Marriott.com", direct), *(extra or [])], merchant="marriott")


def portal(id_, label, price, portal_id, **kw):
    return Channel(id_, "portal", label, price, portal=portal_id, **kw)


class TestCatalog:
    def test_loads_every_card_with_unique_ids(self):
        assert len(catalog.cards) >= 90
        assert len({c.id for c in catalog.cards}) == len(catalog.cards)


class TestEarnRules:
    def test_sapphire_reserve_portal_direct_ota(self):
        csr = card("chase-sapphire-reserve")
        assert compute_earn(csr, ctx("hotel", "portal", True), 100, CASH).points == 800
        assert compute_earn(csr, ctx("hotel", "direct"), 100, CASH).points == 400
        assert compute_earn(csr, ctx("hotel", "ota"), 100, CASH).points == 100

    def test_sapphire_preferred_2x_direct_or_ota_travel(self):
        assert compute_earn(card("chase-sapphire-preferred"), ctx("flight", "ota"), 100, CASH).points == 200

    def test_amex_gold_5x_requires_prepaid(self):
        gold = card("amex-gold")
        assert compute_earn(gold, ctx("hotel", "portal", True), 100, CASH).points == 500
        assert compute_earn(gold, ctx("hotel", "portal", False), 100, CASH).points == 100

    def test_cobrand_merchant_rules(self):
        b = card("marriott-bonvoy-boundless")
        assert compute_earn(b, ctx("hotel", "direct", merchant="marriott"), 100, CASH).points == 600
        assert compute_earn(b, ctx("hotel", "direct", merchant="hilton"), 100, CASH).points == 200

    def test_cap_overflow_earns_base(self):
        gold = card("amex-gold")
        idx = next(i for i, r in enumerate(gold.earn) if "grocery" in r.categories)
        s = UserSettings(cap_spend_used={f"amex-gold:{idx}": 24_900})
        res = compute_earn(gold, ctx("grocery", "direct"), 300, s)
        assert res.points == 100 * 4 + 200 * 1
        assert "annual cap" in res.notes[0]


class TestChannelsAndCredits:
    def test_portal_pairs_only_with_issuer(self):
        b = hotel(300, [portal("c1", "Capital One Travel", 300, "capital_one_travel")])
        opts = compare_options(b, [card("chase-sapphire-reserve"), card("capital-one-venture-x")], catalog, NO_CREDITS)
        assert [o.card_id for o in opts if o.channel_id == "c1"] == ["capital-one-venture-x"]

    def test_citi_benefit_needs_500(self):
        premier = card("citi-strata-premier")
        for price, expected in ((450, 0), (600, 100)):
            b = hotel(price, [portal("citi", "Citi Travel", price, "citi_travel")])
            assert evaluate(b, b.channels[1], premier, catalog, CASH).credits_applied == expected

    def test_credited_amount_excluded_from_earning(self):
        b = hotel(500, [portal("c1", "Capital One Travel", 500, "capital_one_travel")])
        o = evaluate(b, b.channels[1], card("capital-one-venture-x"), catalog, CASH)
        assert o.credits_applied == 300
        assert o.card_points == 2000

    def test_partially_used_credit(self):
        b = hotel(500, [portal("c1", "Capital One Travel", 500, "capital_one_travel")])
        s = UserSettings(credits_used={"capital-one-venture-x:travel-credit": 250})
        assert evaluate(b, b.channels[1], card("capital-one-venture-x"), catalog, s).credits_applied == 50

    def test_platinum_credit_needs_fhr_tag(self):
        plain = hotel(800, [portal("amex", "Amex Travel", 800, "amex_travel")])
        fhr = hotel(800, [portal("amex", "Amex Travel", 800, "amex_travel", tags=("amex_fhr_thc",))])
        plat = card("amex-platinum")
        assert evaluate(plain, plain.channels[1], plat, catalog, CASH).credits_applied == 0
        assert evaluate(fhr, fhr.channels[1], plat, catalog, CASH).credits_applied == 300

    def test_credit_toggle_off(self):
        b = hotel(500)
        o = evaluate(b, b.channels[0], card("chase-sapphire-reserve"), catalog, UserSettings(apply_credits=False))
        assert o.credits_applied == 0
        assert o.card_points == 2000


class TestLoyalty:
    def test_hotel_points_direct_not_portal(self):
        b = hotel(200, [portal("chase", "Chase Travel", 200, "chase_travel")])
        s = UserSettings(credits_used=NO_CREDITS.credits_used, elite_status={"marriott": "gold"})
        csr = card("chase-sapphire-reserve")
        assert evaluate(b, b.channels[0], csr, catalog, s).loyalty_points == 2500
        p = evaluate(b, b.channels[1], csr, catalog, s)
        assert p.loyalty_points == 0
        assert "don't earn Marriott Bonvoy" in " ".join(p.warnings)

    def test_airline_portal_tickets_earn_miles(self):
        b = Booking("flight", [portal("amex", "Amex Travel", 400, "amex_travel")], merchant="delta")
        o = evaluate(b, b.channels[0], card("amex-platinum"), catalog, CASH)
        assert o.loyalty_points == 2000
        assert o.card_points == 2000

    def test_perks_only_where_honored(self):
        b = hotel(300, [portal("chase", "Chase Travel", 300, "chase_travel")])
        b.direct_perks_value = 40
        csr = card("chase-sapphire-reserve")
        assert evaluate(b, b.channels[0], csr, catalog, NO_CREDITS).perks_value == 40
        assert evaluate(b, b.channels[1], csr, catalog, NO_CREDITS).perks_value == 0


class TestGiftCards:
    def test_discount_and_purchase_category(self):
        b = hotel(500, [Channel("gc", "giftcard", "Gift card", 500, gift_card_discount_pct=10, gift_card_purchase_category="grocery")])
        o = evaluate(b, b.channels[1], card("amex-gold"), catalog, CASH)
        assert o.amount_charged == 450
        assert o.card_points == 1800
        assert o.loyalty_points == 5000

    def test_ink_cash_office_supply(self):
        b = hotel(400, [Channel("gc", "giftcard", "Gift card", 400, gift_card_discount_pct=9, gift_card_purchase_category="office_supply")])
        o = evaluate(b, b.channels[1], card("chase-ink-business-cash"), catalog, CASH)
        assert o.amount_charged == 364
        assert o.card_points == 364 * 5


class TestRanking:
    def test_sorted_and_best_per_channel(self):
        b = hotel(300, [portal("chase", "Chase Travel", 300, "chase_travel")])
        opts = compare_options(b, [card("chase-sapphire-reserve"), card("chase-freedom-unlimited")], catalog, NO_CREDITS)
        costs = [o.effective_cost for o in opts]
        assert costs == sorted(costs)
        best = best_per_channel(opts)
        assert len(best) == 2 and all(o.card_id == "chase-sapphire-reserve" for o in best)

    def test_accounting_identity(self):
        b = hotel(250)
        o = evaluate(b, b.channels[0], card("chase-sapphire-reserve"), catalog, CASH)
        expected = o.amount_charged - o.credits_applied - o.card_points_value - o.loyalty_value - o.perks_value
        assert o.effective_cost == pytest.approx(expected, abs=0.02)

    def test_skips_empty_prices(self):
        b = hotel(0, [portal("chase", "Chase Travel", 200, "chase_travel")])
        assert [o.channel_id for o in compare_options(b, [card("chase-sapphire-reserve")], catalog, CASH)] == ["chase"]

    def test_worked_example_from_docs(self):
        b = hotel(420, [portal("chase", "Chase Travel", 405, "chase_travel")])
        opts = compare_options(b, [card("chase-sapphire-reserve")], catalog, CASH)
        assert [(o.channel_id, o.effective_cost) for o in opts] == [("direct", 85.8), ("chase", 96.6)]


class TestDatedRulesAndConditions:
    def test_rotating_category_dates(self):
        flex = card("chase-freedom-flex")
        assert compute_earn(flex, ctx("grocery", "direct", today="2026-11-15"), 100, CASH).points == 500
        assert compute_earn(flex, ctx("grocery", "direct", today="2027-01-15"), 100, CASH).points == 100

    def test_limited_time_handover(self):
        ap = card("chase-aeroplan")
        assert compute_earn(ap, ctx("dining", "direct", today="2026-12-01"), 100, CASH).points == 300
        assert compute_earn(ap, ctx("dining", "direct", today="2027-02-01"), 100, CASH).points == 200

    def test_conditions_surface(self):
        res = compute_earn(card("citi-custom-cash"), ctx("gas", "direct"), 100, CASH)
        assert res.points == 500
        assert "top eligible spend category" in " ".join(res.notes)

    def test_everything_rule(self):
        assert compute_earn(card("amex-blue-business-plus"), ctx("hotel", "ota"), 100, CASH).points == 200

    def test_quarterly_cap_label(self):
        res = compute_earn(card("us-bank-altitude-go"), ctx("dining", "direct"), 2500, CASH)
        assert res.points == 2000 * 4 + 500
        assert "quarterly cap" in " ".join(res.notes)

    def test_merchant_credit(self):
        surpass = card("hilton-honors-surpass")
        hilton = Booking("hotel", [Channel("d", "direct", "Hilton", 300)], merchant="hilton")
        marriott = Booking("hotel", [Channel("d", "direct", "Marriott", 300)], merchant="marriott")
        assert evaluate(hilton, hilton.channels[0], surpass, catalog, CASH).credits_applied == 50
        assert evaluate(marriott, marriott.channels[0], surpass, catalog, CASH).credits_applied == 0

    def test_bilt_portal(self):
        b = hotel(300, [portal("bilt", "Bilt Travel", 300, "bilt_travel")])
        opts = compare_options(b, [card("bilt-obsidian"), card("amex-gold")], catalog, NO_CREDITS)
        assert [o.card_id for o in opts if o.channel_id == "bilt"] == ["bilt-obsidian"]
