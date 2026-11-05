// Pulls discount figures out of a gift card brand page's HTML.
// Kept separate from the network code so it can be unit-tested against saved pages.
//
// Source pages change their markup without notice, so this is deliberately forgiving:
// it reads the visible text and looks for labeled percentages, and returns undefined
// for anything it can't find rather than guessing.

export interface ParsedDiscount {
  discountPct?: number;
  avg12mPct?: number;
  high12mPct?: number;
}

const PCT = String.raw`(\d{1,2}(?:\.\d{1,2})?)\s*%`;

export function htmlToText(html: string): string {
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, ' ')
    .replace(/<style[\s\S]*?<\/style>/gi, ' ')
    .replace(/<[^>]+>/g, ' ')
    .replace(/&nbsp;/g, ' ')
    .replace(/&amp;/g, '&')
    .replace(/&#37;|&percnt;/g, '%')
    .replace(/\s+/g, ' ')
    .trim();
}

function find(text: string, label: string): number | undefined {
  const m = new RegExp(`${label}[^0-9%]{0,40}${PCT}`, 'i').exec(text);
  if (!m) return undefined;
  const n = Number(m[1]);
  return Number.isFinite(n) && n > 0 && n <= 60 ? n : undefined;
}

export function parseDiscountPage(html: string): ParsedDiscount {
  const text = htmlToText(html);
  const meta = /<meta[^>]+name=["']description["'][^>]+content=["']([^"']+)["']/i.exec(html)?.[1] ?? '';
  return {
    discountPct: find(text, 'current discount') ?? find(meta, 'up to') ?? find(text, 'best (?:available )?discount'),
    avg12mPct: find(text, '12[- ]month average'),
    high12mPct: find(text, 'highest(?: recorded)?(?: discount)?'),
  };
}
