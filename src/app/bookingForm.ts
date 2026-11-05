// Turns the form state into the engine's Booking input.
import type { Booking, BookingType, Category, Channel, PortalId } from '../engine/types';
import { PORTAL_LABELS } from '../engine/catalog';

export interface BookingFormState {
  type: BookingType;
  merchant: string;
  directPrice: number;
  otaPrice: number;
  portalPrices: Partial<Record<PortalId, number>>;
  portalNotPrepaid: Partial<Record<PortalId, boolean>>;
  amexFhr: boolean;
  giftCardDiscountPct: number;
  giftCardPurchaseCategory: Category;
  directPerksValue: number;
}

export const initialForm: BookingFormState = {
  type: 'hotel',
  merchant: 'marriott',
  directPrice: 420,
  otaPrice: 0,
  portalPrices: { chase_travel: 405 },
  portalNotPrepaid: {},
  amexFhr: false,
  giftCardDiscountPct: 0,
  giftCardPurchaseCategory: 'grocery',
  directPerksValue: 0,
};

export function toBooking(form: BookingFormState, portals: PortalId[], merchantName: string): Booking {
  const channels: Channel[] = [];
  const directLabel = merchantName ? `Direct (${merchantName})` : 'Direct';
  if (form.directPrice > 0) channels.push({ id: 'direct', kind: 'direct', label: directLabel, price: form.directPrice });
  for (const portal of portals) {
    const price = form.portalPrices[portal] ?? 0;
    if (price > 0) {
      channels.push({
        id: portal,
        kind: 'portal',
        label: PORTAL_LABELS[portal],
        price,
        portal,
        prepaid: !form.portalNotPrepaid[portal],
        tags: portal === 'amex_travel' && form.amexFhr ? ['amex_fhr_thc'] : [],
      });
    }
  }
  if (form.otaPrice > 0) channels.push({ id: 'ota', kind: 'ota', label: 'Online travel agency', price: form.otaPrice });
  if (form.giftCardDiscountPct > 0 && form.directPrice > 0) {
    channels.push({
      id: 'giftcard',
      kind: 'giftcard',
      label: `Direct, paid with ${merchantName || 'merchant'} gift cards`,
      price: form.directPrice,
      giftCardDiscountPct: form.giftCardDiscountPct,
      giftCardPurchaseCategory: form.giftCardPurchaseCategory,
    });
  }
  return {
    type: form.type,
    merchant: form.merchant || undefined,
    channels,
    directPerksValue: form.directPerksValue || undefined,
  };
}
