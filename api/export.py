"""Vercel serverless function: key-protected export of stored screen results.

  GET /api/export?key=YOUR_KEY&format=csv[&run=<id>][&limit=N]

Auth: requires the ``STOCK_COMBER_API_KEY`` environment variable to be set, and
the request to supply it via the ``key`` query param or the ``X-API-Key`` header.
If no key is configured on the server, the endpoint is disabled (503).

Data source: the configured database (latest run, or ``run=<id>``); if no
database is configured it falls back to the committed public/data/latest.json.
"""

from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import csv
import hmac
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from stock_comber.storage import get_storage  # noqa: E402

CSV_COLUMNS = [
    "ticker", "name", "cik", "strategy", "passed", "score", "max_score",
    "score_pct", "price", "pe_ratio", "pb_ratio", "roe_pct", "net_margin_pct",
    "current_ratio", "debt_to_equity", "graham_number",
]

_FALLBACK = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "public", "data", "latest.json",
)


def _load_run(run_id):
    store = get_storage()
    if getattr(store, "enabled", False):
        return store.get_run(int(run_id)) if run_id else store.latest_run()
    try:
        with open(_FALLBACK, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (FileNotFoundError, ValueError):
        return None


def _to_csv(results):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(CSV_COLUMNS)
    for r in results:
        m = r.get("metrics") or {}
        w.writerow([
            r.get("ticker", ""), r.get("name", "") or "", r.get("cik", "") or "",
            r.get("strategy", ""), r.get("passed", ""), r.get("score", ""),
            r.get("max_score", ""), r.get("score_pct", ""),
            m.get("price", ""), m.get("pe_ratio", ""), m.get("pb_ratio", ""),
            m.get("roe_pct", ""), m.get("net_margin_pct", ""),
            m.get("current_ratio", ""), m.get("debt_to_equity", ""),
            m.get("graham_number", ""),
        ])
    return buf.getvalue()


from stock_comber.apiguard import guard  # noqa: E402


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        ok, _rl = guard(self, "export")
        if not ok:
            self._json(429, {"error": "rate limit exceeded — slow down", **_rl})
            return
        params = parse_qs(urlparse(self.path).query)
        configured = os.environ.get("STOCK_COMBER_API_KEY")
        if not configured:
            self._json(503, {"error": "export API is not configured "
                                      "(set STOCK_COMBER_API_KEY)"})
            return
        supplied = (params.get("key", [None])[0]
                    or self.headers.get("X-API-Key"))
        if not supplied or not hmac.compare_digest(str(supplied), str(configured)):
            self._json(401, {"error": "invalid or missing API key"})
            return

        run_id = params.get("run", [None])[0]
        fmt = (params.get("format", ["json"])[0] or "json").lower()
        run = _load_run(run_id)
        if not run:
            self._json(404, {"error": "no stored run found"})
            return

        results = run.get("results", [])
        limit = params.get("limit", [None])[0]
        if limit and str(limit).isdigit():
            results = results[: int(limit)]

        if fmt == "csv":
            body = _to_csv(results).encode("utf-8")
            self._raw(200, body, "text/csv; charset=utf-8",
                      'attachment; filename="stock-comber-export.csv"')
        else:
            self._json(200, {**run, "results": results})

    def _json(self, code, obj):
        self._raw(code, json.dumps(obj, default=str).encode("utf-8"),
                  "application/json; charset=utf-8")

    def _raw(self, code, body, content_type, disposition=None):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        if disposition:
            self.send_header("Content-Disposition", disposition)
        self.end_headers()
        self.wfile.write(body)
