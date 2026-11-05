"""Refresh data/giftcards.json from each brand's live page.

    GIFTCARD_SOURCE=cardbear python scripts/refresh_giftcards.py [--all]

Off by default. CardBear's terms allow reasonable, personal, non-commercial reuse and ask
that its data not be presented as real-time or guaranteed. Ask CardBear for permission
(https://www.cardbear.com/contact) before enabling this for a public site.

Politeness: one request every 2.5 seconds, travel brands only unless --all, a plain
identifying User-Agent, no retries. Brands that fail keep their previous value.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import date
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from giftcard_parse import parse_discount_page  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data/giftcards.json"
DELAY_SECONDS = 2.5
BIG_MOVE_PTS = 10
USER_AGENT = "TravelDealSearch-refresh/0.3 (open-source hobby project)"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true", help="refresh every brand, not just travel")
    args = parser.parse_args()
    if os.environ.get("GIFTCARD_SOURCE") != "cardbear":
        print('GIFTCARD_SOURCE is not set to "cardbear"; nothing to do. See the docstring in this file.')
        return 0

    snap = json.loads(DATA.read_text(encoding="utf-8"))
    brands = [b for b in snap["brands"] if args.all or b["travel"]]
    changed, big, failed = [], [], []
    for b in brands:
        try:
            r = requests.get(b["liveUrl"], headers={"User-Agent": USER_AGENT}, timeout=20)
            r.raise_for_status()
            p = parse_discount_page(r.text)
            if p.discount_pct is None:
                raise ValueError("discount not found on page")
            if p.discount_pct != b["discountPct"]:
                changed.append(f"{b['name']}: {b['discountPct']}% → {p.discount_pct}%")
                if abs(p.discount_pct - b["discountPct"]) >= BIG_MOVE_PTS:
                    big.append(b["name"])
            b["discountPct"] = p.discount_pct
            if p.avg_12m_pct is not None:
                b["avg12mPct"] = p.avg_12m_pct
            if p.high_12m_pct is not None:
                b["high12mPct"] = p.high_12m_pct
            if p.sellers:
                b["sellers"] = [{"name": s.name, "slug": s.slug, "discountPct": s.discount_pct, "notes": s.notes}
                                for s in p.sellers]
        except Exception as e:  # one brand failing shouldn't stop the run
            failed.append(f"{b['name']}: {e}")
        time.sleep(DELAY_SECONDS)

    if len(failed) == len(brands):
        print("Every brand failed. The page layout probably changed; update scripts/giftcard_parse.py.", file=sys.stderr)
        print("\n".join(failed), file=sys.stderr)
        return 1

    snap["asOf"] = date.today().isoformat()
    snap["brands"].sort(key=lambda x: -x["discountPct"])
    DATA.write_text(json.dumps(snap, indent=2) + "\n", encoding="utf-8")

    summary = "\n".join(
        [
            f"Checked {len(brands)} brands on {snap['asOf']}.",
            f"\nChanged ({len(changed)}):\n" + "\n".join(f"- {c}" for c in changed) if changed else "\nNo discount changes.",
            f"\n⚠️ Moved {BIG_MOVE_PTS}+ points, double-check: {', '.join(big)}" if big else "",
            "\nCould not read (kept previous value):\n" + "\n".join(f"- {f}" for f in failed) if failed else "",
        ]
    )
    print(summary)
    (ROOT / ".giftcard-refresh-summary.md").write_text(summary, encoding="utf-8")
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as fh:
            fh.write(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
