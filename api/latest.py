"""Vercel serverless function: serve the most recent committed screen report.

GET /api/latest

Reads public/data/latest.json (refreshed by the scheduled GitHub Actions job)
and returns it. This is the fast path the dashboard loads on open; it works even
when no live screen has been run.
"""

from http.server import BaseHTTPRequestHandler
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
# The bundle layout can vary; check a few plausible locations for the report.
CANDIDATES = [
    os.path.join(_HERE, "..", "public", "data", "latest.json"),
    os.path.join(os.getcwd(), "public", "data", "latest.json"),
    "/var/task/public/data/latest.json",
]


def _load():
    for path in CANDIDATES:
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except (FileNotFoundError, NotADirectoryError):
            continue
    return None


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        payload = _load()
        if payload is not None:
            code = 200
        else:
            payload = {"error": "no report yet", "results": []}
            code = 404

        body = json.dumps(payload, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "public, max-age=300")
        self.end_headers()
        self.wfile.write(body)
