// Refreshes data/giftcards.json from each brand's live page.
//
//   GIFTCARD_SOURCE=cardbear npm run refresh:giftcards
//
// Off by default. CardBear's terms allow reasonable, personal, non-commercial reuse and ask that
// its data not be presented as real-time or guaranteed. Before enabling this for a public site,
// ask CardBear for permission (https://www.cardbear.com/contact).
//
// Politeness: one request every 2.5 seconds, travel brands only unless --all is passed,
// a plain identifying User-Agent, and no retries. Brands that fail keep their previous value.
import { readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { parseDiscountPage } from './giftcard-parse';

const DELAY_MS = 2500;
const BIG_MOVE_PTS = 10;

interface Brand {
  id: string;
  name: string;
  travel: boolean;
  discountPct: number;
  avg12mPct?: number;
  high12mPct?: number;
  liveUrl: string;
}
interface Snapshot {
  asOf: string;
  source: { name: string; url: string; note: string };
  brands: Brand[];
}

const source = process.env.GIFTCARD_SOURCE;
if (source !== 'cardbear') {
  console.log('GIFTCARD_SOURCE is not set to "cardbear"; nothing to do. See the comment at the top of this file.');
  process.exit(0);
}

const root = new URL('..', import.meta.url).pathname;
const file = join(root, 'data/giftcards.json');
const snapshot: Snapshot = JSON.parse(readFileSync(file, 'utf8'));
const all = process.argv.includes('--all');
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

const changed: string[] = [];
const bigMoves: string[] = [];
const failed: string[] = [];

for (const brand of snapshot.brands.filter((b) => all || b.travel)) {
  try {
    const res = await fetch(brand.liveUrl, { headers: { 'User-Agent': 'TravelDealSearch-refresh/0.2 (open-source hobby project)' } });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const parsed = parseDiscountPage(await res.text());
    if (parsed.discountPct === undefined) throw new Error('discount not found on page');
    if (parsed.discountPct !== brand.discountPct) {
      changed.push(`${brand.name}: ${brand.discountPct}% → ${parsed.discountPct}%`);
      if (Math.abs(parsed.discountPct - brand.discountPct) >= BIG_MOVE_PTS) bigMoves.push(brand.name);
    }
    brand.discountPct = parsed.discountPct;
    if (parsed.avg12mPct !== undefined) brand.avg12mPct = parsed.avg12mPct;
    if (parsed.high12mPct !== undefined) brand.high12mPct = parsed.high12mPct;
  } catch (e) {
    failed.push(`${brand.name}: ${(e as Error).message}`);
  }
  await sleep(DELAY_MS);
}

const checked = snapshot.brands.filter((b) => all || b.travel).length;
if (failed.length === checked) {
  console.error('Every brand failed. The page layout probably changed; update scripts/giftcard-parse.ts.');
  for (const f of failed) console.error(`  ${f}`);
  process.exit(1);
}

snapshot.asOf = new Date().toISOString().slice(0, 10);
snapshot.brands.sort((a, b) => b.discountPct - a.discountPct);
writeFileSync(file, JSON.stringify(snapshot, null, 2) + '\n');

const summary = [
  `Checked ${checked} brands on ${snapshot.asOf}.`,
  changed.length ? `\nChanged (${changed.length}):\n${changed.map((c) => `- ${c}`).join('\n')}` : '\nNo discount changes.',
  bigMoves.length ? `\n⚠️ Moved ${BIG_MOVE_PTS}+ points, double-check: ${bigMoves.join(', ')}` : '',
  failed.length ? `\nCould not read (kept previous value):\n${failed.map((f) => `- ${f}`).join('\n')}` : '',
].join('\n');
console.log(summary);
if (process.env.GITHUB_STEP_SUMMARY) writeFileSync(process.env.GITHUB_STEP_SUMMARY, summary, { flag: 'a' });
writeFileSync(join(root, '.giftcard-refresh-summary.md'), summary);
