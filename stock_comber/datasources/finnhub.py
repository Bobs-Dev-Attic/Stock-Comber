"""Finnhub data source (free tier, requires an API key).

Used as an extra source alongside SEC EDGAR + Yahoo/Stooq: a real-time-ish price
(``/quote``) and a bundle of precomputed fundamentals (``/stock/metric``) that we
store alongside the analysis for additional context.

Enabled only when an API key is provided (``config.data.finnhub_api_key`` or the
``FINNHUB_API_KEY`` environment variable); otherwise it is skipped entirely.

Docs: https://finnhub.io/docs/api
"""

from __future__ import annotations

import os
import time
from typing import Any, Optional

try:
    import requests
except Exception:  # pragma: no cover
    requests = None  # type: ignore

from ..models import Quote
from .cache import FileCache

BASE = "https://finnhub.io/api/v1"


def resolve_api_key(config: Optional[dict] = None) -> Optional[str]:
    if config:
        key = config.get("data", {}).get("finnhub_api_key")
        if key:
            return key
    return os.environ.get("FINNHUB_API_KEY")


def parse_quote(data: dict) -> Optional[float]:
    """Finnhub /quote returns {c: current, ...}; 0 means no data."""
    try:
        price = data.get("c")
        return float(price) if price else None
    except (TypeError, ValueError):
        return None


class FinnhubSource:
    """Fetches price and precomputed metrics from Finnhub."""

    def __init__(
        self,
        api_key: str,
        cache: Optional[FileCache] = None,
        timeout: float = 20.0,
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

    def _get(self, path: str, params: dict, namespace: str, key: str) -> Optional[Any]:
        if self.cache is not None:
            cached = self.cache.get(namespace, key)
            if cached is not None:
                return cached
        if self.session is None:  # pragma: no cover
            raise RuntimeError("requests is not available; cannot fetch data")
        params = dict(params, token=self.api_key)
        resp = self.session.get(f"{BASE}{path}", params=params, timeout=self.timeout)
        if self.delay:
            time.sleep(self.delay)
        resp.raise_for_status()
        data = resp.json()
        if self.cache is not None:
            self.cache.set(namespace, key, data)
        return data

    def fetch_quote(self, ticker: str) -> Quote:
        symbol = ticker.upper()
        data = self._get("/quote", {"symbol": symbol}, "finnhub_quote", symbol) or {}
        price = parse_quote(data)
        return Quote(ticker=symbol, price=price, source="finnhub")

    def fetch_metrics(self, ticker: str) -> Optional[dict]:
        """Return Finnhub's precomputed ``metric`` bundle (or None)."""
        symbol = ticker.upper()
        try:
            data = self._get("/stock/metric", {"symbol": symbol, "metric": "all"},
                             "finnhub_metric", symbol)
        except Exception:
            return None
        if not data:
            return None
        return data.get("metric") or data

    def fetch_profile(self, ticker: str) -> Optional[dict]:
        """Return {market_cap, sector, country, exchange, name, avg_volume}.

        Market cap is normalised to dollars (Finnhub reports it in millions);
        average daily volume comes from the metric bundle when available.
        """
        symbol = ticker.upper()
        try:
            p = self._get("/stock/profile2", {"symbol": symbol},
                          "finnhub_profile", symbol)
        except Exception:
            return None
        if not p:
            return None
        cap_m = p.get("marketCapitalization")
        prof = {
            "name": p.get("name"),
            "sector": p.get("finnhubIndustry"),
            "country": p.get("country"),
            "exchange": p.get("exchange"),
            "market_cap": float(cap_m) * 1e6 if cap_m else None,
            "avg_volume": None,
        }
        metrics = self.fetch_metrics(symbol) or {}
        vol_m = (metrics.get("10DayAverageTradingVolume")
                 or metrics.get("3MonthAverageTradingVolume"))
        if vol_m:
            try:
                prof["avg_volume"] = float(vol_m) * 1e6  # reported in millions
            except (TypeError, ValueError):
                pass
        return prof
