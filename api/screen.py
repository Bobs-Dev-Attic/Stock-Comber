"""Vercel serverless function: run a live value screen on demand.

GET /api/screen?tickers=AAPL,MSFT,JNJ&strategy=graham&strategy=buffett

Combs SEC EDGAR + Stooq live for the requested tickers (capped) and returns the
scored results as JSON. Kept small so it fits inside the function time budget;
the full universe sweep belongs in the scheduled GitHub Actions job.
"""

from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json
import os
import sys

# Make the bundled stock_comber package importable from within /api.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from stock_comber import __version__  # noqa: E402
from stock_comber.config import load_config  # noqa: E402
from stock_comber.screener import Screener  # noqa: E402

MAX_TICKERS = 10
VALID_STRATEGIES = ("graham", "buffett")


def run_screen(tickers, strategies):
    cfg = load_config()
    chosen = [s for s in strategies if s in VALID_STRATEGIES] or list(VALID_STRATEGIES)
    cfg["strategies"] = chosen
    # Serverless filesystem is read-only except /tmp; be quick and polite.
    cfg["data"]["cache_dir"] = "/tmp/stock_comber_cache"
    cfg["data"]["request_delay_seconds"] = 0
    cfg["data"]["request_timeout"] = 15
    results = Screener(cfg).run(tickers)
    return {
        "version": __version__,
        "strategies": chosen,
        "count": len({r.ticker for r in results}),
        "passing": sum(1 for r in results if r.passed),
        "results": [r.to_dict() for r in results],
    }


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        params = parse_qs(urlparse(self.path).query)
        raw = ",".join(params.get("tickers", []))
        tickers = [t.strip().upper() for t in raw.split(",") if t.strip()]
        strategies = params.get("strategy") or list(VALID_STRATEGIES)

        if not tickers:
            self._send(400, {"error": f"Provide ?tickers=AAPL,MSFT (max {MAX_TICKERS})."})
            return

        tickers = tickers[:MAX_TICKERS]
        try:
            self._send(200, run_screen(tickers, strategies))
        except Exception as exc:  # never leak a stack trace to the client
            self._send(502, {"error": f"screen failed: {exc}"})

    def _send(self, code, obj):
        body = json.dumps(obj, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "public, max-age=600")
        self.end_headers()
        self.wfile.write(body)
