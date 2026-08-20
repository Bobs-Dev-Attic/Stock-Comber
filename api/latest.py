"""Vercel serverless function: serve the most recent committed screen report.

GET /api/latest

Reads public/data/latest.json (refreshed by the scheduled GitHub Actions job)
and returns it. This is the fast path the dashboard loads on open; it works even
when no live screen has been run.
"""

from http.server import BaseHTTPRequestHandler
import json
import os

DATA_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "public", "data", "latest.json",
)


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            with open(DATA_PATH, "r", encoding="utf-8") as fh:
                payload = json.load(fh)
            code = 200
        except FileNotFoundError:
            payload = {"error": "no report yet", "results": []}
            code = 404
        except Exception as exc:
            payload = {"error": str(exc), "results": []}
            code = 500

        body = json.dumps(payload, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "public, max-age=300")
        self.end_headers()
        self.wfile.write(body)
