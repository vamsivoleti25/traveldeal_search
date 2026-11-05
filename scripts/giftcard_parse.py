"""Pull discount figures out of a gift card brand page's HTML.

Kept separate from the network code so it can be unit-tested. Source pages change
their markup without notice, so this reads the visible text, looks for labeled
percentages, and returns None for anything it can't find rather than guessing.
"""

from __future__ import annotations

import html as htmllib
import re
from dataclasses import dataclass

PCT = r"(\d{1,2}(?:\.\d{1,2})?)\s*%"


@dataclass
class ParsedDiscount:
    discount_pct: float | None = None
    avg_12m_pct: float | None = None
    high_12m_pct: float | None = None


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
        avg_12m_pct=_find(text, r"12[- ]month average"),
        high_12m_pct=_find(text, r"highest(?: recorded)?(?: discount)?"),
    )
