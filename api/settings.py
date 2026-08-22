"""Vercel serverless function: read/write screener settings.

  GET  /api/settings            -> effective settings + key/DB status (no secrets)
  POST /api/settings?key=KEY    -> merge the JSON body into stored settings (DB)

Writing requires a database (`DATABASE_URL`) and the `STOCK_COMBER_API_KEY`
(query `key` or `X-API-Key` header). Reading never returns secret values — only
booleans indicating which keys are configured.
"""

from __future__ import annotations   # `dict | None` annotations on Python 3.9

from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import copy
import hmac
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from stock_comber.config import load_config, validate_config, _deep_merge  # noqa: E402
from stock_comber.storage import get_storage  # noqa: E402
from stock_comber.universe import effective_config  # noqa: E402


# Secret config paths that must never be returned to the browser. Stored in the
# database (via the key-entry field) but write-only over the API.
_SECRET_PATHS = (("data", "finnhub_api_key"), ("data", "tiingo_api_key"))


def _redact(cfg: dict) -> dict:
    """Return a copy of ``cfg`` with stored secrets blanked out."""
    safe = copy.deepcopy(cfg)
    for path in _SECRET_PATHS:
        node = safe
        for key in path[:-1]:
            node = node.get(key) if isinstance(node, dict) else None
            if node is None:
                break
        if isinstance(node, dict) and node.get(path[-1]):
            node[path[-1]] = ""   # present-but-hidden
    return safe


def _strip_blank_secrets(incoming: dict) -> dict:
    """Remove secret paths whose value is blank so an empty form field never
    wipes a stored key (blank = leave unchanged). Mutates and returns ``incoming``."""
    for path in _SECRET_PATHS:
        node = incoming
        for key in path[:-1]:
            node = node.get(key) if isinstance(node, dict) else None
            if node is None:
                break
        if isinstance(node, dict) and node.get(path[-1], None) == "":
            node.pop(path[-1], None)
    return incoming


def _status(cfg: dict | None = None):
    data = (cfg or {}).get("data") or {}
    return {
        "storage_enabled": bool(os.environ.get("DATABASE_URL")
                                or os.environ.get("POSTGRES_URL")),
        "keys": {
            # Configured if set as an env var OR stored in the database.
            "finnhub": bool(os.environ.get("FINNHUB_API_KEY")
                            or data.get("finnhub_api_key")),
            "tiingo": bool(os.environ.get("TIINGO_API_KEY")
                           or data.get("tiingo_api_key")),
            "database": bool(os.environ.get("DATABASE_URL")
                             or os.environ.get("POSTGRES_URL")),
            "export_api": bool(os.environ.get("STOCK_COMBER_API_KEY")),
        },
    }


from stock_comber.apiguard import guard  # noqa: E402


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        ok, _rl = guard(self, "settings")
        if not ok:
            self._json(429, {"error": "rate limit exceeded — slow down", **_rl})
            return
        store = get_storage()
        cfg = effective_config(load_config(), store)
        # Whether the user has actually saved a schedule (vs. the config default).
        # Lets the dashboard show the true hosted default when unconfigured.
        try:
            schedule_configured = bool((store.get_settings() or {}).get("schedule"))
        except Exception:
            schedule_configured = False
        # Compute key status from the real config, then hide secret values.
        self._json(200, {"config": _redact(cfg), "schedule_configured": schedule_configured,
                         **_status(cfg)})

    def do_POST(self):
        ok, _rl = guard(self, "settings")
        if not ok:
            self._json(429, {"error": "rate limit exceeded — slow down", **_rl})
            return
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

        # A blank secret field means "leave the stored value unchanged" — never
        # let an empty form field wipe a stored key.
        _strip_blank_secrets(incoming)

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
        self._json(200, {"saved": True, "settings": _redact(merged),
                         **_status(merged)})

    def _json(self, code, obj):
        body = json.dumps(obj, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)
