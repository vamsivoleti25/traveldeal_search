import { describe, expect, it } from 'vitest';
import { catalog } from '../src/engine/catalog';
import { bestPerChannel, compareOptions, computeEarn, evaluate } from '../src/engine/compare';
import type { Booking, Card, UserSettings } from '../src/engine/types';

const card = (id: string): Card => {
  const c = catalog.cards.find((x) => x.id === id);
  if (!c) throw new Error(`missing card ${id}`);
  return c;
};

const cash: UserSettings = { valuationMode: 'cash' };
// Mark broad travel credits used so they don't dominate simple earn-rate tests.
const noCredits: UserSettings = {
  valuationMode: 'cash',
  creditsUsed: {
    'chase-sapphire-reserve:travel-credit': 300,
    'chase-sapphire-preferred:hotel-credit': 100,
    'capital-one-venture-x:travel-credit': 300,
    'citi-strata-premier:hotel-benefit': 100,
    'amex-platinum:hotel-credit': 300,
  },
};

const hotel = (direct: number, portals: Booking['channels'] = []): Booking => ({
  type: 'hotel',
  merchant: 'marriott',
  channels: [{ id: 'direct', kind: 'direct', label: 'Marriott.com', price: direct }, ...portals],
});

describe('catalog', () => {
  it('loads every seed card', () => {
    expect(catalog.cards.length).toBeGreaterThanOrEqual(10);
    expect(new Set(catalog.cards.map((c) => c.id)).size).toBe(catalog.cards.length);
  });
});

describe('earn rules', () => {
  it('Sapphire Reserve earns 8x in Chase Travel and 4x on direct hotels', () => {
    const csr = card('chase-sapphire-reserve');
    const portal = computeEarn(csr, { category: 'hotel', kind: 'portal', prepaid: true }, 100, cash);
    const direct = computeEarn(csr, { category: 'hotel', kind: 'direct', prepaid: false }, 100, cash);
    const ota = computeEarn(csr, { category: 'hotel', kind: 'ota', prepaid: false }, 100, cash);
    expect(portal.points).toBe(800);
    expect(direct.points).toBe(400);
    expect(ota.points).toBe(100); // Expedia etc. is neither direct nor Chase Travel
  });

  it('Sapphire Preferred earns 2x on travel booked direct or via OTAs', () => {
    const csp = card('chase-sapphire-preferred');
    expect(computeEarn(csp, { category: 'flight', kind: 'ota', prepaid: false }, 100, cash).points).toBe(200);
  });

  it('Amex Gold 5x hotels requires a prepaid Amex Travel booking', () => {
    const gold = card('amex-gold');
    expect(computeEarn(gold, { category: 'hotel', kind: 'portal', prepaid: true }, 100, cash).points).toBe(500);
    expect(computeEarn(gold, { category: 'hotel', kind: 'portal', prepaid: false }, 100, cash).points).toBe(100);
  });

  it('co-brand merchant rules only apply to that merchant', () => {
    const boundless = card('marriott-bonvoy-boundless');
    expect(computeEarn(boundless, { category: 'hotel', kind: 'direct', merchant: 'marriott', prepaid: false }, 100, cash).points).toBe(600);
    expect(computeEarn(boundless, { category: 'hotel', kind: 'direct', merchant: 'hilton', prepaid: false }, 100, cash).points).toBe(200);
  });

  it('spend over an annual cap earns the base rate', () => {
    const gold = card('amex-gold');
    const groceryRule = gold.earn.findIndex((r) => r.categories.includes('grocery'));
    const settings: UserSettings = { valuationMode: 'cash', capSpendUsed: { [`amex-gold:${groceryRule}`]: 24_900 } };
    const res = computeEarn(gold, { category: 'grocery', kind: 'direct', prepaid: false }, 300, settings);
    expect(res.points).toBe(100 * 4 + 200 * 1);
    expect(res.notes[0]).toMatch(/annual cap/);
  });
});

