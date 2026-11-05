import { useMemo, useState } from 'react';
import type { Card } from '../../engine/types';
import { ISSUER_LABELS, PORTAL_LABELS } from '../../engine/catalog';
import { todayIso, ruleIsActive } from '../../engine/compare';
import { describeCredit, describeRule, ruleDetails } from '../format';

interface Props {
  cards: Card[];
  selected: string[];
  onToggle: (id: string) => void;
}

type TypeFilter = 'all' | 'personal' | 'business';

export function CatalogPage({ cards, selected, onToggle }: Props) {
  const [query, setQuery] = useState('');
  const [issuer, setIssuer] = useState('all');
  const [type, setType] = useState<TypeFilter>('all');
  const [portalOnly, setPortalOnly] = useState(false);
  const today = todayIso();

  const issuers = useMemo(() => [...new Set(cards.map((c) => c.issuer))], [cards]);
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return cards.filter(
      (c) =>
        (issuer === 'all' || c.issuer === issuer) &&
        (type === 'all' || c.type === type) &&
        (!portalOnly || c.portal) &&
        (!q || c.name.toLowerCase().includes(q) || ISSUER_LABELS[c.issuer].toLowerCase().includes(q)),
    );
  }, [cards, query, issuer, type, portalOnly]);

  return (
    <div className="catalog">
      <section className="panel">
        <div className="catalog-head">
          <div>
            <h2>Card catalog</h2>
            <p className="muted small">
              {cards.length} U.S. rewards cards with every earning multiplier, cap and travel credit we track. Add the ones in your wallet.
            </p>
          </div>
          <span className="count">{selected.length} in your wallet</span>
        </div>
        <div className="catalog-filters">
          <input type="search" placeholder="Search cards" value={query} onChange={(e) => setQuery(e.target.value)} aria-label="Search cards" />
          <select value={issuer} onChange={(e) => setIssuer(e.target.value)} aria-label="Issuer">
            <option value="all">All issuers</option>
            {issuers.map((i) => (
              <option key={i} value={i}>
                {ISSUER_LABELS[i]}
              </option>
            ))}
          </select>
          <select value={type} onChange={(e) => setType(e.target.value as TypeFilter)} aria-label="Card type">
            <option value="all">Personal & business</option>
            <option value="personal">Personal</option>
            <option value="business">Business</option>
          </select>
          <label className="check">
            <input type="checkbox" checked={portalOnly} onChange={(e) => setPortalOnly(e.target.checked)} />
            Has a travel portal
          </label>
        </div>
      </section>

      <div className="card-grid">
        {filtered.map((card) => {
          const mine = selected.includes(card.id);
          const rules = [...card.earn].sort((a, b) => b.rate - a.rate);
          return (
            <article key={card.id} className={`card-entry ${mine ? 'mine' : ''}`}>
              <header>
                <div>
                  <p className="eyebrow">
                    {ISSUER_LABELS[card.issuer]}
                    {card.type === 'business' && ' · Business'}
                  </p>
                  <h3>{card.name}</h3>
                  <p className="muted small">
                    ${card.annualFee}/yr · base {card.currency === 'cash_back' ? `${card.baseRate}%` : `${card.baseRate}x`}
                    {card.portal && ` · ${PORTAL_LABELS[card.portal]}`}
                  </p>
                </div>
                <button className={mine ? 'btn secondary' : 'btn'} onClick={() => onToggle(card.id)} aria-pressed={mine}>
                  {mine ? 'In wallet ✓' : 'Add'}
                </button>
              </header>
              <ul className="rules">
                {rules.map((rule, i) => {
                  const active = ruleIsActive(rule, today);
                  const details = ruleDetails(rule);
                  return (
                    <li key={i} className={active ? '' : 'inactive'}>
                      <span className="rate">{describeRule(rule, card)}</span>
                      {details.length > 0 && <span className="muted small"> · {details.join(' · ')}</span>}
                      {!active && <span className="badge">not active today</span>}
                    </li>
                  );
                })}
                {rules.length === 0 && <li className="muted">Flat rate on everything</li>}
              </ul>
              {card.credits.length > 0 && (
                <p className="small credits">
                  <strong>Credits:</strong> {card.credits.map(describeCredit).join('; ')}
                </p>
              )}
              <footer className="small muted">
                {card.needsVerification ? <span className="badge warn">Unverified</span> : <span>Checked {card.lastVerified}</span>}
                {card.sources.slice(0, 2).map((s, i) => (
                  <a key={s} href={s} target="_blank" rel="noreferrer">
                    Source {i + 1} ↗
                  </a>
                ))}
              </footer>
            </article>
          );
        })}
      </div>
      {filtered.length === 0 && <p className="muted">No cards match those filters.</p>}
    </div>
  );
}
