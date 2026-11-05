// The comparison engine. Pure functions only: same inputs always give the same output.
//
// For every (booking channel x card you hold) pair it computes:
//   effective cost = amount charged
//                    - statement credits applied
//                    - value of card points earned
//                    - value of airline/hotel loyalty points earned
//                    - value of elite perks (direct bookings)
// and ranks the options from cheapest to most expensive.

import type {
  Booking,
  BookingType,
  CapPeriod,
  CatalogData,
  Card,
  Category,
  Channel,
  ChannelKind,
  Credit,
  EarnRule,
  LineItem,
  LoyaltyProgram,
  Option,
  RuleChannelSpec,
  UserSettings,
} from './types';

const TRAVEL_TYPES: BookingType[] = ['flight', 'hotel', 'car_rental', 'vacation_rental', 'cruise', 'attraction'];

const CAP_PERIOD_LABEL: Record<CapPeriod, string> = {
  billing_cycle: 'billing-cycle',
  month: 'monthly',
  quarter: 'quarterly',
  calendar_year: 'annual',
  anniversary_year: 'annual',
};

const round2 = (n: number) => Math.round(n * 100) / 100;

export function categoryMatches(ruleCategories: Category[], category: Category): boolean {
  if (ruleCategories.includes(category) || ruleCategories.includes('everything')) return true;
  return ruleCategories.includes('travel') && (TRAVEL_TYPES as Category[]).includes(category);
}

/** Gift card purchases happen at a store, so they match like a direct purchase. */
function effectiveChannelKind(kind: ChannelKind): Exclude<ChannelKind, 'giftcard'> {
  return kind === 'giftcard' ? 'direct' : kind;
}

export function channelMatches(spec: RuleChannelSpec, kind: ChannelKind): boolean {
  const k = effectiveChannelKind(kind);
  if (spec === 'any') return true;
  return Array.isArray(spec) ? spec.includes(k) : spec === k;
}

/** A portal channel can only be paid with a card from that portal's issuer. */
export function cardCanUseChannel(card: Card, channel: Channel): boolean {
  if (channel.kind !== 'portal') return true;
  return card.portal !== undefined && card.portal === channel.portal;
}

export interface PurchaseContext {
  category: Category;
  kind: ChannelKind;
  merchant?: string;
  prepaid: boolean;
  /** YYYY-MM-DD, for rotating / limited-time rules. */
  today?: string;
}

export function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

/** Is a dated rule active on `today`? Rules without dates are always active. */
export function ruleIsActive(rule: Pick<EarnRule, 'validFrom' | 'validUntil'>, today: string): boolean {
  if (rule.validFrom && today < rule.validFrom) return false;
  if (rule.validUntil && today > rule.validUntil) return false;
  return true;
}

function purchaseContext(booking: Booking, channel: Channel, today: string): PurchaseContext {
  if (channel.kind === 'giftcard') {
    // The card is charged when you buy the gift card, e.g. at a grocery store.
    return { category: channel.giftCardPurchaseCategory ?? 'other', kind: 'giftcard', prepaid: false, today };
  }
  return {
    category: booking.type,
    kind: channel.kind,
    merchant: booking.merchant,
    prepaid: channel.prepaid ?? channel.kind === 'portal',
    today,
  };
}

function ruleApplies(rule: EarnRule, ctx: PurchaseContext): boolean {
  if (!categoryMatches(rule.categories, ctx.category)) return false;
  if (!channelMatches(rule.channel, ctx.kind)) return false;
  if (rule.prepaidOnly && !ctx.prepaid) return false;
  if (rule.merchant && rule.merchant !== ctx.merchant) return false;
  if (!ruleIsActive(rule, ctx.today ?? todayIso())) return false;
  return true;
}

export interface EarnResult {
  points: number;
  rate: number;
  rule?: EarnRule;
  notes: string[];
}

