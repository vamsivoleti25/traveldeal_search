// Core domain types for TravelDeal Search.
// The engine is pure: it takes card data + a booking + user settings
// and returns ranked options. No network, no UI, fully unit-testable.

export type Issuer =
  | 'chase'
  | 'amex'
  | 'capital_one'
  | 'citi'
  | 'bank_of_america'
  | 'wells_fargo'
  | 'us_bank'
  | 'barclays'
  | 'discover'
  | 'bilt'
  | 'apple'
  | 'other';

/** Issuer-run travel portals. A portal channel only works with cards from the same issuer. */
export type PortalId = 'chase_travel' | 'amex_travel' | 'capital_one_travel' | 'citi_travel' | 'us_bank_travel' | 'bilt_travel';

export type BookingType = 'flight' | 'hotel' | 'car_rental' | 'vacation_rental' | 'cruise' | 'attraction';

/**
 * Spending categories used by earn rules.
 * "travel" matches every BookingType; "everything" matches any purchase (used for capped flat rates).
 * Categories that never affect a booking decision (streaming, rent, ...) are still stored so the
 * catalog is a complete record of each card's multipliers.
 */
export type Category =
  | BookingType
  | 'travel'
  | 'everything'
  | 'dining'
  | 'grocery'
  | 'gas'
  | 'online_retail'
  | 'office_supply'
  | 'drugstore'
  | 'wholesale_club'
  | 'home_improvement'
  | 'transit'
  | 'rideshare'
  | 'streaming'
  | 'entertainment'
  | 'phone_internet'
  | 'advertising'
  | 'shipping'
  | 'fitness'
  | 'rent'
  | 'foreign'
  | 'other';

export type CapPeriod = 'billing_cycle' | 'month' | 'quarter' | 'calendar_year' | 'anniversary_year';

/** Where the booking is made. */
export type ChannelKind = 'direct' | 'portal' | 'ota' | 'giftcard';

/**
 * Which booking channels an earn rule or credit applies to.
 * "direct" = booked with the airline/hotel itself, "portal" = the card issuer's own portal,
 * "ota" = third-party sites like Expedia. "any" matches all three.
 * Gift card purchases are matched as "direct" purchases in the gift card's purchase category.
 */
export type RuleChannel = 'any' | 'direct' | 'portal' | 'ota';
export type RuleChannelSpec = RuleChannel | RuleChannel[];

export interface EarnRule {
  categories: Category[];
  channel: RuleChannelSpec;
  /** Points (or % cash back) per dollar. */
  rate: number;
  /** Only prepaid portal bookings qualify (e.g. Amex prepaid hotels). */
  prepaidOnly?: boolean;
  /** Only purchases with this merchant / loyalty program (co-brand cards). */
  merchant?: string;
  /** Spend cap for this rule per `capPeriod`; spend above it earns the card's base rate. */
  cap?: number;
  capPeriod?: CapPeriod;
  /** First / last day the rule applies (YYYY-MM-DD). Used for rotating and limited-time categories. */
  validFrom?: string;
  validUntil?: string;
  /** Something the user must have done for this rate (activation, chosen category, Prime, ...). Shown as a warning. */
  condition?: string;
  note?: string;
}

export interface Credit {
  id: string;
  name: string;
  /** Maximum dollar amount per period. */
  amount: number;
  period: 'calendar_year' | 'anniversary_year' | 'semiannual' | 'quarterly';
  categories: Category[];
  channel: RuleChannelSpec;
  /** Only purchases with this merchant / loyalty program (e.g. Hilton credit). */
  merchant?: string;
  /** Single purchase must be at least this much (e.g. Citi's $500+ hotel stay). Portal credits use the card's own portal. */
  minSpend?: number;
  /** Booking must carry this tag (e.g. "amex_fhr_thc" for Fine Hotels + Resorts). */
  requiresTag?: string;
  /** If false, the credited part of the purchase earns no points. */
  creditedAmountEarnsPoints: boolean;
  note?: string;
}

