"""Polygon.io universe-enrichment source (licensed API, requires an API key).

Used like Finnhub's profile enrichment: given a ticker, return
``{market_cap, sector, country, exchange, name, avg_volume}`` so the nightly
"hidden gems" engine can classify names by sector, market-cap tier and volume
tier (see ``universe._stratified_pick``). Enabled only when a key is configured
(``config.data.polygon_api_key`` or the ``POLYGON_API_KEY`` env var).

**Rate limiting:** Polygon's free tier allows ~5 API calls/minute, so the source
throttles to a minimum interval between calls (``config.data.polygon_min_interval``,
default 12s = 5/min) and trips a circuit breaker after repeated HTTP 429s so a
run doesn't burn time on guaranteed rejections.

Endpoints (https://polygon.io/docs):
- Ticker Details v3: ``GET /v3/reference/tickers/{ticker}`` → market cap, SIC
  description (used as the sector label), name, primary exchange, locale.
- Previous close:    ``GET /v2/aggs/ticker/{ticker}/prev`` → the last trading
  day's volume (a volume signal for tiering; free tier is end-of-day).

**The key is a secret** — sent only in the ``Authorization: Bearer`` header
(never the URL, cache key, or a log line), env/DB write-only, never returned to
the browser.
"""

from __future__ import annotations

import os
import time
from typing import Any, Optional

try:
    import requests
except Exception:  # pragma: no cover
    requests = None  # type: ignore

from .cache import FileCache

BASE = "https://api.polygon.io"


def resolve_api_key(config: Optional[dict] = None) -> Optional[str]:
    """Polygon key from config (``data.polygon_api_key``) or ``POLYGON_API_KEY``."""
    if config:
        key = config.get("data", {}).get("polygon_api_key")
        if key:
            return key
    return os.environ.get("POLYGON_API_KEY")


def parse_details(data: Any) -> dict:
    """Extract enrichment fields from a Polygon Ticker Details v3 payload."""
    res = (data or {}).get("results") if isinstance(data, dict) else None
    if not isinstance(res, dict):
        return {}
    out: dict[str, Any] = {}
    mc = res.get("market_cap")
    try:
        out["market_cap"] = float(mc) if mc is not None else None
    except (TypeError, ValueError):
        out["market_cap"] = None
    # SIC description is Polygon's closest thing to a sector label.
    out["sector"] = res.get("sic_description") or None
    out["name"] = res.get("name") or None
    out["exchange"] = res.get("primary_exchange") or None
    loc = res.get("locale")
    out["country"] = (str(loc).upper() if loc else None)
    return {k: v for k, v in out.items() if v is not None}


def parse_prev_volume(data: Any) -> Optional[float]:
    """Latest trading day's share volume from a Polygon prev-close payload."""
    try:
        rows = (data or {}).get("results") or []
        v = rows[0].get("v") if rows else None
        return float(v) if v is not None else None
    except (TypeError, ValueError, IndexError, AttributeError):
        return None


class PolygonSource:
    """Enriches a ticker (sector / market cap / volume) via Polygon.io."""

    def __init__(
        self,
        api_key: str,
        cache: Optional[FileCache] = None,
        timeout: float = 20.0,
        delay: float = 12.0,          # 5 calls/min on the free tier
        with_volume: bool = True,
        session: Any = None,
    ) -> None:
        self.api_key = api_key
        self.cache = cache
        self.timeout = timeout
        self.delay = delay
        self.with_volume = with_volume
        self._rate_limited = False    # circuit breaker after repeated 429s
        self._429s = 0
        if session is not None:
            self.session = session
        elif requests is not None:
            self.session = requests.Session()
        else:  # pragma: no cover
            self.session = None

    def _headers(self) -> dict:
        # Key travels only in the Authorization header — never the URL / cache
        # key / a log line — so it can't leak through request logging.
        return {"Authorization": f"Bearer {self.api_key}"}

    def _get(self, path: str, namespace: str, key: str) -> Optional[Any]:
        if self.cache is not None:
            cached = self.cache.get(namespace, key)
            if cached is not None:
                return cached
        if self._rate_limited:            # stop hammering once we've hit the wall
            return None
        if self.session is None:  # pragma: no cover
            raise RuntimeError("requests is not available; cannot fetch data")
        resp = self.session.get(f"{BASE}{path}", headers=self._headers(),
                                timeout=self.timeout)
        if self.delay:
            time.sleep(self.delay)        # throttle to stay under 5 req/min
        if resp.status_code == 429:
            self._429s += 1
            if self._429s >= 3:
                self._rate_limited = True
            resp.raise_for_status()
        resp.raise_for_status()
        self._429s = 0
        data = resp.json()
        if self.cache is not None:
            self.cache.set(namespace, key, data)
        return data

    def fetch_profile(self, ticker: str, with_volume: Optional[bool] = None) -> Optional[dict]:
        """Return ``{market_cap, sector, country, exchange, name, avg_volume}`` or None.

        One API call for the details; a second (for the volume signal) only when
        ``with_volume`` — defaults to the source's setting — since each call
        counts against the 5/min budget.
        """
        symbol = ticker.upper()
        try:
            data = self._get(f"/v3/reference/tickers/{symbol}",
                             "polygon_details", symbol)
        except Exception:
            return None
        prof = parse_details(data)
        if not prof:
            return None
        want_vol = self.with_volume if with_volume is None else with_volume
        if want_vol:
            try:
                pv = self._get(f"/v2/aggs/ticker/{symbol}/prev?adjusted=true",
                               "polygon_prev", symbol)
                vol = parse_prev_volume(pv)
                if vol is not None:
                    prof["avg_volume"] = vol
            except Exception:
                pass
        return prof
