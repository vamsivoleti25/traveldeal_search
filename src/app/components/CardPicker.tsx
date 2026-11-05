import { useMemo, useRef, useState } from 'react';
import type { Card } from '../../engine/types';
import { ISSUER_LABELS } from '../../engine/catalog';

interface Props {
  cards: Card[];
  selected: string[];
  onChange: (ids: string[]) => void;
}

export function CardPicker({ cards, selected, onChange }: Props) {
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const available = useMemo(() => {
    const q = query.trim().toLowerCase();
    return cards.filter(
      (c) =>
        !selected.includes(c.id) &&
        (!q || c.name.toLowerCase().includes(q) || ISSUER_LABELS[c.issuer].toLowerCase().includes(q)),
    );
  }, [cards, selected, query]);

  const grouped = useMemo(() => {
    const groups = new Map<string, Card[]>();
    for (const c of available) groups.set(c.issuer, [...(groups.get(c.issuer) ?? []), c]);
    return [...groups.entries()];
  }, [available]);

  const add = (id: string) => {
    onChange([...selected, id]);
    setQuery('');
    inputRef.current?.focus();
  };

  return (
    <div className="picker">
      <div className="chips">
        {selected.length === 0 && <p className="muted small">No cards yet. Add the cards in your wallet.</p>}
        {selected.map((id) => {
          const card = cards.find((c) => c.id === id);
          if (!card) return null;
          return (
            <span key={id} className="chip">
              {card.name}
              <button aria-label={`Remove ${card.name}`} onClick={() => onChange(selected.filter((s) => s !== id))}>
                ×
              </button>
            </span>
          );
        })}
      </div>

      <div className="combo" onBlur={(e) => !e.currentTarget.contains(e.relatedTarget) && setOpen(false)}>
        <input
          ref={inputRef}
          type="search"
          placeholder="Search cards, e.g. Sapphire, Amex, Venture"
          value={query}
          onFocus={() => setOpen(true)}
          onChange={(e) => {
            setQuery(e.target.value);
            setOpen(true);
          }}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && available[0]) add(available[0].id);
            if (e.key === 'Escape') setOpen(false);
          }}
          aria-expanded={open}
          aria-controls="card-options"
          role="combobox"
        />
        {open && (
          <div className="dropdown" id="card-options" role="listbox">
            {grouped.length === 0 && <div className="muted small pad">No matching cards.</div>}
            {grouped.map(([issuer, list]) => (
              <div key={issuer}>
                <div className="group-label">{ISSUER_LABELS[issuer]}</div>
                {list.map((c) => (
                  <button key={c.id} className="option" role="option" aria-selected={false} onClick={() => add(c.id)}>
                    <span>{c.name}</span>
                    <span className="muted small">
                      ${c.annualFee}/yr{c.needsVerification ? ' · unverified' : ''}
                    </span>
                  </button>
                ))}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
