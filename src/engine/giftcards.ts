// Gift card discount snapshot. Refreshed by scripts/refresh-giftcards.ts (see the
// "Refresh gift card discounts" workflow) and committed to data/giftcards.json.
import raw from '../../data/giftcards.json';

export type GiftCardCategory =
  | 'hotel'
  | 'airline'
  | 'cruise'
  | 'vacation_rental'
  | 'rideshare'
  | 'rail'
  | 'attraction'
  | 'travel_booking'
  | 'dining'
  | 'retail'
  | 'electronics'
  | 'home'
  | 'gas';

export interface GiftCardSeller {
  name: string;
  discountPct: number;
}

export interface GiftCardBrand {
  id: string;
  name: string;
  category: GiftCardCategory;
  travel: boolean;
  /** Loyalty program id when the brand is an airline / hotel chain in data/loyalty.json. */
  merchant?: string;
  /** Best listed discount, in percent. */
  discountPct: number;
  avg12mPct?: number;
  high12mPct?: number;
  sellers?: GiftCardSeller[];
  /** Page with live rates. */
  liveUrl: string;
}

export interface GiftCardSnapshot {
  asOf: string;
  source: { name: string; url: string; note: string };
  brands: GiftCardBrand[];
}

export const giftCards = raw as unknown as GiftCardSnapshot;

/** Best snapshot discount for the gift card that works across a whole loyalty program (e.g. Marriott). */
export function bestGiftCardFor(merchant: string | undefined): GiftCardBrand | undefined {
  if (!merchant) return undefined;
  return giftCards.brands
    .filter((b) => b.merchant === merchant)
    .sort((a, b) => b.discountPct - a.discountPct)[0];
}