/** Points earned by `card` on `spend` dollars, honoring caps, dates and conditions. */
export function computeEarn(card: Card, ctx: PurchaseContext, spend: number, settings: UserSettings): EarnResult {
  const matches = card.earn
    .map((rule, index) => ({ rule, index }))
    .filter(({ rule }) => ruleApplies(rule, ctx))
    .sort((a, b) => b.rule.rate - a.rule.rate);

  if (matches.length === 0 || matches[0].rule.rate <= card.baseRate) {
    return { points: spend * card.baseRate, rate: card.baseRate, notes: [] };
  }

  const { rule, index } = matches[0];
  const notes: string[] = [];
  if (rule.condition) notes.push(`${card.name} ${rule.rate}x assumes: ${rule.condition}`);
  if (rule.validUntil) notes.push(`${card.name} ${rule.rate}x is limited-time, through ${rule.validUntil}.`);
  if (rule.cap === undefined) {
    return { points: spend * rule.rate, rate: rule.rate, rule, notes };
  }

  const used = settings.capSpendUsed?.[`${card.id}:${index}`] ?? 0;
  const remaining = Math.max(0, rule.cap - used);
  const atBonus = Math.min(spend, remaining);
  const overflow = spend - atBonus;
  const points = atBonus * rule.rate + overflow * card.baseRate;
  if (overflow > 0) {
    const period = CAP_PERIOD_LABEL[rule.capPeriod ?? 'calendar_year'];
    notes.push(`$${round2(overflow)} is over the ${rule.rate}x ${period} cap and earns ${card.baseRate}x.`);
  }
  return { points, rate: spend > 0 ? points / spend : rule.rate, rule, notes };
}

function creditApplies(credit: Credit, ctx: PurchaseContext, channel: Channel): boolean {
  if (!categoryMatches(credit.categories, ctx.category)) return false;
  if (!channelMatches(credit.channel, ctx.kind)) return false;
  if (credit.requiresTag && !(channel.tags ?? []).includes(credit.requiresTag)) return false;
  if (credit.minSpend !== undefined && channel.price < credit.minSpend) return false;
  if (credit.merchant && credit.merchant !== ctx.merchant) return false;
  return true;
}

interface CreditResult {
  applied: number;
  nonEarning: number;
  items: LineItem[];
}

export function computeCredits(card: Card, ctx: PurchaseContext, channel: Channel, charged: number, settings: UserSettings): CreditResult {
  let applied = 0;
  let nonEarning = 0;
  const items: LineItem[] = [];
  for (const credit of card.credits) {
    if (!creditApplies(credit, ctx, channel)) continue;
    const used = settings.creditsUsed?.[`${card.id}:${credit.id}`] ?? 0;
    const remaining = Math.max(0, credit.amount - used);
    const amount = Math.min(remaining, charged - applied);
    if (amount <= 0) continue;
    applied += amount;
    if (!credit.creditedAmountEarnsPoints) nonEarning += amount;
    items.push({ label: credit.name, amount: -round2(amount) });
  }
  return { applied, nonEarning, items };
}

export function cppFor(currencyId: string, data: CatalogData, settings: UserSettings): number {
  const override = settings.cppOverrides?.[currencyId];
  if (override !== undefined) return override;
  const currency = data.currencies.find((c) => c.id === currencyId);
  if (!currency) return 1;
  return settings.valuationMode === 'transfer' ? currency.transferCpp : currency.cashCpp;
}

interface LoyaltyResult {
  points: number;
  value: number;
  perks: number;
  warnings: string[];
}

function computeLoyalty(booking: Booking, channel: Channel, program: LoyaltyProgram | undefined, settings: UserSettings): LoyaltyResult {
  const firstParty = channel.kind === 'direct' || channel.kind === 'giftcard';
  const perksValue = booking.directPerksValue ?? 0;
  const warnings: string[] = [];

  if (!program) {
    return { points: 0, value: 0, perks: firstParty ? perksValue : 0, warnings };
  }

  const earns = firstParty || program.earnsOnThirdPartyBookings;
  const perksApply = firstParty || program.elitePerksOnThirdPartyBookings;

  if (!earns) warnings.push(`Third-party bookings usually don't earn ${program.name} points or elite credit.`);
  if (!perksApply && perksValue > 0) warnings.push(`Elite perks usually don't apply when booked outside ${program.name}.`);

  const status = settings.eliteStatus?.[program.id] ?? 'member';
  const bonus = program.eliteBonus[status] ?? 0;
  const points = earns ? channel.price * program.pointsPerDollar * (1 + bonus) : 0;
  const cpp = settings.loyaltyCppOverrides?.[program.id] ?? program.defaultCpp;

  return {
    points: Math.round(points),
    value: (points * cpp) / 100,
    perks: perksApply ? perksValue : 0,
    warnings,
  };
}

