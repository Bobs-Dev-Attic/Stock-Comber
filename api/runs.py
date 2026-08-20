"""Vercel serverless function: the activity log — stored runs and searches.

  GET /api/runs[?limit=N]

Returns run metadata (date, strategies, counts) and the recent ad-hoc search
log. Full per-company results for a run come from /api/export (key-protected).
Returns empty lists when no database is configured.
"""

from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from stock_comber.storage import get_storage  # noqa: E402


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        params = parse_qs(urlparse(self.path).query)
        try:
            limit = min(100, max(1, int(params.get("limit", ["25"])[0])))
        except (ValueError, TypeError):
            limit = 25

        store = get_storage()
        runs, searches = [], []
        if getattr(store, "enabled", False):
            try:
                runs = store.list_runs(limit)
                searches = store.list_searches(limit)
            except Exception as exc:
                self._send(502, {"error": str(exc), "runs": [], "searches": []})
                return
        self._send(200, {"storage_enabled": getattr(store, "enabled", False),
                         "runs": runs, "searches": searches})

    def _send(self, code, obj):
        body = json.dumps(obj, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "public, max-age=60")
        self.end_headers()
        self.wfile.write(body)
