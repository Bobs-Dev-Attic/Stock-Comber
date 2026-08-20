"""Orchestrates the end-to-end screen: fetch -> evaluate -> rank."""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional

from .criteria import STRATEGIES
from .datasources import FileCache, SecEdgarSource, StooqSource
from .models import Company, ScreenResult

log = logging.getLogger("stock_comber")


class Screener:
    """Runs configured strategies across a universe of tickers."""

    def __init__(
        self,
        config: dict[str, Any],
        sec: Optional[SecEdgarSource] = None,
        stooq: Optional[StooqSource] = None,
    ) -> None:
        self.config = config
        data = config.get("data", {})
        cache = FileCache(
            data.get("cache_dir", ".cache/stock_comber"),
            data.get("cache_ttl_hours", 24),
        )
        self.sec = sec or SecEdgarSource(
            user_agent=data.get("user_agent", "Stock-Comber"),
            cache=cache,
            timeout=data.get("request_timeout", 30),
            delay=data.get("request_delay_seconds", 0.2),
        )
        self.stooq = stooq or StooqSource(
            cache=cache,
            timeout=data.get("request_timeout", 30),
            delay=data.get("request_delay_seconds", 0.2),
        )

    # -- universe --------------------------------------------------------
    def resolve_universe(self) -> list[str]:
        uni = self.config.get("universe", {})
        tickers = [t.upper() for t in uni.get("tickers", []) if t]
        if tickers:
            return tickers
        limit = uni.get("limit") or None
        return self.sec.list_tickers(limit=limit)

    # -- single ticker ---------------------------------------------------
    def screen_ticker(self, ticker: str) -> list[ScreenResult]:
        results: list[ScreenResult] = []
        try:
            company = self.sec.fetch_company(ticker)
        except Exception as exc:  # network/parse errors shouldn't abort the run
            log.warning("failed to fetch %s: %s", ticker, exc)
            company = None
        if company is None:
            company = Company(ticker=ticker.upper())
            company_error = "ticker not found on SEC EDGAR"
        else:
            company_error = None

        # Price is only needed for price-based strategies (Graham). Fetch it
        # lazily but never let a price failure sink the whole ticker.
        try:
            company.quote = self.stooq.fetch_quote(ticker)
        except Exception as exc:
            log.warning("failed to fetch price for %s: %s", ticker, exc)

        for strat in self.config.get("strategies", []):
            evaluate: Callable[[Company, dict], ScreenResult] = STRATEGIES[strat]
            res = evaluate(company, self.config)
            if company_error:
                res.errors.append(company_error)
            results.append(res)
        return results

    # -- full run --------------------------------------------------------
    def run(self, tickers: Optional[list[str]] = None,
            progress: Optional[Callable[[int, int, str], None]] = None
            ) -> list[ScreenResult]:
        universe = tickers or self.resolve_universe()
        all_results: list[ScreenResult] = []
        total = len(universe)
        for i, ticker in enumerate(universe, 1):
            if progress:
                progress(i, total, ticker)
            all_results.extend(self.screen_ticker(ticker))
        return self.rank(all_results)

    # -- ranking ---------------------------------------------------------
    def rank(self, results: list[ScreenResult]) -> list[ScreenResult]:
        sort_by = self.config.get("output", {}).get("sort_by", "score_pct")

        def key(r: ScreenResult) -> tuple:
            if sort_by == "score_pct":
                return (r.passed, r.score_pct)
            return (r.passed, getattr(r, sort_by, r.score_pct))

        return sorted(results, key=key, reverse=True)
