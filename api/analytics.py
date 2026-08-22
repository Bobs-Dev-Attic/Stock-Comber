"""Vercel serverless function: aggregated analytics for the charts view.

  GET /api/analytics[?runs=N]

Returns read-only, non-sensitive aggregations over the stored history:
runs-over-time (screened vs. passing), the most frequently passing tickers,
passing results by sector, and the news-sentiment grade distribution.
Returns empty series when no database is configured.
"""

from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from stock_comber.storage import get_storage  # noqa: E402


from stock_comber.apiguard import guard  # noqa: E402


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        ok, _rl = guard(self, "analytics")
        if not ok:
            self._send(429, {"error": "rate limit exceeded — slow down", **_rl})
            return
        params = parse_qs(urlparse(self.path).query)
        try:
            run_limit = min(90, max(1, int(params.get("runs", ["30"])[0])))
        except (ValueError, TypeError):
            run_limit = 30

        store = get_storage()
        data = {"runs": [], "top_tickers": [], "sectors": [], "sentiment": [],
                "health": []}
        if getattr(store, "enabled", False):
            try:
                data = store.analytics(run_limit)
            except Exception as exc:
                self._send(502, {"error": str(exc), **data})
                return
        self._send(200, {"storage_enabled": getattr(store, "enabled", False),
                         **data})

    def _send(self, code, obj):
        body = json.dumps(obj, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "public, max-age=120")
        self.end_headers()
        self.wfile.write(body)
