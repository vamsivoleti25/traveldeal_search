// Validates every card file against schema/card.schema.json and checks cross-references.
//
//   npm run validate                      # errors fail the run, warnings are printed
//   npm run validate -- --report out.md   # also writes a Markdown health report (used by the monthly workflow)
//
// Warnings flag data that needs a human: cards not verified in STALE_AFTER_DAYS,
// dated rules (rotating categories, limited-time offers) that have expired or expire soon.
import { readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import Ajv from 'ajv';

const STALE_AFTER_DAYS = 180;
const EXPIRING_SOON_DAYS = 21;
const KNOWN_RETAIL_MERCHANTS = new Set(['amazon', 'apple']);

interface RawRule {
  channel: string | string[];
  cap?: number;
  capPeriod?: string;
  merchant?: string;
  validFrom?: string;
  validUntil?: string;
  note?: string;
  rate: number;
}
interface RawCard {
  id: string;
  name: string;
  currency: string;
  portal?: string;
  lastVerified: string | null;
  needsVerification: boolean;
  earn: RawRule[];
  credits: { merchant?: string }[];
}

const root = new URL('..', import.meta.url).pathname;
const read = (p: string) => JSON.parse(readFileSync(join(root, p), 'utf8'));
const schema = read('schema/card.schema.json');
const currencyIds = new Set((read('data/currencies.json') as { id: string }[]).map((c) => c.id));
const loyaltyIds = new Set((read('data/loyalty.json') as { id: string }[]).map((c) => c.id));

const ajv = new Ajv({ allErrors: true });
const validate = ajv.compile<RawCard>(schema);

const today = new Date().toISOString().slice(0, 10);
const daysBetween = (a: string, b: string) => (Date.parse(b) - Date.parse(a)) / 86_400_000;

const errors: string[] = [];
const stale: string[] = [];
const unverified: string[] = [];
const expired: string[] = [];
const expiringSoon: string[] = [];
const ids = new Set<string>();
const cardDir = join(root, 'data/cards');

for (const file of readdirSync(cardDir).filter((f) => f.endsWith('.json')).sort()) {
  const card: unknown = JSON.parse(readFileSync(join(cardDir, file), 'utf8'));
  if (!validate(card)) {
    for (const e of validate.errors ?? []) errors.push(`${file}: ${e.instancePath || '/'} ${e.message}`);
    continue;
  }
  if (`${card.id}.json` !== file) errors.push(`${file}: id "${card.id}" must match the file name`);
  if (ids.has(card.id)) errors.push(`${file}: duplicate id "${card.id}"`);
  ids.add(card.id);
  if (!currencyIds.has(card.currency)) errors.push(`${file}: unknown currency "${card.currency}"`);

  card.earn.forEach((rule, i) => {
    const usesPortal = rule.channel === 'portal' || (Array.isArray(rule.channel) && rule.channel.includes('portal'));
    if (usesPortal && !card.portal) errors.push(`${file}: earn[${i}] is a portal rule but the card has no "portal"`);
    if (rule.cap !== undefined && !rule.capPeriod) errors.push(`${file}: earn[${i}] has a cap but no capPeriod`);
    if (rule.merchant && !loyaltyIds.has(rule.merchant) && !KNOWN_RETAIL_MERCHANTS.has(rule.merchant)) {
      errors.push(`${file}: earn[${i}] merchant "${rule.merchant}" is not in data/loyalty.json`);
    }
    if (rule.validFrom && rule.validUntil && rule.validFrom > rule.validUntil) {
      errors.push(`${file}: earn[${i}] validFrom is after validUntil`);
    }
    const label = `${card.name}: ${rule.rate}x ${rule.note ?? ''}`.trim();
    if (rule.validUntil && rule.validUntil < today) expired.push(`${label} (ended ${rule.validUntil})`);
    else if (rule.validUntil && daysBetween(today, rule.validUntil) <= EXPIRING_SOON_DAYS) {
      expiringSoon.push(`${label} (ends ${rule.validUntil})`);
    }
  });
  for (const c of card.credits) {
    if (c.merchant && !loyaltyIds.has(c.merchant)) errors.push(`${file}: credit merchant "${c.merchant}" is not in data/loyalty.json`);
  }

  if (card.lastVerified) {
    const age = daysBetween(card.lastVerified, today);
    if (age > STALE_AFTER_DAYS) stale.push(`${card.name} (last verified ${card.lastVerified})`);
  } else if (!card.needsVerification) {
    errors.push(`${file}: lastVerified is null, so needsVerification must be true`);
  }
  if (card.needsVerification) unverified.push(card.name);
}

const section = (title: string, items: string[]) =>
  items.length ? `### ${title} (${items.length})\n\n${items.map((i) => `- ${i}`).join('\n')}\n` : '';

const reportPath = process.argv.includes('--report') ? process.argv[process.argv.indexOf('--report') + 1] : undefined;
if (reportPath) {
  const body = [
    `## Card data health — ${today}`,
    '',
    `${ids.size} cards checked.`,
    '',
    section('Expired dated rules (rotating categories, limited-time offers)', expired),
    section(`Dated rules ending within ${EXPIRING_SOON_DAYS} days`, expiringSoon),
    section(`Cards not verified in ${STALE_AFTER_DAYS}+ days`, stale),
    section('Cards marked needsVerification', unverified),
    expired.length + expiringSoon.length + stale.length === 0 ? 'Nothing needs attention.\n' : '',
  ].join('\n');
  writeFileSync(reportPath, body);
}

for (const w of expired) console.warn(`warn  expired rule: ${w}`);
for (const w of expiringSoon) console.warn(`warn  expiring soon: ${w}`);
for (const w of stale) console.warn(`warn  stale: ${w}`);
if (errors.length) {
  for (const e of errors) console.error(`error ${e}`);
  console.error(`\n${errors.length} error(s) in card data.`);
  process.exit(1);
}
console.log(
  `OK: ${ids.size} cards valid. ${unverified.length} need verification, ${stale.length} stale, ${expired.length} expired rule(s).`,
);
