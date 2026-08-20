"""Vercel serverless function: actionable signals (the "alerts" list).

  GET /api/signals[?runs=30&action=BUY,WATCH]

Reads the most recent stored runs, groups each run's results by ticker,
summarises them into a plain BUY / WATCH / AVOID signal (see
``stock_comber.signals``), and returns the most recent signal per ticker —
newest first, actionable ones (BUY/WATCH) by default. Read-only, no secrets;
empty without a database.

Educational only — a transparent summary of the value checklists, not advice.
"""

from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from stock_comber.signals import compute_signal  # noqa: E402
from stock_comber.storage import get_storage  # noqa: E402

VALID_ACTIONS = {"BUY", "WATCH", "AVOID", "N/A"}


def build_signals(rows: list, wanted: set) -> list:
    """Group rows by ticker (latest run wins), compute a signal for each."""
    by_ticker: dict = {}
    for r in rows:  # rows are newest-run first
        t = r.get("ticker")
        if not t:
            continue
        # First time we see a ticker is its most recent run; collect that run's rows.
        slot = by_ticker.setdefault(t, {"run_id": r.get("run_id"),
                                        "created_at": r.get("created_at"),
                                        "name": r.get("name"), "rows": []})
        if r.get("run_id") == slot["run_id"]:
            slot["rows"].append(r)

    out = []
    for ticker, slot in by_ticker.items():
        sig = compute_signal(slot["rows"])
        if wanted and sig["action"] not in wanted:
            continue
        out.append({
            "ticker": ticker, "name": slot.get("name"),
            "run_id": slot.get("run_id"), "created_at": slot.get("created_at"),
            **sig,
        })
    order = {"BUY": 0, "WATCH": 1, "AVOID": 2, "N/A": 3}
    out.sort(key=lambda s: (order.get(s["action"], 9), -s.get("score", 0)))
    return out


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        params = parse_qs(urlparse(self.path).query)
        try:
            runs = min(90, max(1, int(params.get("runs", ["30"])[0])))
        except (ValueError, TypeError):
            runs = 30
        if params.get("action"):
            wanted = {a.strip().upper() for a in params["action"][0].split(",")
                      if a.strip().upper() in VALID_ACTIONS}
        else:
            wanted = {"BUY", "WATCH"}

        store = get_storage()
        signals = []
        if getattr(store, "enabled", False):
            try:
                signals = build_signals(store.recent_results(runs), wanted)
            except Exception as exc:
                self._send(502, {"error": str(exc), "signals": []})
                return
        self._send(200, {"storage_enabled": getattr(store, "enabled", False),
                         "signals": signals})

    def _send(self, code, obj):
        body = json.dumps(obj, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "public, max-age=120")
        self.end_headers()
        self.wfile.write(body)
