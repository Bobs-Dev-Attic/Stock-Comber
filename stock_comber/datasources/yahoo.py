"""Yahoo Finance price source (free, no API key).

Uses the public chart endpoint, which returns the latest regular-market price
and generally works from server IPs where Stooq rate-limits. Used as the primary
price source with Stooq as a fallback.

Endpoint: https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=1d&interval=1d
"""

from __future__ import annotations

import time
from typing import Any, Optional

try:
    import requests
except Exception:  # pragma: no cover
    requests = None  # type: ignore

from ..models import Quote
from .cache import FileCache

CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
_UA = "Mozilla/5.0 (compatible; Stock-Comber/1.0)"


def parse_chart(data: dict) -> Optional[tuple[str, float]]:
    """Return (as_of, price) from a Yahoo chart payload, or None."""
    try:
        result = data["chart"]["result"][0]
        meta = result["meta"]
        price = meta.get("regularMarketPrice")
        if price is None:
            return None
        ts = meta.get("regularMarketTime")
        as_of = str(ts) if ts is not None else ""
        return as_of, float(price)
    except (KeyError, IndexError, TypeError, ValueError):
        return None


class YahooSource:
    """Fetches the latest market price for a ticker from Yahoo Finance."""

    def __init__(
        self,
        cache: Optional[FileCache] = None,
        timeout: float = 30.0,
        delay: float = 0.0,
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

    def fetch_quote(self, ticker: str) -> Quote:
        symbol = ticker.upper()
        data: Optional[dict] = None
        if self.cache is not None:
            cached = self.cache.get("yahoo", symbol)
            if cached is not None:
                data = cached
        if data is None:
            if self.session is None:  # pragma: no cover
                raise RuntimeError("requests is not available; cannot fetch price")
            resp = self.session.get(
                CHART_URL.format(symbol=symbol),
                params={"range": "1d", "interval": "1d"},
                headers={"User-Agent": _UA},
                timeout=self.timeout,
            )
            if self.delay:
                time.sleep(self.delay)
            resp.raise_for_status()
            data = resp.json()
            if self.cache is not None:
                self.cache.set("yahoo", symbol, data)
        parsed = parse_chart(data or {})
        if parsed is None:
            return Quote(ticker=symbol, source="yahoo")
        as_of, price = parsed
        return Quote(ticker=symbol, price=price, as_of=as_of, source="yahoo")