describe('channels and credits', () => {
  it('portal channels only pair with cards from that issuer', () => {
    const booking = hotel(300, [{ id: 'c1', kind: 'portal', label: 'Capital One Travel', price: 300, portal: 'capital_one_travel' }]);
    const opts = compareOptions(booking, [card('chase-sapphire-reserve'), card('capital-one-venture-x')], catalog, noCredits);
    const portalCards = opts.filter((o) => o.channelId === 'c1').map((o) => o.cardId);
    expect(portalCards).toEqual(['capital-one-venture-x']);
  });

  it('Citi $100 hotel benefit needs a $500+ stay', () => {
    const premier = card('citi-strata-premier');
    const mk = (price: number): Booking =>
      hotel(price, [{ id: 'citi', kind: 'portal', label: 'Citi Travel', price, portal: 'citi_travel' }]);
    expect(evaluate(mk(450), mk(450).channels[1], premier, catalog, cash).creditsApplied).toBe(0);
    expect(evaluate(mk(600), mk(600).channels[1], premier, catalog, cash).creditsApplied).toBe(100);
  });

  it('credited amounts that earn no points are excluded from earning', () => {
    const vx = card('capital-one-venture-x');
    const booking = hotel(500, [{ id: 'c1', kind: 'portal', label: 'Capital One Travel', price: 500, portal: 'capital_one_travel' }]);
    const opt = evaluate(booking, booking.channels[1], vx, catalog, cash);
    expect(opt.creditsApplied).toBe(300);
    expect(opt.cardPoints).toBe(200 * 10);
  });

  it('partially used credits only apply what is left', () => {
    const vx = card('capital-one-venture-x');
    const booking = hotel(500, [{ id: 'c1', kind: 'portal', label: 'Capital One Travel', price: 500, portal: 'capital_one_travel' }]);
    const settings: UserSettings = { valuationMode: 'cash', creditsUsed: { 'capital-one-venture-x:travel-credit': 250 } };
    expect(evaluate(booking, booking.channels[1], vx, catalog, settings).creditsApplied).toBe(50);
  });

  it('Amex Platinum hotel credit needs an FHR / Hotel Collection tag', () => {
    const plat = card('amex-platinum');
    const base = { id: 'amex', kind: 'portal' as const, label: 'Amex Travel', price: 800, portal: 'amex_travel' as const };
    const plain = hotel(800, [base]);
    const fhr = hotel(800, [{ ...base, tags: ['amex_fhr_thc'] }]);
    expect(evaluate(plain, plain.channels[1], plat, catalog, cash).creditsApplied).toBe(0);
    expect(evaluate(fhr, fhr.channels[1], plat, catalog, cash).creditsApplied).toBe(300);
  });
});

describe('credit toggle', () => {
  it('ignores all credits when applyCredits is false', () => {
    const booking = hotel(500);
    const opt = evaluate(booking, booking.channels[0], card('chase-sapphire-reserve'), catalog, { valuationMode: 'cash', applyCredits: false });
    expect(opt.creditsApplied).toBe(0);
    expect(opt.cardPoints).toBe(2000);
  });
});

