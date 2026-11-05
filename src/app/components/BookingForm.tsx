import type { BookingType, Category, LoyaltyProgram, PortalId } from '../../engine/types';
import { PORTAL_LABELS } from '../../engine/catalog';
import { bestGiftCardFor, giftCards } from '../../engine/giftcards';
import type { BookingFormState } from '../bookingForm';

interface Props {
  form: BookingFormState;
  onChange: (f: BookingFormState) => void;
  portals: PortalId[];
  programs: LoyaltyProgram[];
}

const TYPES: { value: BookingType; label: string }[] = [
  { value: 'hotel', label: 'Hotel' },
  { value: 'flight', label: 'Flight' },
  { value: 'car_rental', label: 'Rental car' },
  { value: 'vacation_rental', label: 'Vacation rental' },
  { value: 'cruise', label: 'Cruise' },
  { value: 'attraction', label: 'Attraction' },
];

const GIFT_CATEGORIES: { value: Category; label: string }[] = [
  { value: 'grocery', label: 'Grocery store' },
  { value: 'office_supply', label: 'Office supply store' },
  { value: 'drugstore', label: 'Drugstore' },
  { value: 'gas', label: 'Gas station' },
  { value: 'online_retail', label: 'Online retailer' },
  { value: 'other', label: 'Other / marketplace' },
];

function Money({ label, value, onChange, hint }: { label: string; value: number; onChange: (n: number) => void; hint?: string }) {
  return (
    <label className="field">
      <span>{label}</span>
      <div className="money">
        <span aria-hidden>$</span>
        <input
          type="number"
          inputMode="decimal"
          min={0}
          step="0.01"
          value={value || ''}
          placeholder="—"
          onChange={(e) => onChange(Number(e.target.value) || 0)}
        />
      </div>
      {hint && <small className="muted">{hint}</small>}
    </label>
  );
}

export function BookingForm({ form, onChange, portals, programs }: Props) {
  const set = <K extends keyof BookingFormState>(k: K, v: BookingFormState[K]) => onChange({ ...form, [k]: v });
  const kind = form.type === 'flight' ? 'airline' : form.type === 'hotel' ? 'hotel' : null;
  const merchantOptions = kind ? programs.filter((p) => p.kind === kind) : [];
  const giftDeal = bestGiftCardFor(form.merchant);

  return (
    <div className="form">
      <div className="row">
        <label className="field">
          <span>What are you booking?</span>
          <select
            value={form.type}
            onChange={(e) => {
              const type = e.target.value as BookingType;
              const nextKind = type === 'flight' ? 'airline' : type === 'hotel' ? 'hotel' : null;
              const keep = programs.find((p) => p.id === form.merchant)?.kind === nextKind;
              onChange({ ...form, type, merchant: keep ? form.merchant : '' });
            }}
          >
            {TYPES.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>{kind === 'airline' ? 'Airline' : kind === 'hotel' ? 'Hotel brand' : 'Merchant'}</span>
          <select value={form.merchant} onChange={(e) => set('merchant', e.target.value)} disabled={!kind}>
            <option value="">Other / independent</option>
            {merchantOptions.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </label>
      </div>

      <h3>Prices you found</h3>
      <p className="muted small">Enter the total for the same trip on each site. Leave a channel blank to skip it.</p>
      <div className="grid">
        <Money label="Direct (airline / hotel site)" value={form.directPrice} onChange={(n) => set('directPrice', n)} />
        {portals.map((p) => (
          <div key={p}>
            <Money
              label={PORTAL_LABELS[p]}
              value={form.portalPrices[p] ?? 0}
              onChange={(n) => set('portalPrices', { ...form.portalPrices, [p]: n })}
            />
            {form.type === 'hotel' && (
              <label className="check">
                <input
                  type="checkbox"
                  checked={!form.portalNotPrepaid[p]}
                  onChange={(e) => set('portalNotPrepaid', { ...form.portalNotPrepaid, [p]: !e.target.checked })}
                />
                Prepaid rate
              </label>
            )}
            {p === 'amex_travel' && form.type === 'hotel' && (
              <label className="check">
                <input type="checkbox" checked={form.amexFhr} onChange={(e) => set('amexFhr', e.target.checked)} />
                Fine Hotels + Resorts / Hotel Collection
              </label>
            )}
          </div>
        ))}
        <Money label="Online travel agency (Expedia etc.)" value={form.otaPrice} onChange={(n) => set('otaPrice', n)} />
      </div>
      {portals.length === 0 && <p className="muted small">Add a card with a travel portal to compare portal prices.</p>}

      {giftDeal && form.giftCardDiscountPct !== giftDeal.discountPct && (
        <div className="hint">
          <span>
            <strong>{giftDeal.name} gift cards</strong> were up to {giftDeal.discountPct}% off on {giftCards.asOf}.{' '}
            <a href={giftDeal.liveUrl} target="_blank" rel="noreferrer">
              Check live rate ↗
            </a>
          </span>
          <button className="btn small" onClick={() => set('giftCardDiscountPct', giftDeal.discountPct)}>
            Add to comparison
          </button>
        </div>
      )}

      <details className="extras" open={form.giftCardDiscountPct > 0 || undefined}>
        <summary>Gift cards and elite perks</summary>
        <div className="grid">
          <label className="field">
            <span>Gift card discount</span>
            <div className="money">
              <input
                type="number"
                min={0}
                max={50}
                step="0.5"
                value={form.giftCardDiscountPct || ''}
                placeholder="0"
                onChange={(e) => set('giftCardDiscountPct', Number(e.target.value) || 0)}
              />
              <span aria-hidden>%</span>
            </div>
            <small className="muted">Off the direct price, from a gift card marketplace or store promo.</small>
          </label>
          <label className="field">
            <span>Where you'd buy the gift card</span>
            <select
              value={form.giftCardPurchaseCategory}
              onChange={(e) => set('giftCardPurchaseCategory', e.target.value as Category)}
            >
              {GIFT_CATEGORIES.map((g) => (
                <option key={g.value} value={g.value}>
                  {g.label}
                </option>
              ))}
            </select>
            <small className="muted">Decides which card category the purchase earns in.</small>
          </label>
          <Money
            label="Value of elite perks when booking direct"
            value={form.directPerksValue}
            onChange={(n) => set('directPerksValue', n)}
            hint="Breakfast, upgrade, late checkout — your own estimate."
          />
        </div>
      </details>
    </div>
  );
}
