"""Pull discount figures out of a gift card brand page's HTML.

Kept separate from the network code so it can be unit-tested. Source pages change
their markup without notice, so this reads the visible text, looks for labeled
percentages, and returns None for anything it can't find rather than guessing.
"""

from __future__ import annotations

import html as htmllib
import re
from dataclasses import dataclass, field

PCT = r"(\d{1,2}(?:\.\d{1,2})?)\s*%"


@dataclass
class ParsedSeller:
    name: str
    slug: str
    discount_pct: float
    notes: list[str] = field(default_factory=list)


@dataclass
class ParsedDiscount:
    discount_pct: float | None = None
    avg_12m_pct: float | None = None
    high_12m_pct: float | None = None
    sellers: list[ParsedSeller] = field(default_factory=list)


def html_to_text(raw: str) -> str:
    raw = re.sub(r"<script[\s\S]*?</script>", " ", raw, flags=re.I)
    raw = re.sub(r"<style[\s\S]*?</style>", " ", raw, flags=re.I)
    raw = re.sub(r"<[^>]+>", " ", raw)
    return re.sub(r"\s+", " ", htmllib.unescape(raw)).strip()


def _find(text: str, label: str) -> float | None:
    m = re.search(label + r"[^0-9%]{0,40}" + PCT, text, flags=re.I)
    if not m:
        return None
    n = float(m.group(1))
    return n if 0 < n <= 60 else None


def parse_discount_page(raw: str) -> ParsedDiscount:
    text = html_to_text(raw)
    meta = re.search(r"""<meta[^>]+name=["']description["'][^>]+content=["']([^"']+)["']""", raw, flags=re.I)
    meta_text = meta.group(1) if meta else ""
    return ParsedDiscount(
        discount_pct=_find(text, "current discount") or _find(meta_text, "up to") or _find(text, r"best (?:available )?discount"),
        avg_12m_pct=_find(text, r"(?:12|twelve)[- ]month average") or _find(text, r"year avg"),
        high_12m_pct=_find(text, r"highest(?: recorded)?(?: discount)?"),
        sellers=parse_sellers(raw),
    )


_ROW = re.compile(r'<div\s+role="row"', re.I)


def parse_sellers(raw: str) -> list[ParsedSeller]:
    """Sellers currently offering the card, best discount first.

    Each seller is a role="row" block with the seller's logo (alt = name), a discount cell and a
    "View Offer" link (...&giftstore=<slug>). Out-of-stock sellers are rows marked `hidden` with
    no offer link, and are skipped.
    """
    starts = [m.start() for m in _ROW.finditer(raw)]
    out: list[ParsedSeller] = []
    for i, start in enumerate(starts):
        chunk = raw[start: starts[i + 1] if i + 1 < len(starts) else len(raw)]
        opening = chunk[: chunk.find(">") + 1]
        if re.search(r"\shidden(?:[\s=>])", opening) or "data-unavailable-offer-row" in opening:
            continue
        name = re.search(r'<img[^>]+src="[^"]*gcstore/[^"]*"[^>]*alt="([^"]+)"', chunk) or \
            re.search(r'<img[^>]+alt="([^"]+)"[^>]*src="[^"]*gcstore/', chunk)
        slug = re.search(r"giftstore=([A-Za-z0-9_-]+)", chunk)
        if not name or not slug:
            continue
        cells = re.split(r'<div\s+role="cell"', chunk)[1:]
        pct = None
        for cell in cells:
            m = re.search(PCT, html_to_text("<div " + cell))
            if m:
                pct = float(m.group(1))
                break
        if pct is None or not 0 < pct <= 60:
            continue
        desktop = next((c for c in cells if re.match(r'\s*class="hidden', c)), "")
        notes = [n for n in (html_to_text(x) for x in re.findall(r"<div>(.*?)</div>", desktop, flags=re.S)) if n]
        out.append(ParsedSeller(htmllib.unescape(name.group(1)), slug.group(1), pct, list(dict.fromkeys(notes))))
    return sorted(out, key=lambda s: -s.discount_pct)
