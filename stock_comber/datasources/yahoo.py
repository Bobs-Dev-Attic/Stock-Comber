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
from ..validation import normalize_ticker
from .cache import FileCache

CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
_UA = "Mozilla/5.0 (compatible; Stock-Comber/1.0)"


def parse_chart(data: dict) -> Optional[tuple[str, float, Optional[float]]]:
    """Return (as_of, price, volume) from a Yahoo chart payload, or None.

    ``volume`` is the latest regular-market share volume (``regularMarketVolume``
    from the chart meta, falling back to the last non-null bar in the volume
    series), or ``None`` when the payload doesn't carry it.
    """
    try:
        result = data["chart"]["result"][0]
        meta = result["meta"]
        price = meta.get("regularMarketPrice")
        if price is None:
            return None
        ts = meta.get("regularMarketTime")
        as_of = str(ts) if ts is not None else ""
        return as_of, float(price), _parse_volume(result, meta)
    except (KeyError, IndexError, TypeError, ValueError):
        return None


def _parse_volume(result: dict, meta: dict) -> Optional[float]:
    """Latest share volume from a chart payload: meta first, then the series."""
    v = meta.get("regularMarketVolume")
    if v:
        try:
            return float(v)
        except (TypeError, ValueError):
            pass
    try:
        bars = result["indicators"]["quote"][0].get("volume") or []
    except (KeyError, IndexError, TypeError):
        return None
    for val in reversed(bars):
        if val is not None:
            try:
                return float(val)
            except (TypeError, ValueError):
                return None
    return None


def parse_history(data: dict) -> dict:
    """Return {year: close} from a Yahoo monthly-interval chart payload.

    Keeps the last available month's close within each calendar year (i.e. the
    December close), which is the natural year-end anchor for an annual backtest.
    """
    import datetime as _dt
    try:
        result = data["chart"]["result"][0]
        stamps = result.get("timestamp") or []
        closes = result["indicators"]["quote"][0].get("close") or []
    except (KeyError, IndexError, TypeError):
        return {}
    best: dict[int, tuple[int, float]] = {}
    for ts, close in zip(stamps, closes):
        if ts is None or close is None:
            continue
        try:
            year = _dt.datetime.utcfromtimestamp(int(ts)).year
        except (ValueError, OverflowError, OSError):
            continue
        prev = best.get(year)
        if prev is None or ts > prev[0]:
            best[year] = (int(ts), float(close))
    return {y: c for y, (_ts, c) in best.items()}


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
        symbol = normalize_ticker(ticker)
        if symbol is None:  # never interpolate a malformed symbol into the URL
            return Quote(ticker=str(ticker)[:10].upper(), source="yahoo")
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
        as_of, price, volume = parsed
        return Quote(ticker=symbol, price=price, as_of=as_of, source="yahoo",
                     volume=volume)

    def fetch_history(self, ticker: str, years: int = 10) -> dict:
        """Return {year: year-end close} for the last ``years`` years, or {}."""
        symbol = normalize_ticker(ticker)
        if symbol is None:  # never interpolate a malformed symbol into the URL
            return {}
        data: Optional[dict] = None
        ns_key = f"{symbol}:hist:{years}"
        if self.cache is not None:
            cached = self.cache.get("yahoo_hist", ns_key)
            if cached is not None:
                data = cached
        if data is None:
            if self.session is None:  # pragma: no cover
                raise RuntimeError("requests is not available; cannot fetch history")
            resp = self.session.get(
                CHART_URL.format(symbol=symbol),
                params={"range": f"{max(2, years)}y", "interval": "1mo"},
                headers={"User-Agent": _UA},
                timeout=self.timeout,
            )
            if self.delay:
                time.sleep(self.delay)
            resp.raise_for_status()
            data = resp.json()
            if self.cache is not None:
                self.cache.set("yahoo_hist", ns_key, data)
        return parse_history(data or {})