/** Evaluate one channel paid with one card. */
export function evaluate(booking: Booking, channel: Channel, card: Card, data: CatalogData, settings: UserSettings): Option {
  const ctx = purchaseContext(booking, channel, settings.today ?? todayIso());
  const warnings: string[] = [];
  const breakdown: LineItem[] = [];

  const discount = channel.kind === 'giftcard' ? (channel.giftCardDiscountPct ?? 0) / 100 : 0;
  const charged = channel.price * (1 - discount);
  breakdown.push({ label: `${channel.label} price`, amount: round2(channel.price) });
  if (discount > 0) breakdown.push({ label: `Gift card discount (${channel.giftCardDiscountPct}%)`, amount: -round2(channel.price - charged) });

  const credits =
    settings.applyCredits === false
      ? { applied: 0, nonEarning: 0, items: [] }
      : computeCredits(card, ctx, channel, charged, settings);
  breakdown.push(...credits.items);
  for (const credit of card.credits) {
    const used = credits.items.some((i) => i.label === credit.name);
    if (used && credit.channel === 'any') {
      warnings.push(`${credit.name} works on any travel. If you'd use it elsewhere anyway, mark it as used in Settings so it doesn't skew this comparison.`);
    }
  }

  const earningSpend = Math.max(0, charged - credits.nonEarning);
  const earn = computeEarn(card, ctx, earningSpend, settings);
  warnings.push(...earn.notes);
  const cpp = cppFor(card.currency, data, settings);
  const cardPointsValue = (earn.points * cpp) / 100;
  breakdown.push({
    label: `${card.name}: ${Math.round(earn.points).toLocaleString()} pts at ${cpp}¢ (${round2(earn.rate)}x)`,
    amount: -round2(cardPointsValue),
  });

  const program = booking.merchant ? data.loyalty.find((p) => p.id === booking.merchant) : undefined;
  const loyalty = computeLoyalty(booking, channel, program, settings);
  warnings.push(...loyalty.warnings);
  if (program && loyalty.points > 0) {
    breakdown.push({ label: `${program.name}: ~${loyalty.points.toLocaleString()} pts`, amount: -round2(loyalty.value) });
  }
  if (loyalty.perks > 0) breakdown.push({ label: 'Elite perks (your estimate)', amount: -round2(loyalty.perks) });

  if (channel.kind === 'giftcard') {
    warnings.push('Confirm the merchant accepts gift cards for this booking. Some issuers exclude gift card purchases from bonus categories.');
  }
  if (card.needsVerification) warnings.push(`${card.name} terms have not been verified yet.`);

  const effectiveCost = charged - credits.applied - cardPointsValue - loyalty.value - loyalty.perks;
  const baseline = Math.min(...booking.channels.filter((c) => c.kind !== 'giftcard' && c.price > 0).map((c) => c.price), channel.price);

  return {
    channelId: channel.id,
    channelLabel: channel.label,
    channelKind: channel.kind,
    cardId: card.id,
    cardName: card.name,
    amountCharged: round2(charged),
    cardPoints: Math.round(earn.points),
    cardCurrency: card.currency,
    cardPointsValue: round2(cardPointsValue),
    creditsApplied: round2(credits.applied),
    loyaltyPoints: loyalty.points,
    loyaltyValue: round2(loyalty.value),
    perksValue: round2(loyalty.perks),
    effectiveCost: round2(effectiveCost),
    returnPct: baseline > 0 ? round2(((baseline - effectiveCost) / baseline) * 100) : 0,
    breakdown,
    warnings,
  };
}

/** Every (channel x card) combination the user can actually book, cheapest first. */
export function compareOptions(booking: Booking, cards: Card[], data: CatalogData, settings: UserSettings): Option[] {
  const options: Option[] = [];
  for (const channel of booking.channels) {
    if (!(channel.price > 0)) continue;
    for (const card of cards) {
      if (!cardCanUseChannel(card, channel)) continue;
      options.push(evaluate(booking, channel, card, data, settings));
    }
  }
  return options.sort((a, b) => a.effectiveCost - b.effectiveCost || b.cardPointsValue - a.cardPointsValue);
}

/** The best card for each channel, cheapest channel first. */
export function bestPerChannel(options: Option[]): Option[] {
  const seen = new Set<string>();
  return options.filter((o) => (seen.has(o.channelId) ? false : (seen.add(o.channelId), true)));
}
