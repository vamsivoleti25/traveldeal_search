"""Validate every card file against schema/card.schema.json and check cross-references.

    python scripts/validate_data.py                     # errors exit 1, warnings are printed
    python scripts/validate_data.py --report report.md  # also write a Markdown health report

Warnings flag data that needs a human: cards not verified in STALE_AFTER_DAYS days,
and dated rules (rotating categories, limited-time offers) that expired or end soon.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from jsonschema import Draft7Validator

ROOT = Path(__file__).resolve().parent.parent
STALE_AFTER_DAYS = 180
EXPIRING_SOON_DAYS = 21
KNOWN_RETAIL_MERCHANTS = {"amazon", "apple"}


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def days_between(a: str, b: str) -> int:
    return (date.fromisoformat(b) - date.fromisoformat(a)).days


def check(root: Path = ROOT, today: str | None = None) -> dict[str, list[str]]:
    today = today or date.today().isoformat()
    validator = Draft7Validator(load(root / "schema/card.schema.json"))
    currencies = {c["id"] for c in load(root / "data/currencies.json")}
    programs = {p["id"] for p in load(root / "data/loyalty.json")}
    out: dict[str, list[str]] = {k: [] for k in ("errors", "expired", "expiring", "stale", "unverified")}
    ids: set[str] = set()

    for path in sorted((root / "data/cards").glob("*.json")):
        card = load(path)
        errs = sorted(validator.iter_errors(card), key=lambda e: list(e.path))
        if errs:
            out["errors"] += [f"{path.name}: /{'/'.join(map(str, e.path))} {e.message}" for e in errs]
            continue
        if f"{card['id']}.json" != path.name:
            out["errors"].append(f"{path.name}: id {card['id']!r} must match the file name")
        if card["id"] in ids:
            out["errors"].append(f"{path.name}: duplicate id {card['id']!r}")
        ids.add(card["id"])
        if card["currency"] not in currencies:
            out["errors"].append(f"{path.name}: unknown currency {card['currency']!r}")

        for i, rule in enumerate(card["earn"]):
            ch = rule["channel"]
            if (ch == "portal" or (isinstance(ch, list) and "portal" in ch)) and not card.get("portal"):
                out["errors"].append(f"{path.name}: earn[{i}] is a portal rule but the card has no portal")
            if "cap" in rule and "capPeriod" not in rule:
                out["errors"].append(f"{path.name}: earn[{i}] has a cap but no capPeriod")
            m = rule.get("merchant")
            if m and m not in programs and m not in KNOWN_RETAIL_MERCHANTS:
                out["errors"].append(f"{path.name}: earn[{i}] merchant {m!r} is not in data/loyalty.json")
            if rule.get("validFrom") and rule.get("validUntil") and rule["validFrom"] > rule["validUntil"]:
                out["errors"].append(f"{path.name}: earn[{i}] validFrom is after validUntil")
            until = rule.get("validUntil")
            label = f"{card['name']}: {rule['rate']:g}x {rule.get('note', '')}".strip()
            if until and until < today:
                out["expired"].append(f"{label} (ended {until})")
            elif until and days_between(today, until) <= EXPIRING_SOON_DAYS:
                out["expiring"].append(f"{label} (ends {until})")
        for c in card["credits"]:
            if c.get("merchant") and c["merchant"] not in programs:
                out["errors"].append(f"{path.name}: credit merchant {c['merchant']!r} is not in data/loyalty.json")
        bags = card.get("checkedBags")
        if bags and bags["program"] not in programs:
            out["errors"].append(f"{path.name}: checkedBags program {bags['program']!r} is not in data/loyalty.json")
        for f in card.get("freeNight", []):
            if f["program"] not in programs:
                out["errors"].append(f"{path.name}: freeNight program {f['program']!r} is not in data/loyalty.json")
            if f["basis"] == "spend" and "spendThreshold" not in f:
                out["errors"].append(f"{path.name}: spend-based freeNight needs spendThreshold")

        if card["lastVerified"]:
            if days_between(card["lastVerified"], today) > STALE_AFTER_DAYS:
                out["stale"].append(f"{card['name']} (last verified {card['lastVerified']})")
        elif not card["needsVerification"]:
            out["errors"].append(f"{path.name}: lastVerified is null, so needsVerification must be true")
        if card["needsVerification"]:
            out["unverified"].append(card["name"])

    transfers_path = root / "data/transfers.json"
    if transfers_path.exists():
        t = load(transfers_path)
        for prog, cur in t.get("programCurrencies", {}).items():
            if prog not in programs:
                out["errors"].append(f"transfers.json: programCurrencies has unknown program {prog!r}")
            if cur not in currencies:
                out["errors"].append(f"transfers.json: programCurrencies has unknown currency {cur!r}")
        for cur, cards in t.get("transferCards", {}).items():
            out["errors"] += [f"transfers.json: transferCards[{cur}] has unknown card {c!r}" for c in cards if c not in ids]
        for i, tr in enumerate(t.get("transfers", []) + t.get("bonuses", [])):
            if tr["from"] not in currencies:
                out["errors"].append(f"transfers.json: entry {i} has unknown currency {tr['from']!r}")
            if tr["to"] not in programs:
                out["errors"].append(f"transfers.json: entry {i} has unknown program {tr['to']!r}")
            out["errors"] += [f"transfers.json: entry {i} has unknown card {c!r}" for c in tr.get("cards", []) if c not in ids]
        for b in t.get("bonuses", []):
            if b["until"] < today:
                out["expired"].append(f"Transfer bonus {b['from']} -> {b['to']} +{b['bonusPct']:g}% (ended {b['until']})")
            elif days_between(today, b["until"]) <= EXPIRING_SOON_DAYS:
                out["expiring"].append(f"Transfer bonus {b['from']} -> {b['to']} +{b['bonusPct']:g}% (ends {b['until']})")

    out["count"] = [str(len(ids))]
    return out


def report(result: dict[str, list[str]], today: str) -> str:
    def section(title: str, items: list[str]) -> str:
        return f"### {title} ({len(items)})\n\n" + "\n".join(f"- {i}" for i in items) + "\n" if items else ""

    needs_attention = result["expired"] or result["expiring"] or result["stale"]
    return "\n".join(
        [
            f"## Card data health — {today}",
            "",
            f"{result['count'][0]} cards checked.",
            "",
            section("Expired dated rules (rotating categories, limited-time offers)", result["expired"]),
            section(f"Dated rules ending within {EXPIRING_SOON_DAYS} days", result["expiring"]),
            section(f"Cards not verified in {STALE_AFTER_DAYS}+ days", result["stale"]),
            section("Cards marked needsVerification", result["unverified"]),
            "" if needs_attention else "Nothing needs attention.\n",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    today = date.today().isoformat()
    result = check(today=today)
    if args.report:
        args.report.write_text(report(result, today), encoding="utf-8")
    for w in result["expired"]:
        print(f"warn  expired rule: {w}")
    for w in result["expiring"]:
        print(f"warn  expiring soon: {w}")
    for w in result["stale"]:
        print(f"warn  stale: {w}")
    if result["errors"]:
        for e in result["errors"]:
            print(f"error {e}", file=sys.stderr)
        print(f"\n{len(result['errors'])} error(s) in card data.", file=sys.stderr)
        return 1
    print(
        f"OK: {result['count'][0]} cards valid. {len(result['unverified'])} need verification, "
        f"{len(result['stale'])} stale, {len(result['expired'])} expired rule(s)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
