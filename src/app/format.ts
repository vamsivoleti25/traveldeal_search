// Human-readable labels for card rules, used by the catalog and settings.
import type { Card, Category, Credit, EarnRule, RuleChannelSpec } from '../engine/types';
import { ISSUER_LABELS, PORTAL_LABELS } from '../engine/catalog';

const CATEGORY_LABELS: Record<Category, string> = {
  flight: 'flights',
  hotel: 'hotels',
  car_rental: 'car rentals',
  vacation_rental: 'vacation rentals',
  cruise: 'cruises',
  attraction: 'attractions',
  travel: 'travel',
  everything: 'everything',
  dining: 'dining',
  grocery: 'groceries',
  gas: 'gas',
  online_retail: 'online shopping',
  office_supply: 'office supply stores',
  drugstore: 'drugstores',
  wholesale_club: 'wholesale clubs',
  home_improvement: 'home improvement',
  transit: 'transit',
  rideshare: 'rideshare',
  streaming: 'streaming',
  entertainment: 'entertainment',
  phone_internet: 'phone & internet',
  advertising: 'advertising',
  shipping: 'shipping',
  fitness: 'fitness',
  rent: 'rent',
  foreign: 'foreign purchases',
  other: 'other',
};

const MERCHANT_LABELS: Record<string, string> = {
  marriott: 'Marriott',
  hilton: 'Hilton',
  hyatt: 'Hyatt',
  ihg: 'IHG',
  wyndham: 'Wyndham',
  delta: 'Delta',
  united: 'United',
  american: 'American Airlines',
  southwest: 'Southwest',
  jetblue: 'JetBlue',
  alaska: 'Alaska & Hawaiian',
  air_canada: 'Air Canada',
  amazon: 'Amazon',
  apple: 'Apple',
};

const PERIOD_LABELS: Record<string, string> = {
  billing_cycle: 'billing cycle',
  month: 'month',
  quarter: 'quarter',
  calendar_year: 'year',
  anniversary_year: 'year',
  semiannual: 'half-year',
  quarterly: 'quarter',
};

export const categoryLabel = (c: Category) => CATEGORY_LABELS[c] ?? c;
export const merchantLabel = (m: string) => MERCHANT_LABELS[m] ?? m;
export const issuerLabel = (i: string) => ISSUER_LABELS[i] ?? i;

const usd = (n: number) => `$${n.toLocaleString('en-US')}`;

function list(items: string[]): string {
  if (items.length <= 2) return items.join(' & ');
  return `${items.slice(0, -1).join(', ')} & ${items[items.length - 1]}`;
}

function channelSuffix(spec: RuleChannelSpec, card: Card): string {
  const portal = card.portal ? PORTAL_LABELS[card.portal] : 'the issuer portal';
  if (spec === 'any') return '';
  const parts = Array.isArray(spec) ? spec : [spec];
  if (parts.length === 1 && parts[0] === 'portal') return ` via ${portal}`;
  if (parts.length === 1 && parts[0] === 'direct') return ' booked direct';
  if (parts.includes('direct') && parts.includes('portal')) return ` direct or via ${portal}`;
  if (parts.includes('direct') && parts.includes('ota')) return ' (not via portal)';
  return '';
}

export function rateLabel(card: Card, rate: number): string {
  return card.currency === 'cash_back' ? `${rate}%` : `${rate}x`;
}

/** e.g. "8x travel via Chase Travel", "4x dining · up to $50,000/year" */
export function describeRule(rule: EarnRule, card: Card): string {
  const what = rule.merchant
    ? merchantLabel(rule.merchant) + (rule.categories.includes('hotel') ? ' hotels' : '')
    : list(rule.categories.map(categoryLabel));
  let text = `${rateLabel(card, rule.rate)} ${what}${channelSuffix(rule.channel, card)}`;
  if (rule.prepaidOnly) text += ' (prepaid)';
  return text;
}

export function ruleDetails(rule: EarnRule): string[] {
  const out: string[] = [];
  if (rule.cap) out.push(`up to ${usd(rule.cap)}/${PERIOD_LABELS[rule.capPeriod ?? 'calendar_year']}`);
  if (rule.validFrom && rule.validUntil) out.push(`${rule.validFrom} to ${rule.validUntil}`);
  else if (rule.validUntil) out.push(`through ${rule.validUntil}`);
  else if (rule.validFrom) out.push(`from ${rule.validFrom}`);
  if (rule.condition) out.push(rule.condition);
  return out;
}

export function describeCredit(credit: Credit): string {
  return `${credit.name} (${usd(credit.amount)}/${PERIOD_LABELS[credit.period]})`;
}
