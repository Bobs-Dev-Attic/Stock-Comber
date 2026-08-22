"""Vercel serverless function: a per-ticker signal backtest.

  GET /api/backtest?ticker=XOM[&years=10]

For each fiscal year, replays every value lens using only the fundamentals
reported through that year plus the year-end price, then measures the following
year's return — so you can see whether a lens's PASS verdicts preceded stronger
forward returns (its "edge"). SEC fundamentals + Yahoo year-end prices only;
educational, not a research backtest and not advice.
"""

from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from stock_comber import __version__  # noqa: E402
from stock_comber.analysis import _full_config  # noqa: E402
from stock_comber.backtest import backtest_all  # noqa: E402
from stock_comber.config import load_config  # noqa: E402
from stock_comber.datasources import YahooSource  # noqa: E402
from stock_comber.screener import Screener  # noqa: E402

_TICKER = re.compile(r"^[A-Z][A-Z0-9.\-]{0,9}$")


def run_backtest(ticker: str, years: int = 10) -> dict:
    cfg = _full_config(load_config())
    cfg["data"]["cache_dir"] = "/tmp/stock_comber_cache"
    cfg["data"]["request_delay_seconds"] = 0
    cfg["data"]["request_timeout"] = 25

    screener = Screener(cfg)
    company = screener.sec.fetch_company(ticker)
    if company is None:
        return {"error": f"ticker '{ticker}' not found in SEC EDGAR", "strategies": {}}
    if not company.annuals:
        return {"error": "no annual fundamentals available for this ticker",
                "ticker": ticker.upper(), "name": company.name, "strategies": {}}

    yahoo = YahooSource(timeout=25)
    try:
        price_by_year = yahoo.fetch_history(ticker, years=years)
    except Exception as exc:
        return {"error": f"could not fetch price history: {exc}",
                "ticker": ticker.upper(), "name": company.name, "strategies": {}}
    if not price_by_year:
        return {"error": "no price history available for this ticker",
                "ticker": ticker.upper(), "name": company.name, "strategies": {}}

    result = backtest_all(company, price_by_year, cfg)
    result["version"] = __version__
    return result


from stock_comber.apiguard import guard  # noqa: E402


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        ok, _rl = guard(self, "backtest")
        if not ok:
            self._send(429, {"error": "rate limit exceeded — slow down", **_rl})
            return
        params = parse_qs(urlparse(self.path).query)
        ticker = (params.get("ticker", [""])[0] or "").strip().upper()
        try:
            years = min(15, max(3, int(params.get("years", ["10"])[0])))
        except (ValueError, TypeError):
            years = 10
        if not ticker or not _TICKER.match(ticker):
            self._send(400, {"error": "Provide a valid ?ticker=XOM."})
            return
        try:
            self._send(200, run_backtest(ticker, years))
        except Exception as exc:  # never leak a stack trace
            self._send(502, {"error": f"backtest failed: {exc}"})

    def _send(self, code, obj):
        body = json.dumps(obj, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "public, max-age=3600")
        self.end_headers()
        self.wfile.write(body)
