import { useMemo, useState } from 'react';
import { giftCards, type GiftCardBrand, type GiftCardCategory } from '../../engine/giftcards';

interface Props {
  onUse: (brand: GiftCardBrand) => void;
}

const FILTERS: { id: string; label: string; match: (b: GiftCardBrand) => boolean }[] = [
  { id: 'travel', label: 'All travel', match: (b) => b.travel },
  { id: 'hotel', label: 'Hotels', match: (b) => b.category === 'hotel' },
  { id: 'airline', label: 'Airlines', match: (b) => b.category === 'airline' },
  { id: 'cruise', label: 'Cruises', match: (b) => b.category === 'cruise' },
  { id: 'stays', label: 'Rentals & booking sites', match: (b) => b.category === 'vacation_rental' || b.category === 'travel_booking' },
  { id: 'ground', label: 'Rides & rail', match: (b) => b.category === 'rideshare' || b.category === 'rail' },
  { id: 'everyday', label: 'Everyday', match: (b) => !b.travel },
];

const CATEGORY_NAMES: Record<GiftCardCategory, string> = {
  hotel: 'Hotel',
  airline: 'Airline',
  cruise: 'Cruise',
  vacation_rental: 'Vacation rental',
  rideshare: 'Rideshare',
  rail: 'Rail',
  attraction: 'Attraction',
  travel_booking: 'Travel booking',
  dining: 'Dining',
  retail: 'Retail',
  electronics: 'Electronics',
  home: 'Home',
  gas: 'Gas',
};

const USABLE_IN_COMPARE: GiftCardCategory[] = ['hotel', 'airline', 'cruise', 'vacation_rental', 'travel_booking', 'attraction'];

function Monogram({ name }: { name: string }) {
  const letters = name
    .replace(/[^A-Za-z0-9 ]/g, '')
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0])
    .join('')
    .toUpperCase();
  return <span className="monogram" aria-hidden>{letters}</span>;
}

export function GiftCardsPage({ onUse }: Props) {
  const [filter, setFilter] = useState('travel');
  const [query, setQuery] = useState('');
  const [sort, setSort] = useState<'discount' | 'name'>('discount');

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    const f = FILTERS.find((x) => x.id === filter) ?? FILTERS[0];
    return giftCards.brands
      .filter((b) => (q ? b.name.toLowerCase().includes(q) : f.match(b)))
      .sort((a, b) => (sort === 'discount' ? b.discountPct - a.discountPct : a.name.localeCompare(b.name)));
  }, [filter, query, sort]);

  const highlights = useMemo(
    () => giftCards.brands.filter((b) => b.travel && USABLE_IN_COMPARE.includes(b.category)).slice(0, 4),
    [],
  );

  const asOf = new Date(`${giftCards.asOf}T12:00:00`).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });

  return (
    <div className="gift-page">
      <section className="panel gift-intro">
        <div>
          <h2>Discounted travel gift cards</h2>
          <p className="muted">
            Buy a brand's gift card below face value, then pay for the trip with it. Stack it with a card that earns well where you buy the
            gift card, and you usually still earn the airline or hotel's own points.
          </p>
        </div>
        <p className="snapshot small">
          Snapshot from{' '}
          <a href={giftCards.source.url} target="_blank" rel="noreferrer">
            {giftCards.source.name}
          </a>{' '}
          · {asOf}. {giftCards.source.note}
        </p>
      </section>

      <section className="highlights" aria-label="Biggest travel discounts">
        {highlights.map((b) => (
          <article key={b.id} className="tile">
            <div className="tile-top">
              <Monogram name={b.name} />
              <span className="pct">{b.discountPct}%</span>
            </div>
            <h3>{b.name}</h3>
            <p className="muted small">
              {CATEGORY_NAMES[b.category]}
              {b.avg12mPct !== undefined && ` · 12-mo avg ${b.avg12mPct}%`}
            </p>
            <button className="btn" onClick={() => onUse(b)}>
              Compare a booking
            </button>
          </article>
        ))}
      </section>

      <section className="panel">
        <div className="gift-toolbar">
          <input
            type="search"
            placeholder="Search 47 brands"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            aria-label="Search gift card brands"
          />
          <select value={sort} onChange={(e) => setSort(e.target.value as 'discount' | 'name')} aria-label="Sort">
            <option value="discount">Biggest discount</option>
            <option value="name">Name A–Z</option>
          </select>
        </div>
        <div className="filter-chips" role="tablist">
          {FILTERS.map((f) => (
            <button
              key={f.id}
              role="tab"
              aria-selected={!query && filter === f.id}
              className={!query && filter === f.id ? 'on' : ''}
              onClick={() => {
                setFilter(f.id);
                setQuery('');
              }}
            >
              {f.label}
            </button>
          ))}
        </div>

        <div className="table-wrap">
          <table className="rank gift-table">
            <thead>
              <tr>
                <th>Brand</th>
                <th>Type</th>
                <th className="num">Best discount</th>
                <th className="num">Save on $500</th>
                <th aria-label="Actions" />
              </tr>
            </thead>
            <tbody>
              {rows.map((b) => (
                <tr key={b.id}>
                  <td>
                    <span className="brand-cell">
                      <Monogram name={b.name} />
                      {b.name}
                    </span>
                  </td>
                  <td className="muted">{CATEGORY_NAMES[b.category]}</td>
                  <td className="num strong">{b.discountPct}%</td>
                  <td className="num good">${((500 * b.discountPct) / 100).toFixed(0)}</td>
                  <td className="actions">
                    {USABLE_IN_COMPARE.includes(b.category) && (
                      <button className="link" onClick={() => onUse(b)}>
                        Use in comparison
                      </button>
                    )}
                    <a className="link" href={b.liveUrl} target="_blank" rel="noreferrer">
                      Live rates ↗
                    </a>
                  </td>
                </tr>
              ))}
              {rows.length === 0 && (
                <tr>
                  <td colSpan={5} className="muted">
                    No brands match.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel how">
        <h2>How to stack a gift card deal</h2>
        <ol>
          <li>Check the live rate and the seller's guarantee before buying. Discounts move daily and stock sells out.</li>
          <li>
            Pay for the gift card with a card that earns well <em>where you buy it</em>: a 5x office-supply card at Staples, a 4x grocery card at the
            supermarket, or your best everyday card online.
          </li>
          <li>Book directly with the airline or hotel and pay with the gift card. Direct bookings usually still earn loyalty points.</li>
          <li>Confirm the merchant accepts gift cards for that rate type. Some prepaid or third-party rates don't.</li>
        </ol>
      </section>
    </div>
  );
}
