"""Page registry, so views can switch to each other without circular imports."""

from __future__ import annotations

import streamlit as st

_PAGES: dict[str, st.Page] = {}


def register(pages: dict[str, st.Page]) -> None:
    _PAGES.update(pages)


def compare_page() -> st.Page:
    return _PAGES["compare"]
