"""Input validation shared across the API handlers and data sources.

The single source of truth for what a *ticker* may look like. Every place that
interpolates a ticker into an upstream URL (SEC EDGAR, Yahoo, Stooq, Finnhub)
should validate it first, so a crafted "ticker" can never redirect or poison a
fetch (an SSRF / path-injection guard). Real listed symbols are 1–10 characters,
start with a letter, and contain only letters, digits, dots and hyphens
(e.g. ``BRK.B``, ``RDS-A``).
"""

from __future__ import annotations

import re
from typing import Optional

# Start with a letter; then up to 9 of [A-Z0-9.-]. Case-folded before matching.
TICKER_RE = re.compile(r"^[A-Z][A-Z0-9.\-]{0,9}$")


def is_valid_ticker(ticker: object) -> bool:
    """True if ``ticker`` is a well-formed symbol (after upper-casing)."""
    if not isinstance(ticker, str):
        return False
    return bool(TICKER_RE.match(ticker.strip().upper()))


def normalize_ticker(ticker: object) -> Optional[str]:
    """Return the upper-cased, trimmed symbol if valid, else ``None``."""
    if not isinstance(ticker, str):
        return None
    t = ticker.strip().upper()
    return t if TICKER_RE.match(t) else None
