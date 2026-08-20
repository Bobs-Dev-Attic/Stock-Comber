"""Vercel serverless function: the investment thesis tracker.

  GET    /api/thesis                      -> list stored theses + statuses
  POST   /api/thesis?key=…  {ticker, note, conditions:[{metric,op,value}]}
                                           -> create a thesis (snapshots a baseline)
  DELETE /api/thesis?key=…&id=N           -> delete a thesis

Write operations require the STOCK_COMBER_API_KEY (same gate as settings/export).
Creating a thesis screens the ticker once to snapshot the baseline metrics and
record an initial check. No-op without a database.
"""

from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import hmac
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from stock_comber.config import load_config  # noqa: E402
from stock_comber.screener import Screener  # noqa: E402
from stock_comber.storage import get_storage  # noqa: E402
from stock_comber.thesis import (  # noqa: E402
    evaluate_thesis, snapshot_metrics, validate_thesis)

_TICKER = re.compile(r"^[A-Z][A-Z0-9.\-]{0,9}$")
MAX_CONDITIONS = 15


def _authorized(handler) -> bool:
    configured = os.environ.get("STOCK_COMBER_API_KEY")
    if not configured:
        return False
    params = parse_qs(urlparse(handler.path).query)
    supplied = params.get("key", [None])[0] or handler.headers.get("X-API-Key")
    return bool(supplied) and hmac.compare_digest(str(supplied), str(configured))


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        store = get_storage()
        theses = []
        if getattr(store, "enabled", False):
            try:
                theses = store.list_theses(100)
            except Exception as exc:
                self._json(502, {"error": str(exc), "theses": []})
                return
        self._json(200, {"storage_enabled": getattr(store, "enabled", False),
                         "theses": theses})

    def do_POST(self):
        if not os.environ.get("STOCK_COMBER_API_KEY"):
            self._json(503, {"error": "thesis API not configured (set STOCK_COMBER_API_KEY)"})
            return
        if not _authorized(self):
            self._json(401, {"error": "invalid or missing API key"})
            return
        store = get_storage()
        if not getattr(store, "enabled", False):
            self._json(503, {"error": "no database configured (set DATABASE_URL)"})
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length) or b"{}")
            if not isinstance(body, dict):
                raise ValueError("body must be a JSON object")
        except (ValueError, json.JSONDecodeError) as exc:
            self._json(400, {"error": f"bad JSON body: {exc}"})
            return

        ticker = str(body.get("ticker", "")).strip().upper()
        note = (body.get("note") or "").strip()[:2000]
        conditions = body.get("conditions") or []
        if not isinstance(conditions, list):
            self._json(400, {"error": "conditions must be a list"})
            return
        conditions = conditions[:MAX_CONDITIONS]
        problems = validate_thesis(ticker, conditions)
        if not _TICKER.match(ticker):
            problems.append("ticker is not a valid symbol")
        if problems:
            self._json(400, {"error": "invalid thesis", "problems": problems})
            return

        # Snapshot the baseline by screening the ticker once.
        try:
            cfg = load_config()
            cfg["data"]["cache_dir"] = "/tmp/stock_comber_cache"
            cfg["data"]["request_delay_seconds"] = 0
            cfg["data"]["request_timeout"] = 25
            results = Screener(cfg).run([ticker])
            baseline = snapshot_metrics(results[0].metrics if results else {})
        except Exception as exc:
            self._json(502, {"error": f"could not snapshot metrics: {exc}"})
            return

        try:
            tid = store.create_thesis(ticker, note, conditions, baseline)
        except Exception as exc:
            self._json(502, {"error": f"could not save thesis: {exc}"})
            return
        ev = evaluate_thesis(conditions, baseline, baseline)
        self._json(200, {"id": tid, "ticker": ticker, "status": ev["status"],
                         "baseline": baseline, "checks": ev["checks"]})

    def do_DELETE(self):
        if not _authorized(self):
            self._json(401, {"error": "invalid or missing API key"})
            return
        store = get_storage()
        if not getattr(store, "enabled", False):
            self._json(503, {"error": "no database configured"})
            return
        params = parse_qs(urlparse(self.path).query)
        try:
            tid = int(params.get("id", [""])[0])
        except (ValueError, TypeError):
            self._json(400, {"error": "id query parameter required"})
            return
        try:
            deleted = store.delete_thesis(tid)
        except Exception as exc:
            self._json(502, {"error": str(exc)})
            return
        self._json(200 if deleted else 404, {"deleted": deleted, "id": tid})

    def _json(self, code, obj):
        body = json.dumps(obj, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)
