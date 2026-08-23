"""Free, key-less online data sources for fundamentals and prices."""

from typing import Any, Optional

from .cache import FileCache
from .finnhub import FinnhubSource
from .polygon import PolygonSource
from .sec_edgar import SecEdgarSource
from .stooq import StooqSource
from .tiingo import TiingoSource
from .tiingo import resolve_api_key as _resolve_tiingo_key
from .yahoo import YahooSource

__all__ = [
    "FileCache", "FinnhubSource", "PolygonSource", "SecEdgarSource",
    "StooqSource", "TiingoSource", "YahooSource", "make_history_source",
]


def make_history_source(
    cfg: Optional[dict] = None,
    cache: Any = None,
    timeout: float = 30.0,
    delay: float = 0.0,
) -> Any:
    """Return the price-**history** source for a backtest.

    Tiingo when a key is configured (``data.tiingo_api_key`` / ``TIINGO_API_KEY``)
    — its ``fetch_history`` uses dividend/split-**adjusted** closes — else Yahoo.
    Both expose ``fetch_history(ticker, years) -> {year: close}`` with an
    identical shape, so callers need no branching. Each returned source owns a
    ``requests.Session`` (not thread-safe): build one per worker thread.
    """
    key = _resolve_tiingo_key(cfg or {})
    if key:
        return TiingoSource(key, cache=cache, timeout=timeout, delay=delay)
    return YahooSource(cache=cache, timeout=timeout, delay=delay)
