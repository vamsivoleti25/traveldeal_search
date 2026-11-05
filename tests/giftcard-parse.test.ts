import { describe, expect, it } from 'vitest';
import { htmlToText, parseDiscountPage } from '../scripts/giftcard-parse';
import { giftCards, bestGiftCardFor } from '../src/engine/giftcards';

// A hand-written page shaped like a typical brand page. Not a copy of any real site's markup.
const page = `
<html><head><meta name="description" content="Marriott gift cards up to 9% off from 5 sellers"></head>
<body>
  <script>var x = "current discount 99%";</script>
  <section><h2>Current discount</h2><p class="big">9<span>%</span></p></section>
  <dl><dt>12-month average</dt><dd>8.2%</dd><dt>Highest recorded</dt><dd>12%</dd></dl>
</body></html>`;

describe('gift card page parser', () => {
  it('reads labeled discounts and ignores script contents', () => {
    expect(parseDiscountPage(page)).toEqual({ discountPct: 9, avg12mPct: 8.2, high12mPct: 12 });
  });

  it('falls back to the meta description', () => {
    const html = '<meta name="description" content="Save up to 6.5% on Airbnb gift cards"><body>No labels here</body>';
    expect(parseDiscountPage(html).discountPct).toBe(6.5);
  });

  it('returns undefined instead of guessing', () => {
    expect(parseDiscountPage('<body>Out of stock everywhere</body>')).toEqual({
      discountPct: undefined,
      avg12mPct: undefined,
      high12mPct: undefined,
    });
  });

  it('rejects implausible values', () => {
    expect(parseDiscountPage('<p>Current discount 95%</p>').discountPct).toBeUndefined();
  });

  it('strips tags and entities', () => {
    expect(htmlToText('<b>A&amp;B</b>&nbsp;10&#37;')).toBe('A&B 10%');
  });
});

describe('gift card snapshot', () => {
  it('has a date, a source and sane discounts', () => {
    expect(giftCards.asOf).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(giftCards.brands.length).toBeGreaterThan(20);
    for (const b of giftCards.brands) {
      expect(b.discountPct).toBeGreaterThan(0);
      expect(b.discountPct).toBeLessThanOrEqual(60);
      expect(b.liveUrl).toMatch(/^https:\/\//);
    }
  });

  it('finds chain-wide gift cards for loyalty programs', () => {
    expect(bestGiftCardFor('marriott')?.name).toBe('Marriott');
    expect(bestGiftCardFor('nonexistent')).toBeUndefined();
  });
});
