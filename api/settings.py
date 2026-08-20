"""Vercel serverless function: read/write screener settings.

  GET  /api/settings            -> effective settings + key/DB status (no secrets)
  POST /api/settings?key=KEY    -> merge the JSON body into stored settings (DB)

Writing requires a database (`DATABASE_URL`) and the `STOCK_COMBER_API_KEY`
(query `key` or `X-API-Key` header). Reading never returns secret values — only
booleans indicating which keys are configured.
"""

from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import hmac
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from stock_comber.config import load_config, validate_config, _deep_merge  # noqa: E402
from stock_comber.storage import get_storage  # noqa: E402
from stock_comber.universe import effective_config  # noqa: E402


def _status():
    return {
        "storage_enabled": bool(os.environ.get("DATABASE_URL")
                                or os.environ.get("POSTGRES_URL")),
        "keys": {
            "finnhub": bool(os.environ.get("FINNHUB_API_KEY")),
            "database": bool(os.environ.get("DATABASE_URL")
                             or os.environ.get("POSTGRES_URL")),
            "export_api": bool(os.environ.get("STOCK_COMBER_API_KEY")),
        },
    }


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        store = get_storage()
        cfg = effective_config(load_config(), store)
        self._json(200, {"config": cfg, **_status()})

    def do_POST(self):
        configured = os.environ.get("STOCK_COMBER_API_KEY")
        if not configured:
            self._json(503, {"error": "settings API not configured "
                                      "(set STOCK_COMBER_API_KEY)"})
            return
        params = parse_qs(urlparse(self.path).query)
        supplied = params.get("key", [None])[0] or self.headers.get("X-API-Key")
        if not supplied or not hmac.compare_digest(str(supplied), str(configured)):
            self._json(401, {"error": "invalid or missing API key"})
            return

        store = get_storage()
        if not getattr(store, "enabled", False):
            self._json(503, {"error": "no database configured (set DATABASE_URL)"})
            return

        try:
            length = int(self.headers.get("Content-Length", 0))
            incoming = json.loads(self.rfile.read(length) or b"{}")
            if not isinstance(incoming, dict):
                raise ValueError("body must be a JSON object")
        except (ValueError, json.JSONDecodeError) as exc:
            self._json(400, {"error": f"bad JSON body: {exc}"})
            return

        # Validate the merged result before saving.
        problems = validate_config(_deep_merge(load_config(), incoming))
        if problems:
            self._json(400, {"error": "invalid settings", "problems": problems})
            return

        try:
            merged = _deep_merge(store.get_settings() or {}, incoming)
            store.save_settings(merged)
        except Exception as exc:
            self._json(502, {"error": f"could not save settings: {exc}"})
            return
        self._json(200, {"saved": True, "settings": merged, **_status()})

    def _json(self, code, obj):
        body = json.dumps(obj, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)
