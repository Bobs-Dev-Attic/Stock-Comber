"""Tiingo price data source (licensed API, requires an API key).

Tiingo is a **licensed** market-data provider with an explicit terms-of-service
and redistribution policy — unlike the free Yahoo endpoint, which is unofficial
and can break without notice. When a Tiingo key is configured, prices are served
from here as the **primary** source, with Yahoo/Stooq kept as fallbacks; without
a key, Tiingo is skipped entirely and the free chain is unchanged.

Enabled only when a key is provided (``config.data.tiingo_api_key`` or the
``TIINGO_API_KEY`` environment variable). **The key is a secret** — it is sent
only in the request ``Authorization`` header (never in the URL, the cache key, or
a log line) and is never returned to the browser.

Endpoints (https://www.tiingo.com/documentation/end-of-day):
- Latest EOD:  GET /tiingo/daily/{ticker}/prices
- History:     GET /tiingo/daily/{ticker}/prices?startDate=YYYY-MM-DD&resampleFreq=monthly

Both return a JSON array of daily/monthly bars with ``close``, ``volume`` and the
dividend/split-``adjClose``. The quote uses the raw ``close`` (the actual last
traded price); the backtest history uses ``adjClose`` so splits and dividends
don't distort year-over-year returns.
"""

from __future__ import annotations

import datetime as _dt
import os
import time
from typing import Any, Optional

try:
    import requests
except Exception:  # pragma: no cover
    requests = None  # type: ignore

from ..models import Quote
from ..validation import normalize_ticker
from .cache import FileCache

BASE = "https://api.tiingo.com/tiingo/daily"


def resolve_api_key(config: Optional[dict] = None) -> Optional[str]:
    """Tiingo key from config (``data.tiingo_api_key``) or ``TIINGO_API_KEY`` env."""
    if config:
        key = config.get("data", {}).get("tiingo_api_key")
        if key:
            return key
    return os.environ.get("TIINGO_API_KEY")


def tiingo_symbol(ticker: str) -> Optional[str]:
    """Map a validated ticker to Tiingo's symbol form (lower-case, ``.``→``-``).

    Returns None for a malformed ticker so a bad symbol never reaches the URL.
    """
    norm = normalize_ticker(ticker)
    if norm is None:
        return None
    return norm.lower().replace(".", "-")


def parse_latest(rows: Any) -> Optional[tuple[str, float, Optional[float]]]:
    """Return (as_of, close, volume) from a Tiingo prices payload, or None.

    The endpoint returns bars oldest-first; the latest is the last row.
    """
    if not isinstance(rows, list) or not rows:
        return None
    row = rows[-1]
    if not isinstance(row, dict):
        return None
    close = row.get("close")
    if close is None:
        return None
    try:
        price = float(close)
    except (TypeError, ValueError):
        return None
    as_of = str(row.get("date") or "")[:10]
    vol = row.get("volume")
    volume: Optional[float]
    try:
        volume = float(vol) if vol is not None else None
    except (TypeError, ValueError):
        volume = None
    return as_of, price, volume


def parse_history(rows: Any) -> dict:
    """Return {year: year-end adjusted close} from a Tiingo prices payload.

    Keeps the last bar within each calendar year (the December close), using
    ``adjClose`` so splits/dividends don't distort an annual backtest. Falls back
    to ``close`` when ``adjClose`` is absent.
    """
    if not isinstance(rows, list):
        return {}
    best: dict[int, tuple[str, float]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        date = str(row.get("date") or "")
        val = row.get("adjClose")
        if val is None:
            val = row.get("close")
        if not date or val is None:
            continue
        try:
            year = _dt.datetime.strptime(date[:10], "%Y-%m-%d").year
            close = float(val)
        except (ValueError, TypeError):
            continue
        prev = best.get(year)
        if prev is None or date > prev[0]:
            best[year] = (date, close)
    return {y: c for y, (_d, c) in best.items()}


class TiingoSource:
    """Fetches latest price + year-end history for a ticker from Tiingo."""

    def __init__(
        self,
        api_key: str,
        cache: Optional[FileCache] = None,
        timeout: float = 30.0,
        delay: float = 0.0,
        session: Any = None,
    ) -> None:
        self.api_key = api_key
        self.cache = cache
        self.timeout = timeout
        self.delay = delay
        if session is not None:
            self.session = session
        elif requests is not None:
            self.session = requests.Session()
        else:  # pragma: no cover
            self.session = None

    def _headers(self) -> dict[str, str]:
        # The key travels only in the Authorization header — never the URL, the
        # cache key, or a log line — so it can't leak through request logging.
        return {
            "Content-Type": "application/json",
            "Authorization": f"Token {self.api_key}",
        }

    def _get(self, symbol: str, params: dict, namespace: str, key: str) -> Any:
        if self.cache is not None:
            cached = self.cache.get(namespace, key)
            if cached is not None:
                return cached
        if self.session is None:  # pragma: no cover
            raise RuntimeError("requests is not available; cannot fetch price")
        resp = self.session.get(
            f"{BASE}/{symbol}/prices",
            params=params,
            headers=self._headers(),
            timeout=self.timeout,
        )
        if self.delay:
            time.sleep(self.delay)
        resp.raise_for_status()
        data = resp.json()
        if self.cache is not None:
            self.cache.set(namespace, key, data)
        return data

    def fetch_quote(self, ticker: str) -> Quote:
        symbol = tiingo_symbol(ticker)
        if symbol is None:  # never interpolate a malformed symbol into the URL
            return Quote(ticker=str(ticker)[:10].upper(), source="tiingo")
        data = self._get(symbol, {}, "tiingo", symbol)
        parsed = parse_latest(data)
        if parsed is None:
            return Quote(ticker=normalize_ticker(ticker) or ticker.upper(),
                         source="tiingo")
        as_of, price, volume = parsed
        return Quote(ticker=normalize_ticker(ticker) or ticker.upper(),
                     price=price, as_of=as_of, source="tiingo", volume=volume)

    def fetch_history(self, ticker: str, years: int = 10) -> dict:
        """Return {year: year-end adjusted close} for the last ``years`` years."""
        symbol = tiingo_symbol(ticker)
        if symbol is None:  # never interpolate a malformed symbol into the URL
            return {}
        start = _start_date(years)
        params = {"startDate": start, "resampleFreq": "monthly"}
        ns_key = f"{symbol}:hist:{years}"
        data = self._get(symbol, params, "tiingo_hist", ns_key)
        return parse_history(data)


def _start_date(years: int) -> str:
    """A YYYY-01-01 start ``max(2, years)`` calendar years back (UTC-based)."""
    span = max(2, years)
    this_year = _dt.datetime.now(_dt.timezone.utc).year
    return f"{this_year - span}-01-01"
