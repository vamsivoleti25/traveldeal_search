// Loads the card catalog bundled with the app. Each file in data/cards is one card.
import type { Card, CatalogData, Currency, LoyaltyProgram } from './types';
import currencies from '../../data/currencies.json';
import loyalty from '../../data/loyalty.json';

const cardModules = import.meta.glob<{ default: Card }>('../../data/cards/*.json', { eager: true });

export const catalog: CatalogData = {
  cards: Object.values(cardModules)
    .map((m) => m.default)
    .sort((a, b) => a.issuer.localeCompare(b.issuer) || a.name.localeCompare(b.name)),
  currencies: currencies as unknown as Currency[],
  loyalty: loyalty as unknown as LoyaltyProgram[],
};

export const PORTAL_LABELS: Record<string, string> = {
  chase_travel: 'Chase Travel',
  amex_travel: 'Amex Travel',
  capital_one_travel: 'Capital One Travel',
  citi_travel: 'Citi Travel',
};

export const ISSUER_LABELS: Record<string, string> = {
  chase: 'Chase',
  amex: 'American Express',
  capital_one: 'Capital One',
  citi: 'Citi',
  bank_of_america: 'Bank of America',
  wells_fargo: 'Wells Fargo',
  other: 'Other',
};
