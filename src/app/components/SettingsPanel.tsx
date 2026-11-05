import type { Card, CatalogData, UserSettings } from '../../engine/types';
import { cppFor } from '../../engine/compare';

interface Props {
  cards: Card[];
  data: CatalogData;
  settings: UserSettings;
  onChange: (s: UserSettings) => void;
}

export function SettingsPanel({ cards, data, settings, onChange }: Props) {
  const currencyIds = [...new Set(cards.map((c) => c.currency))];
  const credits = cards.flatMap((card) => card.credits.map((credit) => ({ card, credit })));
  const programs = data.loyalty;

  return (
    <div className="settings">
      <fieldset>
        <legend>How should points be valued?</legend>
        <div className="segmented" role="radiogroup">
          {(['cash', 'transfer'] as const).map((mode) => (
            <button
              key={mode}
              role="radio"
              aria-checked={settings.valuationMode === mode}
              className={settings.valuationMode === mode ? 'on' : ''}
              onClick={() => onChange({ ...settings, valuationMode: mode })}
            >
              {mode === 'cash' ? 'Cash value' : 'Transfer partners'}
            </button>
          ))}
        </div>
        <p className="muted small">
          {settings.valuationMode === 'cash'
            ? 'Conservative: what points are worth as statement credit or simple travel redemption.'
            : 'Typical value when you move points to airline or hotel partners.'}
        </p>
      </fieldset>

      {currencyIds.length > 0 && (
        <fieldset>
          <legend>Cents per point</legend>
          {currencyIds.map((id) => {
            const currency = data.currencies.find((c) => c.id === id);
            const override = settings.cppOverrides?.[id];
            return (
              <label key={id} className="inline">
                <span>{currency?.name ?? id}</span>
                <input
                  type="number"
                  step="0.05"
                  min={0}
                  value={override ?? ''}
                  placeholder={String(cppFor(id, data, { ...settings, cppOverrides: {} }))}
                  onChange={(e) => {
                    const next = { ...settings.cppOverrides };
                    if (e.target.value === '') delete next[id];
                    else next[id] = Number(e.target.value);
                    onChange({ ...settings, cppOverrides: next });
                  }}
                />
                <span className="muted small">¢</span>
              </label>
            );
          })}
        </fieldset>
      )}

      {credits.length > 0 && (
        <fieldset>
          <legend>Credits already used this period</legend>
          {credits.map(({ card, credit }) => {
            const key = `${card.id}:${credit.id}`;
            return (
              <label key={key} className="inline">
                <span>
                  {credit.name}
                  <br />
                  <small className="muted">{card.name}</small>
                </span>
                <input
                  type="number"
                  min={0}
                  max={credit.amount}
                  value={settings.creditsUsed?.[key] ?? ''}
                  placeholder="0"
                  onChange={(e) =>
                    onChange({ ...settings, creditsUsed: { ...settings.creditsUsed, [key]: Number(e.target.value) || 0 } })
                  }
                />
                <span className="muted small">of ${credit.amount}</span>
              </label>
            );
          })}
        </fieldset>
      )}

      <fieldset>
        <legend>Elite status</legend>
        {programs.map((p) => (
          <label key={p.id} className="inline">
            <span>{p.name}</span>
            <select
              value={settings.eliteStatus?.[p.id] ?? 'member'}
              onChange={(e) => onChange({ ...settings, eliteStatus: { ...settings.eliteStatus, [p.id]: e.target.value } })}
            >
              {Object.keys(p.eliteBonus).map((s) => (
                <option key={s} value={s}>
                  {s.replace(/_/g, ' ')}
                </option>
              ))}
            </select>
          </label>
        ))}
      </fieldset>
    </div>
  );
}
