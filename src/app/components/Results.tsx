import { Fragment, useState } from 'react';
import type { Option } from '../../engine/types';
import { bestPerChannel } from '../../engine/compare';

const usd = (n: number) => n.toLocaleString('en-US', { style: 'currency', currency: 'USD' });

function Breakdown({ option }: { option: Option }) {
  return (
    <div className="breakdown">
      <table>
        <tbody>
          {option.breakdown.map((line, i) => (
            <tr key={i}>
              <td>{line.label}</td>
              <td className={`num ${line.amount < 0 ? 'good' : ''}`}>{line.amount < 0 ? `−${usd(-line.amount)}` : usd(line.amount)}</td>
            </tr>
          ))}
          <tr className="total">
            <td>Effective cost</td>
            <td className="num">{usd(option.effectiveCost)}</td>
          </tr>
        </tbody>
      </table>
      {option.warnings.length > 0 && (
        <ul className="warnings">
          {option.warnings.map((w, i) => (
            <li key={i}>{w}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function Results({ options }: { options: Option[] }) {
  const [showAll, setShowAll] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);

  if (options.length === 0) {
    return <p className="empty">Add at least one card and one price to see a recommendation.</p>;
  }

  const best = options[0];
  const perChannel = bestPerChannel(options);
  const runnerUp = perChannel[1];
  const list = showAll ? options : perChannel;

  return (
    <div className="results">
      <div className="winner">
        <p className="eyebrow">Best option</p>
        <h2>
          {best.channelLabel} <span className="muted">with</span> {best.cardName}
        </h2>
        <p className="big">{usd(best.effectiveCost)}</p>
        <p className="muted">
          You pay {usd(best.amountCharged)}
          {best.creditsApplied > 0 && `, get ${usd(best.creditsApplied)} in credits`}, and earn about{' '}
          {usd(best.cardPointsValue + best.loyaltyValue + best.perksValue)} in rewards.
          {runnerUp && ` That beats ${runnerUp.channelLabel} by ${usd(runnerUp.effectiveCost - best.effectiveCost)}.`}
        </p>
        <Breakdown option={best} />
      </div>

      <div className="table-head">
        <h3>{showAll ? 'Every card on every channel' : 'Best card for each channel'}</h3>
        <button className="link" onClick={() => setShowAll((s) => !s)}>
          {showAll ? 'Show best per channel' : `Show all ${options.length} combinations`}
        </button>
      </div>

      <div className="table-wrap">
        <table className="rank">
          <thead>
            <tr>
              <th>Channel</th>
              <th>Card</th>
              <th className="num">Charged</th>
              <th className="num">Rewards + credits</th>
              <th className="num">Effective cost</th>
            </tr>
          </thead>
          <tbody>
            {list.map((o) => {
              const key = `${o.channelId}:${o.cardId}`;
              const open = expanded === key;
              return (
                <Fragment key={key}>
                  <tr className={o === best ? 'top' : ''} onClick={() => setExpanded(open ? null : key)}>
                    <td>
                      <button className="row-toggle" aria-expanded={open}>
                        {o.channelLabel}
                      </button>
                    </td>
                    <td>{o.cardName}</td>
                    <td className="num">{usd(o.amountCharged)}</td>
                    <td className="num good">{usd(o.creditsApplied + o.cardPointsValue + o.loyaltyValue + o.perksValue)}</td>
                    <td className="num strong">{usd(o.effectiveCost)}</td>
                  </tr>
                  {open && (
                    <tr className="detail">
                      <td colSpan={5}>
                        <Breakdown option={o} />
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="muted small">Tap a row for the full breakdown. Annual fees are ignored: you pay them either way.</p>
    </div>
  );
}
