"""Vercel serverless function: the activity log — stored runs and searches.

  GET /api/runs[?limit=N]
  GET /api/runs?results=all[&limit=N]   -> deduped per-company roll-up

Returns run metadata (date, strategies, counts) and the recent ad-hoc search
log. With ``results=all`` it instead returns ``{results: [...]}`` — every
company across all stored runs, deduped to the latest result per
(ticker, strategy) — so the dashboard's "Full list" tab can render it like any
screen. Full raw fundamentals for a run still come from /api/export
(key-protected). Returns empty lists when no database is configured.
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
        want_results = params.get("results", [""])[0] == "all"
        default_limit = "500" if want_results else "25"
        cap = 2000 if want_results else 100
        try:
            limit = min(cap, max(1, int(params.get("limit", [default_limit])[0])))
        except (ValueError, TypeError):
            limit = int(default_limit)

        store = get_storage()
        enabled = getattr(store, "enabled", False)

        if want_results:
            results = []
            if enabled:
                try:
                    results = store.list_all_results(limit)
                except Exception as exc:
                    self._send(502, {"error": str(exc), "results": []})
                    return
            self._send(200, {"storage_enabled": enabled, "results": results,
                             "count": len(results)})
            return

        runs, searches = [], []
        if enabled:
            try:
                runs = store.list_runs(limit)
                searches = store.list_searches(limit)
            except Exception as exc:
                self._send(502, {"error": str(exc), "runs": [], "searches": []})
                return
        self._send(200, {"storage_enabled": enabled,
                         "runs": runs, "searches": searches})

    def _send(self, code, obj):
        body = json.dumps(obj, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "public, max-age=60")
        self.end_headers()
        self.wfile.write(body)
