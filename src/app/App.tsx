import { useEffect, useMemo, useState } from 'react';
import { catalog } from '../engine/catalog';
import { compareOptions } from '../engine/compare';
import type { PortalId, UserSettings } from '../engine/types';
import { initialForm, toBooking, type BookingFormState } from './bookingForm';
import { BookingForm } from './components/BookingForm';
import { CardPicker } from './components/CardPicker';
import { CatalogPage } from './components/CatalogPage';
import { GiftCardsPage } from './components/GiftCardsPage';
import type { GiftCardBrand } from '../engine/giftcards';
import { Results } from './components/Results';
import { SettingsPanel } from './components/SettingsPanel';
import { usePersistentList, usePersistentState } from './storage';

const defaultSettings: UserSettings = { valuationMode: 'cash' };

type Page = 'compare' | 'giftcards' | 'cards';
const PAGES: { id: Page; label: string }[] = [
  { id: 'compare', label: 'Compare' },
  { id: 'giftcards', label: 'Gift card deals' },
  { id: 'cards', label: 'Card catalog' },
];

const pageFromHash = (): Page => {
  const h = window.location.hash.replace('#/', '');
  return PAGES.some((p) => p.id === h) ? (h as Page) : 'compare';
};

const GIFT_TO_BOOKING: Partial<Record<GiftCardBrand['category'], BookingFormState['type']>> = {
  hotel: 'hotel',
  airline: 'flight',
  cruise: 'cruise',
  vacation_rental: 'vacation_rental',
  travel_booking: 'hotel',
  attraction: 'attraction',
};

export function App() {
  const [selectedIds, setSelectedIds] = usePersistentList('tds.cards', ['chase-sapphire-reserve']);
  const [settings, setSettings] = usePersistentState<UserSettings>('tds.settings', defaultSettings);
  const [form, setForm] = usePersistentState<BookingFormState>('tds.booking', initialForm);
  const [page, setPage] = useState<Page>(pageFromHash);

  useEffect(() => {
    const onHash = () => setPage(pageFromHash());
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);

  const go = (p: Page) => {
    window.location.hash = `/${p}`;
    window.scrollTo({ top: 0 });
  };

  const applyGiftCard = (brand: GiftCardBrand) => {
    const type = GIFT_TO_BOOKING[brand.category] ?? form.type;
    setForm({ ...form, type, merchant: brand.merchant ?? '', giftCardDiscountPct: brand.discountPct });
    go('compare');
  };

  const toggleCard = (id: string) =>
    setSelectedIds(selectedIds.includes(id) ? selectedIds.filter((s) => s !== id) : [...selectedIds, id]);

  const myCards = useMemo(
    () => selectedIds.map((id) => catalog.cards.find((c) => c.id === id)).filter((c) => c !== undefined),
    [selectedIds],
  );
  const portals = useMemo(
    () => [...new Set(myCards.map((c) => c.portal).filter((p): p is PortalId => p !== undefined))],
    [myCards],
  );
  const merchantName = catalog.loyalty.find((p) => p.id === form.merchant)?.name ?? '';
  const options = useMemo(
    () => compareOptions(toBooking(form, portals, merchantName), myCards, catalog, settings),
    [form, portals, merchantName, myCards, settings],
  );

  return (
    <div className="page">
      <header>
        <h1>TravelDeal Search</h1>
        <p className="muted">Book direct, through a card portal, or with discounted gift cards? Find the cheapest way to pay with the cards you already have.</p>
        <nav className="tabs" aria-label="Sections">
          {PAGES.map((p) => (
            <a key={p.id} href={`#/${p.id}`} className={page === p.id ? 'on' : ''} aria-current={page === p.id ? 'page' : undefined}>
              {p.label}
            </a>
          ))}
        </nav>
      </header>

      {page === 'giftcards' && <GiftCardsPage onUse={applyGiftCard} />}
      {page === 'cards' && <CatalogPage cards={catalog.cards} selected={selectedIds} onToggle={toggleCard} />}

      <main hidden={page !== 'compare'}>
        <aside>
          <section className="panel">
            <h2>Your cards</h2>
            <CardPicker cards={catalog.cards} selected={selectedIds} onChange={setSelectedIds} />
            <a className="link small browse" href="#/cards">
              Browse all {catalog.cards.length} cards and their multipliers →
            </a>
          </section>
          <section className="panel">
            <details>
              <summary>
                <h2>Settings</h2>
              </summary>
              <SettingsPanel cards={myCards} data={catalog} settings={settings} onChange={setSettings} />
            </details>
          </section>
        </aside>

        <div className="content">
          <section className="panel">
            <h2>Your trip</h2>
            <BookingForm form={form} onChange={setForm} portals={portals} programs={catalog.loyalty} />
          </section>
          <section className="panel">
            <label className="credit-toggle">
              <input
                type="checkbox"
                checked={settings.applyCredits !== false}
                onChange={(e) => setSettings({ ...settings, applyCredits: e.target.checked })}
              />
              Apply my unused card credits to this booking
            </label>
            <Results options={options} />
          </section>
        </div>
      </main>

      <footer className="muted small">
        Card terms change often. Each card shows when it was last verified; check the issuer's site before you book. Not financial advice.
        Card data lives in <code>data/cards</code> — corrections welcome.
      </footer>
    </div>
  );
}
