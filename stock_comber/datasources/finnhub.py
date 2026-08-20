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
        self._rate_limited = False  # circuit breaker after repeated 429s
        self._429s = 0
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
        # Once we've hit the free-tier limit repeatedly, stop calling for the
        # rest of the run so we don't waste time on guaranteed 429s.
        if self._rate_limited:
            return None
        if self.session is None:  # pragma: no cover
            raise RuntimeError("requests is not available; cannot fetch data")
        params = dict(params, token=self.api_key)
        resp = self.session.get(f"{BASE}{path}", params=params, timeout=self.timeout)
        if self.delay:
            time.sleep(self.delay)  # throttle to stay under ~60 req/min
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

    def fetch_news(self, ticker: str, days: int = 14, limit: int = 20,
                   today: Optional[str] = None) -> list[dict]:
        """Return recent company news [{headline, datetime, url, source, summary}].

        ``today`` is an ISO date (YYYY-MM-DD); when omitted it is computed now.
        Finnhub's /company-news is available on the free tier for US symbols.
        """
        import datetime as _dt
        end = (_dt.date.fromisoformat(today) if today else _dt.date.today())
        start = end - _dt.timedelta(days=days)
        symbol = ticker.upper()
        try:
            data = self._get(
                "/company-news",
                {"symbol": symbol, "from": start.isoformat(), "to": end.isoformat()},
                "finnhub_news", f"{symbol}:{start}:{end}")
        except Exception:
            return []
        if not isinstance(data, list):
            return []
        out = []
        for a in data[:limit]:
            out.append({
                "headline": a.get("headline"),
                "datetime": a.get("datetime"),
                "url": a.get("url"),
                "source": a.get("source"),
                "summary": (a.get("summary") or "")[:280],
            })
        return out

    def fetch_peers(self, ticker: str, limit: int = 8) -> list[str]:
        """Return same-sector peer tickers for a symbol (Finnhub /stock/peers).

        The endpoint lists the company itself first; we drop it and cap the
        rest. Free tier, one call. Returns [] on any error / no data.
        """
        symbol = ticker.upper()
        try:
            data = self._get("/stock/peers", {"symbol": symbol},
                             "finnhub_peers", symbol)
        except Exception:
            return []
        if not isinstance(data, list):
            return []
        peers = []
        for p in data:
            t = str(p or "").upper().strip()
            if t and t != symbol and t not in peers:
                peers.append(t)
            if len(peers) >= limit:
                break
        return peers

    def fetch_profile(self, ticker: str, with_volume: bool = False) -> Optional[dict]:
        """Return {market_cap, sector, country, exchange, name, avg_volume}.

        Market cap is normalised to dollars (Finnhub reports it in millions).
        This is one API call by default; ``with_volume=True`` spends a second
        call on the metric bundle for average volume — off by default to conserve
        the free-tier rate limit.
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
        if with_volume:
            metrics = self.fetch_metrics(symbol) or {}
            vol_m = (metrics.get("10DayAverageTradingVolume")
                     or metrics.get("3MonthAverageTradingVolume"))
            if vol_m:
                try:
                    prof["avg_volume"] = float(vol_m) * 1e6  # reported in millions
                except (TypeError, ValueError):
                    pass
        return prof
