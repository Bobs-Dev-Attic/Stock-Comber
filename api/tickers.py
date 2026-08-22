"""Vercel serverless function: ticker autocomplete.

  GET /api/tickers?q=AAP[&limit=10]

Prefix/substring search over the SEC ticker list (cached), returning
[{ticker, name}]. Powers the dashboard's search autocomplete.
"""

from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from stock_comber.datasources import FileCache, SecEdgarSource  # noqa: E402
from stock_comber.datasources.sec_edgar import match_tickers  # noqa: E402

# Cache the ticker map across warm invocations on this instance.
_MAP = None


def _ticker_map():
    global _MAP
    if _MAP is None:
        cache = FileCache("/tmp/stock_comber_cache", ttl_hours=24)
        sec = SecEdgarSource(
            user_agent="Stock-Comber (bobchang711@gmail.com)",
            cache=cache, timeout=20, delay=0.0)
        _MAP = sec.ticker_map()
    return _MAP


from stock_comber.apiguard import guard  # noqa: E402


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        ok, _rl = guard(self, "tickers")
        if not ok:
            self._send(429, {"error": "rate limit exceeded — slow down", **_rl})
            return
        params = parse_qs(urlparse(self.path).query)
        q = params.get("q", [""])[0]
        try:
            limit = min(25, max(1, int(params.get("limit", ["10"])[0])))
        except (ValueError, TypeError):
            limit = 10
        try:
            results = match_tickers(_ticker_map(), q, limit) if q else []
        except Exception as exc:
            self._send(502, {"error": str(exc), "results": []})
            return
        self._send(200, {"query": q, "results": results})

    def _send(self, code, obj):
        body = json.dumps(obj, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "public, max-age=3600")
        self.end_headers()
        self.wfile.write(body)