describe('loyalty and perks', () => {
  it('direct hotel bookings earn hotel points with elite bonus; portal bookings do not', () => {
    const booking = hotel(200, [{ id: 'chase', kind: 'portal', label: 'Chase Travel', price: 200, portal: 'chase_travel' }]);
    const settings: UserSettings = { ...noCredits, eliteStatus: { marriott: 'gold' } };
    const csr = card('chase-sapphire-reserve');
    const direct = evaluate(booking, booking.channels[0], csr, catalog, settings);
    const portal = evaluate(booking, booking.channels[1], csr, catalog, settings);
    expect(direct.loyaltyPoints).toBe(200 * 10 * 1.25);
    expect(portal.loyaltyPoints).toBe(0);
    expect(portal.warnings.join(' ')).toMatch(/don't earn Marriott Bonvoy/);
  });

  it('airline tickets bought in a portal still earn miles', () => {
    const booking: Booking = {
      type: 'flight',
      merchant: 'delta',
      channels: [{ id: 'amex', kind: 'portal', label: 'Amex Travel', price: 400, portal: 'amex_travel' }],
    };
    const opt = evaluate(booking, booking.channels[0], card('amex-platinum'), catalog, cash);
    expect(opt.loyaltyPoints).toBe(2000);
    expect(opt.cardPoints).toBe(2000);
  });

  it('elite perk value only counts when the program honors it', () => {
    const booking: Booking = {
      ...hotel(300, [{ id: 'chase', kind: 'portal', label: 'Chase Travel', price: 300, portal: 'chase_travel' }]),
      directPerksValue: 40,
    };
    const csr = card('chase-sapphire-reserve');
    expect(evaluate(booking, booking.channels[0], csr, catalog, noCredits).perksValue).toBe(40);
    expect(evaluate(booking, booking.channels[1], csr, catalog, noCredits).perksValue).toBe(0);
  });
});

describe('gift cards', () => {
  it('applies the discount and earns in the purchase category', () => {
    const booking = hotel(500, [
      { id: 'gc', kind: 'giftcard', label: 'Marriott gift card', price: 500, giftCardDiscountPct: 10, giftCardPurchaseCategory: 'grocery' },
    ]);
    const opt = evaluate(booking, booking.channels[1], card('amex-gold'), catalog, cash);
    expect(opt.amountCharged).toBe(450);
    expect(opt.cardPoints).toBe(450 * 4);
    expect(opt.loyaltyPoints).toBe(5000); // the stay itself still earns Bonvoy points
  });
});

describe('ranking', () => {
  it('sorts by effective cost and picks one card per channel', () => {
    const booking = hotel(300, [{ id: 'chase', kind: 'portal', label: 'Chase Travel', price: 300, portal: 'chase_travel' }]);
    const opts = compareOptions(booking, [card('chase-sapphire-reserve'), card('chase-freedom-unlimited')], catalog, noCredits);
    for (let i = 1; i < opts.length; i++) expect(opts[i].effectiveCost).toBeGreaterThanOrEqual(opts[i - 1].effectiveCost);
    const best = bestPerChannel(opts);
    expect(best).toHaveLength(2);
    expect(best.every((o) => o.cardId === 'chase-sapphire-reserve')).toBe(true);
  });

  it('effective cost equals charge minus every value line', () => {
    const booking = hotel(250);
    const o = evaluate(booking, booking.channels[0], card('chase-sapphire-reserve'), catalog, cash);
    const expected = o.amountCharged - o.creditsApplied - o.cardPointsValue - o.loyaltyValue - o.perksValue;
    expect(o.effectiveCost).toBeCloseTo(expected, 1);
  });

  it('skips channels with no price entered', () => {
    const booking = hotel(0, [{ id: 'chase', kind: 'portal', label: 'Chase Travel', price: 200, portal: 'chase_travel' }]);
    const opts = compareOptions(booking, [card('chase-sapphire-reserve')], catalog, cash);
    expect(opts.map((o) => o.channelId)).toEqual(['chase']);
  });
});

describe('dated rules, conditions and wider catalog', () => {
  const at = (today: string): UserSettings => ({ valuationMode: 'cash', today });

  it('rotating categories only apply inside their dates', () => {
    const flex = card('chase-freedom-flex');
    const ctx = (today: string) => ({ category: 'grocery' as const, kind: 'direct' as const, prepaid: false, today });
    expect(computeEarn(flex, ctx('2026-11-15'), 100, at('2026-11-15')).points).toBe(500);
    expect(computeEarn(flex, ctx('2027-01-15'), 100, at('2027-01-15')).points).toBe(100);
  });

  it('limited-time rates hand over to the next rate when they end', () => {
    const aeroplan = card('chase-aeroplan');
    const ctx = (today: string) => ({ category: 'dining' as const, kind: 'direct' as const, prepaid: false, today });
    expect(computeEarn(aeroplan, ctx('2026-12-01'), 100, at('2026-12-01')).points).toBe(300);
    expect(computeEarn(aeroplan, ctx('2027-02-01'), 100, at('2027-02-01')).points).toBe(200);
  });

  it('surfaces conditions as notes', () => {
    const custom = card('citi-custom-cash');
    const res = computeEarn(custom, { category: 'gas', kind: 'direct', prepaid: false }, 100, cash);
    expect(res.points).toBe(500);
    expect(res.notes.join(' ')).toMatch(/top eligible spend category/);
  });

  it('"everything" rules cover any purchase up to their cap', () => {
    const bbp = card('amex-blue-business-plus');
    expect(computeEarn(bbp, { category: 'hotel', kind: 'ota', prepaid: false }, 100, cash).points).toBe(200);
  });

  it('quarterly caps are labeled in the note', () => {
    const go = card('us-bank-altitude-go');
    const res = computeEarn(go, { category: 'dining', kind: 'direct', prepaid: false }, 2500, cash);
    expect(res.points).toBe(2000 * 4 + 500);
    expect(res.notes.join(' ')).toMatch(/quarterly cap/);
  });

  it('merchant-specific credits only apply at that merchant', () => {
    const surpass = card('hilton-honors-surpass');
    const hilton: Booking = { type: 'hotel', merchant: 'hilton', channels: [{ id: 'd', kind: 'direct', label: 'Hilton', price: 300 }] };
    const marriott: Booking = { ...hilton, merchant: 'marriott' };
    expect(evaluate(hilton, hilton.channels[0], surpass, catalog, cash).creditsApplied).toBe(50);
    expect(evaluate(marriott, marriott.channels[0], surpass, catalog, cash).creditsApplied).toBe(0);
  });

  it('Bilt portal pairs only with Bilt cards', () => {
    const booking = hotel(300, [{ id: 'bilt', kind: 'portal', label: 'Bilt Travel', price: 300, portal: 'bilt_travel' }]);
    const opts = compareOptions(booking, [card('bilt-obsidian'), card('amex-gold')], catalog, noCredits);
    expect(opts.filter((o) => o.channelId === 'bilt').map((o) => o.cardId)).toEqual(['bilt-obsidian']);
  });

  it('Ink Business Cash earns 5x on gift cards bought at office supply stores', () => {
    const booking = hotel(400, [
      { id: 'gc', kind: 'giftcard', label: 'Gift card', price: 400, giftCardDiscountPct: 9, giftCardPurchaseCategory: 'office_supply' },
    ]);
    const opt = evaluate(booking, booking.channels[1], card('chase-ink-business-cash'), catalog, cash);
    expect(opt.amountCharged).toBe(364);
    expect(opt.cardPoints).toBe(364 * 5);
  });
});
