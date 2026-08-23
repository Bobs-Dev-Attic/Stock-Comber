"""Vercel serverless function: run a full analysis on one ticker on demand.

  GET /api/analyze?ticker=AAPL[&news_days=14]

Unlike /api/screen (quick, no enrichment) this runs the *deep* analysis a
queued ticker would get: all strategies, Finnhub metric enrichment, and recent
company news scored into an A–F sentiment grade. The result is returned inline
and — when a database is configured — stored as its own run (so it also shows
up in History and Analytics). This backs the dashboard's "Analyze now" button.

Kept to a single ticker to fit the function time budget; news + sentiment need
a FINNHUB_API_KEY (the screen still returns without one, just no news).
"""

from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from stock_comber import __version__  # noqa: E402
from stock_comber.analysis import _full_config, _jobs_criteria_for, analyze_ticker  # noqa: E402
from stock_comber.config import load_config  # noqa: E402
from stock_comber.screener import Screener  # noqa: E402
from stock_comber.storage import get_storage  # noqa: E402
from stock_comber.universe import effective_config  # noqa: E402

_TICKER = re.compile(r"^[A-Z][A-Z0-9.\-]{0,9}$")


def run_analysis(ticker: str, news_days: int = 14) -> dict:
    # Merge DB-stored settings (tuned thresholds + a stored Finnhub key) over the
    # file defaults so the settings page drives live analysis too. If the ticker
    # belongs to a saved custom job's pool, that job's criteria are re-evaluated
    # too, so the "Custom criteria" strategy still shows after a deep analysis.
    merged = effective_config(load_config(), get_storage())
    cfg = _full_config(merged, criteria=_jobs_criteria_for(ticker, merged))
    # Serverless filesystem is read-only except /tmp; be quick and polite.
    cfg["data"]["cache_dir"] = "/tmp/stock_comber_cache"
    cfg["data"]["request_delay_seconds"] = 0
    cfg["data"]["request_timeout"] = 25

    store = get_storage(cfg)
    screener = Screener(cfg)
    screener.store = store
    results, company = analyze_ticker(ticker, screener, news_days=news_days)

    extra = getattr(company, "extra", None) or {}
    news = extra.get("news", [])
    sentiment = extra.get("sentiment")
    peers = extra.get("peers", [])
    from stock_comber.signals import compute_signal
    signal = compute_signal(results)
    from stock_comber.scoring import compute_scores
    scores = compute_scores(results[0].metrics if results else {})
    # Company snapshot for the header (Finnhub profile2, one throttled call).
    profile = None
    if screener.finnhub is not None:
        try:
            profile = screener.finnhub.fetch_profile(ticker)
        except Exception:
            profile = None

    # Optional per-strategy backtest, folded into the report (default on). One
    # extra price-history fetch; never let it fail the analysis.
    backtest = None
    if cfg.get("data", {}).get("backtest_on_analysis", True):
        try:
            from stock_comber.backtest import backtest_all
            from stock_comber.datasources import make_history_source
            if company is not None and company.annuals:
                price_by_year = make_history_source(cfg, timeout=25).fetch_history(ticker, years=10)
                if price_by_year:
                    backtest = backtest_all(company, price_by_year, cfg)
        except Exception:
            backtest = None

    # Illustrative value entry zone (transparent margin-of-safety reference, not
    # advice). Derived from the fair value + backtest edge + sentiment + volume;
    # never let it fail the analysis.
    entry_zone = None
    try:
        from stock_comber.entry import suggest_entry_zone
        entry_zone = suggest_entry_zone(company, backtest, sentiment, cfg)
    except Exception:
        entry_zone = None

    run_id = None
    passing = sum(1 for r in results if r.passed)
    if getattr(store, "enabled", False):
        try:
            run_id = store.save_run(results, screener.last_companies,
                                    meta={"source": "manual", "ticker": ticker.upper()})
            store.enqueue([ticker.upper()])
            store.mark_queue(ticker.upper(), "done", run_id=run_id)
        except Exception:  # persistence must never fail the analysis
            run_id = None
        # Record the analysis in the search log so it shows in History.
        try:
            store.log_search("analyze", [ticker.upper()], cfg.get("strategies", []),
                             None, len({r.ticker for r in results}), passing)
        except Exception:
            pass

    return {
        "version": __version__,
        "ticker": ticker.upper(),
        "run_id": run_id,
        "finnhub_enabled": screener.finnhub is not None,
        "count": len({r.ticker for r in results}),
        "passing": passing,
        "results": [r.to_dict() for r in results],
        "news": news,
        "sentiment": sentiment,
        "peers": peers,
        "signal": signal,
        "scores": scores,
        "profile": profile,
        "backtest": backtest,
        "entry_zone": entry_zone,
    }


from stock_comber.apiguard import guard  # noqa: E402


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        ok, _rl = guard(self, "analyze")
        if not ok:
            self._send(429, {"error": "rate limit exceeded — slow down", **_rl})
            return
        params = parse_qs(urlparse(self.path).query)
        ticker = (params.get("ticker", [""])[0] or "").strip().upper()
        try:
            news_days = min(30, max(1, int(params.get("news_days", ["14"])[0])))
        except (ValueError, TypeError):
            news_days = 14

        if not ticker or not _TICKER.match(ticker):
            self._send(400, {"error": "Provide a valid ?ticker=AAPL."})
            return
        try:
            self._send(200, run_analysis(ticker, news_days))
        except Exception as exc:  # never leak a stack trace to the client
            self._send(502, {"error": f"analysis failed: {exc}"})

    def _send(self, code, obj):
        body = json.dumps(obj, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)
