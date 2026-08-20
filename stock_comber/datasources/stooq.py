"""Stooq price data source (free, no API key).

Stooq serves daily OHLC history as CSV. We only need the latest close to
compute price-based ratios (P/E, P/B, Graham number).

Endpoint: https://stooq.com/q/d/l/?s={symbol}&i=d
US tickers are queried with a ``.us`` suffix (e.g. ``aapl.us``).
"""

from __future__ import annotations

import csv
import io
import time
from typing import Any, Optional

try:
    import requests
except Exception:  # pragma: no cover
    requests = None  # type: ignore

from ..models import Quote
from .cache import FileCache

QUOTE_URL = "https://stooq.com/q/d/l/?s={symbol}&i=d"


def parse_latest_close(csv_text: str) -> Optional[tuple[str, float]]:
    """Return (date, close) of the most recent row, or None if unparseable."""
    reader = csv.DictReader(io.StringIO(csv_text))
    last: Optional[dict[str, str]] = None
    for row in reader:
        if row.get("Close") not in (None, "", "N/D"):
            last = row
    if not last:
        return None
    try:
        return last.get("Date", ""), float(last["Close"])
    except (ValueError, KeyError):
        return None


class StooqSource:
    """Fetches the latest close price for a US ticker from Stooq."""

    def __init__(
        self,
        cache: Optional[FileCache] = None,
        timeout: float = 30.0,
        delay: float = 0.2,
        session: Any = None,
    ) -> None:
        self.cache = cache
        self.timeout = timeout
        self.delay = delay
        if session is not None:
            self.session = session
        elif requests is not None:
            self.session = requests.Session()
        else:  # pragma: no cover
            self.session = None

    def _symbol(self, ticker: str) -> str:
        t = ticker.lower().replace(".", "-")
        return t if "." in ticker else f"{t}.us"

    def fetch_quote(self, ticker: str) -> Quote:
        symbol = self._symbol(ticker)
        csv_text: Optional[str] = None
        if self.cache is not None:
            cached = self.cache.get("stooq", symbol)
            if cached is not None:
                csv_text = cached
        if csv_text is None:
            if self.session is None:  # pragma: no cover
                raise RuntimeError("requests is not available; cannot fetch price")
            resp = self.session.get(
                QUOTE_URL.format(symbol=symbol), timeout=self.timeout
            )
            if self.delay:
                time.sleep(self.delay)
            resp.raise_for_status()
            csv_text = resp.text
            if self.cache is not None:
                self.cache.set("stooq", symbol, csv_text)
        parsed = parse_latest_close(csv_text or "")
        if parsed is None:
            return Quote(ticker=ticker.upper(), source="stooq")
        as_of, price = parsed
        return Quote(ticker=ticker.upper(), price=price, as_of=as_of, source="stooq")
