"""Vercel serverless function: run a live value screen on demand.

  GET /api/screen?tickers=AAPL,MSFT,JNJ&strategy=graham&strategy=buffett
  GET /api/screen?tickers=AAPL&strategy=custom&custom=<url-encoded JSON array>

`custom` is a JSON array of rules like
  [{"name":"Cheap","metric":"pe_ratio","op":"<=","value":12}]
When present, the "custom" strategy is added automatically.

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
from stock_comber.config import load_config, validate_config  # noqa: E402
from stock_comber.screener import Screener  # noqa: E402
from stock_comber.storage import get_storage  # noqa: E402

MAX_TICKERS = 10
MAX_CUSTOM = 15
VALID_STRATEGIES = ("graham", "buffett", "custom", "piotroski",
                    "greenblatt", "lynch", "netnet")


def run_screen(tickers, strategies, custom_criteria=None):
    cfg = load_config()
    chosen = [s for s in strategies if s in VALID_STRATEGIES]
    if custom_criteria:
        cfg["custom"]["criteria"] = custom_criteria[:MAX_CUSTOM]
        if "custom" not in chosen:
            chosen.append("custom")
    if not chosen:
        chosen = ["graham", "buffett"]
    cfg["strategies"] = chosen

    problems = validate_config(cfg)
    if problems:
        return {"error": "invalid criteria: " + "; ".join(problems), "results": []}

    # Serverless filesystem is read-only except /tmp; be quick and polite.
    cfg["data"]["cache_dir"] = "/tmp/stock_comber_cache"
    cfg["data"]["request_delay_seconds"] = 0
    cfg["data"]["request_timeout"] = 25
    results = Screener(cfg).run(tickers)
    passing = sum(1 for r in results if r.passed)

    # Log the ad-hoc search to the activity log (best-effort, when a DB exists).
    try:
        store = get_storage(cfg)
        if getattr(store, "enabled", False):
            store.log_search("live", tickers, chosen, custom_criteria,
                             len({r.ticker for r in results}), passing)
    except Exception:
        pass

    return {
        "version": __version__,
        "strategies": chosen,
        "count": len({r.ticker for r in results}),
        "passing": passing,
        "results": [r.to_dict() for r in results],
    }


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        params = parse_qs(urlparse(self.path).query)
        raw = ",".join(params.get("tickers", []))
        tickers = [t.strip().upper() for t in raw.split(",") if t.strip()]
        strategies = params.get("strategy") or ["graham", "buffett"]

        custom_criteria = None
        if params.get("custom"):
            try:
                custom_criteria = json.loads(params["custom"][0])
                if not isinstance(custom_criteria, list):
                    raise ValueError("custom must be a JSON array")
            except (ValueError, json.JSONDecodeError) as exc:
                self._send(400, {"error": f"bad custom criteria: {exc}"})
                return

        if not tickers:
            self._send(400, {"error": f"Provide ?tickers=AAPL,MSFT (max {MAX_TICKERS})."})
            return

        tickers = tickers[:MAX_TICKERS]
        try:
            self._send(200, run_screen(tickers, strategies, custom_criteria))
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
