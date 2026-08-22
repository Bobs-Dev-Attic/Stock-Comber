"""Orchestrates the end-to-end screen: fetch -> evaluate -> rank."""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional

from .criteria import STRATEGIES
from .datasources import (
    FileCache, FinnhubSource, SecEdgarSource, StooqSource, TiingoSource,
    YahooSource,
)
from .datasources.finnhub import resolve_api_key
from .datasources.tiingo import resolve_api_key as resolve_tiingo_key
from .models import Company, Quote, ScreenResult
from .validation import is_valid_ticker

log = logging.getLogger("stock_comber")


class Screener:
    """Runs configured strategies across a universe of tickers."""

    def __init__(
        self,
        config: dict[str, Any],
        sec: Optional[SecEdgarSource] = None,
        stooq: Optional[StooqSource] = None,
        price_sources: Optional[list] = None,
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
        # Optional Finnhub source, active only when an API key is configured.
        timeout = data.get("request_timeout", 30)
        delay = data.get("request_delay_seconds", 0.2)
        self.finnhub: Optional[FinnhubSource] = None
        fh_key = resolve_api_key(config)
        if fh_key:
            # Throttle Finnhub to stay under the free-tier ~60 req/min limit.
            self.finnhub = FinnhubSource(
                fh_key, cache=cache, timeout=timeout,
                delay=data.get("finnhub_min_interval", 1.1))

        # Optional Tiingo source, active only when an API key is configured.
        # Tiingo is a *licensed* provider (real ToS + SLA), so when a key is
        # present it becomes the primary price source ahead of the free chain.
        self.tiingo: Optional[TiingoSource] = None
        tg_key = resolve_tiingo_key(config)
        if tg_key:
            self.tiingo = TiingoSource(
                tg_key, cache=cache, timeout=timeout, delay=delay)

        # Price sources are tried in order until one returns a price. When a
        # Tiingo key is configured it leads (licensed, reliable); otherwise Yahoo
        # is primary (unmetered from servers) with Stooq as the free fallback and
        # Finnhub only as a last resort — Finnhub's budget is reserved for
        # universe enrichment, not per-ticker prices.
        if price_sources is not None:
            self.price_sources = price_sources
        elif stooq is not None:
            self.price_sources = [stooq]
        else:
            self.price_sources = []
            if self.tiingo is not None:
                self.price_sources.append(self.tiingo)
            self.price_sources += [
                YahooSource(cache=cache, timeout=timeout, delay=0.0),
                StooqSource(cache=cache, timeout=timeout, delay=delay),
            ]
            if self.finnhub is not None:
                self.price_sources.append(self.finnhub)
        # Back-compat alias.
        self.stooq = stooq or (self.price_sources[-1] if self.price_sources else None)
        # Companies fetched during the most recent run(), for persistence. When
        # ``retain_companies`` is False they are not accumulated, so a memory-
        # conscious caller streaming results keeps peak memory O(1) in the number
        # of tickers (at the cost of raw-fundamentals persistence, which needs
        # them). ``run()`` keeps the default True so persistence is unchanged.
        self.retain_companies = True
        self.last_companies: dict[str, Company] = {}
        # Optional storage (for the nightly universe catalog / rotation).
        self.store = None

    def fetch_price(self, ticker: str) -> Quote:
        """Try each price source in order; return the first quote with a price."""
        if not is_valid_ticker(ticker):
            return Quote(ticker=str(ticker)[:10].upper())
        last = Quote(ticker=ticker.upper())
        for src in self.price_sources:
            try:
                quote = src.fetch_quote(ticker)
            except Exception as exc:
                log.warning("price source %s failed for %s: %s",
                            type(src).__name__, ticker, exc)
                continue
            if quote and quote.price is not None:
                return quote
            last = quote or last
        return last

    # -- universe --------------------------------------------------------
    def resolve_universe(self) -> list[str]:
        uni = self.config.get("universe", {})
        # Explicit tickers always win.
        tickers = [t.upper() for t in uni.get("tickers", []) if t]
        if tickers:
            return tickers
        if uni.get("mode") == "nightly":
            from datetime import datetime, timezone
            from .universe import build_nightly
            from .schedule import rotation_tick
            # The rotation seed advances every hour, so shorter-than-daily
            # schedules screen fresh names each run (not just each day).
            return build_nightly(
                self.config, store=self.store, finnhub=self.finnhub,
                day_ordinal=rotation_tick(datetime.now(timezone.utc)),
            )
        limit = uni.get("limit") or None
        return self.sec.list_tickers(limit=limit)

    # -- single ticker ---------------------------------------------------
    def screen_ticker(self, ticker: str) -> list[ScreenResult]:
        results: list[ScreenResult] = []
        company: Optional[Company] = None
        company_error = None
        # Reject malformed symbols before any upstream fetch (SSRF guard). Still
        # return one error result per strategy so the run stays well-formed.
        if not is_valid_ticker(ticker):
            company = Company(ticker=str(ticker)[:10].upper())
            if self.retain_companies:
                self.last_companies[company.ticker] = company
            for strat in self.config.get("strategies", []):
                res = STRATEGIES[strat](company, self.config)
                res.errors.append(f"invalid ticker symbol: {str(ticker)[:20]!r}")
                results.append(res)
            return results
        try:
            company = self.sec.fetch_company(ticker)
            if company is None:
                company_error = f"{ticker.upper()} not found in SEC ticker list"
        except Exception as exc:  # network/parse errors shouldn't abort the run
            log.warning("failed to fetch %s: %s", ticker, exc)
            company = None
            company_error = f"SEC fetch failed: {type(exc).__name__}: {exc}"
        if company is None:
            company = Company(ticker=ticker.upper())

        # Price is only needed for price-based strategies (Graham). Fetch it
        # lazily but never let a price failure sink the whole ticker.
        try:
            company.quote = self.fetch_price(ticker)
        except Exception as exc:
            log.warning("failed to fetch price for %s: %s", ticker, exc)

        # Supplementary Finnhub metrics (stored alongside the analysis). Off by
        # default — one extra Finnhub call per ticker is costly on the free tier.
        if self.finnhub is not None and self.config.get("data", {}).get(
                "finnhub_enrich_results", False):
            try:
                company.extra = self.finnhub.fetch_metrics(ticker)
            except Exception as exc:
                log.warning("finnhub metrics failed for %s: %s", ticker, exc)

        if self.retain_companies:
            self.last_companies[company.ticker] = company
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
        self.last_companies = {}
        all_results: list[ScreenResult] = []
        total = len(universe)
        for i, ticker in enumerate(universe, 1):
            if progress:
                progress(i, total, ticker)
            all_results.extend(self.screen_ticker(ticker))
        return self.rank(all_results)

    def iter_results(self, tickers: Optional[list[str]] = None,
                     progress: Optional[Callable[[int, int, str], None]] = None):
        """Stream per-ticker results without buffering the whole run.

        Yields the list of :class:`ScreenResult` for each ticker in turn. With
        ``retain_companies=False`` the source ``Company`` for each ticker is
        released before the next is fetched, so peak memory stays O(1) in the
        universe size — for large list-mode screens that don't need the run
        persisted or globally ranked. (``run()`` remains the buffered, ranked,
        persistence-friendly path.)
        """
        universe = tickers or self.resolve_universe()
        self.last_companies = {}   # reset per call, like run()
        total = len(universe)
        for i, ticker in enumerate(universe, 1):
            if progress:
                progress(i, total, ticker)
            yield self.screen_ticker(ticker)

    # -- ranking ---------------------------------------------------------
    def rank(self, results: list[ScreenResult]) -> list[ScreenResult]:
        from .scoring import overall_health

        sort_by = self.config.get("output", {}).get("sort_by", "score_pct")

        # Attach the composite 0–100 health score to every result so it can be
        # ranked on, exported, and shown. Cheap: pure math over metrics we
        # already computed. The nightly "hidden gems" run ranks by it (see
        # cli._load), surfacing the strongest businesses at the top.
        for r in results:
            if r.metrics is not None and "health_score" not in r.metrics:
                r.metrics["health_score"] = overall_health(r.metrics)

        def key(r: ScreenResult) -> tuple:
            if sort_by == "health":
                health = (r.metrics or {}).get("health_score")
                return (r.passed, health if health is not None else -1.0, r.score_pct)
            if sort_by == "score_pct":
                return (r.passed, r.score_pct)
            return (r.passed, getattr(r, sort_by, r.score_pct))

        return sorted(results, key=key, reverse=True)
