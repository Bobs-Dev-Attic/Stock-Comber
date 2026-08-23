"""Full, deeper analysis of queued tickers.

The live screen is intentionally quick. Tickers a user submits are added to a
queue (``analysis_queue``) and processed here by a worker: a full screen across
all strategies, Finnhub metric enrichment, and recent news with a sentiment
grade. Each processed ticker is stored as its own run and marked done.
"""

from __future__ import annotations

import copy
import logging
from typing import Any, Optional

from .screener import Screener
from .sentiment import compute_sentiment

log = logging.getLogger("stock_comber.analysis")


_BUILTIN_LENSES = ["graham", "buffett", "piotroski", "greenblatt", "lynch", "netnet"]


def _full_config(base: dict) -> dict:
    cfg = copy.deepcopy(base)
    cfg.setdefault("data", {})["finnhub_enrich_results"] = True
    # A manual/queued analysis runs every built-in investor lens — never the
    # "custom" pseudo-strategy (custom jobs no longer emit custom rows).
    cfg["strategies"] = list(_BUILTIN_LENSES)
    cfg["universe"] = {**cfg.get("universe", {}), "mode": "list"}
    return cfg


def analyze_ticker(ticker: str, screener: Screener, news_days: int = 14):
    """Run a full analysis for one ticker, attaching news + sentiment."""
    results = screener.run([ticker])
    company = screener.last_companies.get(ticker.upper())
    if company is not None and screener.finnhub is not None:
        try:
            news = screener.finnhub.fetch_news(ticker, days=news_days)
        except Exception as exc:
            log.warning("news fetch failed for %s: %s", ticker, exc)
            news = []
        sentiment = compute_sentiment(
            [h for h in (n.get("headline") for n in news) if h])
        try:
            peers = screener.finnhub.fetch_peers(ticker)
        except Exception as exc:
            log.warning("peers fetch failed for %s: %s", ticker, exc)
            peers = []
        company.extra = {**(company.extra or {}),
                         "news": news[:15], "sentiment": sentiment, "peers": peers}
    return results, company


def process_queue(cfg: dict, store, limit: int = 5,
                  screener: Optional[Screener] = None) -> dict:
    """Pop up to ``limit`` pending tickers and fully analyse each."""
    if not getattr(store, "enabled", False):
        return {"processed": 0, "note": "no database configured"}
    tickers = store.pop_pending(limit)
    if not tickers:
        return {"processed": 0, "tickers": []}

    scr = screener or Screener(_full_config(cfg))
    scr.store = store
    done = []
    for t in tickers:
        try:
            results, _company = analyze_ticker(t, scr)
            run_id = store.save_run(results, scr.last_companies,
                                    meta={"source": "queue", "ticker": t})
            store.mark_queue(t, "done", run_id=run_id)
            done.append({"ticker": t, "run_id": run_id})
        except Exception as exc:  # never let one ticker sink the batch
            log.warning("analysis failed for %s: %s", t, exc)
            store.mark_queue(t, "error", note=str(exc)[:300])
            done.append({"ticker": t, "error": str(exc)})
    return {"processed": len(done), "tickers": done}
