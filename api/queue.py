"""Vercel serverless function: the analysis queue.

  GET  /api/queue                 -> recent queue items + status
  POST /api/queue  {"tickers": [...]}  -> enqueue tickers for full analysis

Enqueuing is open but capped and de-duplicated. Processing happens out-of-band
in the `analyze` GitHub Actions worker (news + sentiment + full screen), so this
endpoint just records intent. No-op without a database.
"""

from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from stock_comber.storage import get_storage  # noqa: E402

MAX_ENQUEUE = 25
_TICKER = re.compile(r"^[A-Z][A-Z0-9.\-]{0,9}$")


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        params = parse_qs(urlparse(self.path).query)
        try:
            limit = min(100, max(1, int(params.get("limit", ["50"])[0])))
        except (ValueError, TypeError):
            limit = 50
        store = get_storage()
        items = []
        if getattr(store, "enabled", False):
            try:
                items = store.list_queue(limit)
            except Exception as exc:
                self._send(502, {"error": str(exc), "queue": []})
                return
        self._send(200, {"storage_enabled": getattr(store, "enabled", False),
                         "queue": items})

    def do_POST(self):
        store = get_storage()
        if not getattr(store, "enabled", False):
            self._send(503, {"error": "no database configured (set DATABASE_URL)"})
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length) or b"{}")
            raw = body.get("tickers", [])
            if isinstance(raw, str):
                raw = raw.split(",")
        except (ValueError, json.JSONDecodeError) as exc:
            self._send(400, {"error": f"bad JSON body: {exc}"})
            return

        tickers, seen = [], set()
        for t in raw:
            t = str(t).strip().upper()
            if t and t not in seen and _TICKER.match(t):
                seen.add(t)
                tickers.append(t)
            if len(tickers) >= MAX_ENQUEUE:
                break
        if not tickers:
            self._send(400, {"error": "no valid tickers provided"})
            return
        try:
            n = store.enqueue(tickers)
        except Exception as exc:
            self._send(502, {"error": f"could not enqueue: {exc}"})
            return
        self._send(200, {"queued": n, "tickers": tickers})

    def _send(self, code, obj):
        body = json.dumps(obj, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)