export interface Card {
  id: string;
  name: string;
  issuer: Issuer;
  network: 'visa' | 'mastercard' | 'amex' | 'discover';
  /** Personal or small-business card. */
  type: 'personal' | 'business';
  annualFee: number;
  /** Rewards currency id, matches data/currencies.json. */
  currency: string;
  /** Earn rate for anything no rule matches. */
  baseRate: number;
  earn: EarnRule[];
  credits: Credit[];
  /** Portal this card unlocks, if any. */
  portal?: PortalId;
  lastVerified: string | null;
  needsVerification: boolean;
  sources: string[];
  notes?: string[];
}

export interface Currency {
  id: string;
  name: string;
  /** Cents per point if redeemed as cash / statement credit. */
  cashCpp: number;
  /** Cents per point a typical points enthusiast gets via transfer partners or portal boosts. */
  transferCpp: number;
}

export interface LoyaltyProgram {
  id: string;
  name: string;
  kind: 'airline' | 'hotel' | 'car_rental';
  /** Program points per dollar on eligible spend for a base member. */
  pointsPerDollar: number;
  /** Elite bonus as a fraction of base, keyed by status name. */
  eliteBonus: Record<string, number>;
  /** Default value of one program point, in cents. */
  defaultCpp: number;
  /** Do bookings through card portals / OTAs earn program points? Airlines usually yes, hotels usually no. */
  earnsOnThirdPartyBookings: boolean;
  /** Do elite benefits (upgrades, breakfast, late checkout) usually apply to third-party bookings? */
  elitePerksOnThirdPartyBookings: boolean;
}

export interface Channel {
  id: string;
  kind: ChannelKind;
  label: string;
  /** Total price shown on that channel, in USD, before any card rewards. */
  price: number;
  portal?: PortalId;
  /** Portal booking is prepaid (needed for some earn rules, e.g. Amex hotels). */
  prepaid?: boolean;
  /** Gift card discount, as a percentage (e.g. 8 for 8% off). */
  giftCardDiscountPct?: number;
  /** Category the gift card purchase codes as when buying it (e.g. grocery store). */
  giftCardPurchaseCategory?: Category;
  tags?: string[];
}

export interface Booking {
  type: BookingType;
  /** Loyalty program id of the airline / hotel chain, if any (e.g. "marriott"). */
  merchant?: string;
  channels: Channel[];
  /** Dollar value the user puts on elite perks when booking direct (breakfast, upgrade, etc.). */
  directPerksValue?: number;
}

export type ValuationMode = 'cash' | 'transfer';

export interface UserSettings {
  valuationMode: ValuationMode;
  /** Apply unused card statement credits to this booking (default true). */
  applyCredits?: boolean;
  /** Per-currency cents-per-point overrides. */
  cppOverrides?: Record<string, number>;
  /** Credits already used: key is `${cardId}:${creditId}`, value is dollars already used. */
  creditsUsed?: Record<string, number>;
  /** Spend already counted toward a capped rule this year: key `${cardId}:${ruleIndex}`. */
  capSpendUsed?: Record<string, number>;
  /** Elite status per loyalty program, e.g. { marriott: "gold" }. */
  eliteStatus?: Record<string, string>;
  /** Per-program cpp overrides for airline / hotel points. */
  loyaltyCppOverrides?: Record<string, number>;
  /** Date used for rotating / limited-time rules (YYYY-MM-DD). Defaults to today. */
  today?: string;
}

export interface LineItem {
  label: string;
  /** Positive = cost, negative = value back to you. */
  amount: number;
}

export interface Option {
  channelId: string;
  channelLabel: string;
  channelKind: ChannelKind;
  cardId: string;
  cardName: string;
  /** Dollars charged to the card. */
  amountCharged: number;
  cardPoints: number;
  cardCurrency: string;
  cardPointsValue: number;
  creditsApplied: number;
  loyaltyPoints: number;
  loyaltyValue: number;
  perksValue: number;
  /** What the booking really costs you after rewards, credits and perks. */
  effectiveCost: number;
  /** Effective savings vs. the cheapest sticker price, as a % of that price. */
  returnPct: number;
  breakdown: LineItem[];
  warnings: string[];
}

export interface CatalogData {
  cards: Card[];
  currencies: Currency[];
  loyalty: LoyaltyProgram[];
}
