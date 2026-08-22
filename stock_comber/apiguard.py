"""Shared API audit + rate-limit guard for the serverless handlers.

This is a library (not a serverless function), imported by the ``api/*.py``
handlers. A single call at the top of each handler both records the request in
the ``api_audit`` table and enforces the configured per-client rate limit:

    from stock_comber.apiguard import guard
    ok, rl = guard(self, "screen")
    if not ok:
        self._send(429, {"error": "rate limit exceeded", **rl}); return

Both the audit log and the limit are backed by Postgres, so they are active
only when a database is configured. The guard never raises — on any storage or
config error it fails open (allows the request) so a logging hiccup can never
take the API down. Secrets are never stored: an API key is bucketed only by a
short, non-reversible fingerprint.
"""

from __future__ import annotations

import hashlib
from typing import Any
from urllib.parse import urlparse, parse_qs


def _fingerprint(secret: str) -> str:
    """A short, non-reversible tag for an API key (never the key itself)."""
    return "key:" + hashlib.sha256(secret.encode("utf-8")).hexdigest()[:12]


def _supplied_key(handler) -> str:
    """The API key presented on the request (query ``key`` or X-API-Key), or ''."""
    try:
        q = parse_qs(urlparse(handler.path).query)
        k = (q.get("key", [None])[0]) or handler.headers.get("X-API-Key")
        return str(k) if k else ""
    except Exception:
        return ""


def _client_ip(handler) -> str:
    """Best-effort client IP behind the Vercel proxy."""
    try:
        xff = handler.headers.get("X-Forwarded-For")
        if xff:
            return xff.split(",")[0].strip()
        real = handler.headers.get("X-Real-IP")
        if real:
            return real.strip()
        addr = getattr(handler, "client_address", None)
        if addr:
            return str(addr[0])
    except Exception:
        pass
    return "unknown"


def client_id(handler, scope: str) -> str:
    """The rate-limit bucket id for this request under the given scope."""
    if scope == "global":
        return "global"
    if scope == "key":
        k = _supplied_key(handler)
        return _fingerprint(k) if k else "ip:" + _client_ip(handler)
    return "ip:" + _client_ip(handler)


def guard(handler, endpoint: str, method: str = None, store=None,
          cfg: dict[str, Any] = None):
    """Record the request and enforce the configured rate limit.

    Returns ``(ok, meta)`` where ``ok`` is False when the caller should reject
    the request with 429 and ``meta`` carries ``retry_after``/``limit``/
    ``remaining``/``scope``/``client`` for the response and headers. Fails open.
    """
    method = method or getattr(handler, "command", "GET")
    try:
        if store is None:
            from .storage import get_storage
            store = get_storage()
        if not getattr(store, "enabled", False):
            return True, {}
        if cfg is None:
            from .config import load_config
            from .universe import effective_config
            cfg = effective_config(load_config(), store)

        api = cfg.get("api", {}) if isinstance(cfg, dict) else {}
        rl = api.get("rate_limit", {}) if isinstance(api, dict) else {}
        scope = rl.get("scope", "ip")
        client = client_id(handler, scope)

        ok, retry_after, count, limit = True, 0, 0, None
        if rl.get("enabled", True):
            limit = int(rl.get("max_requests", 120))
            window = int(rl.get("window_seconds", 60))
            try:
                count = store.count_api_calls(client, window)
            except Exception:
                count = 0
            if limit >= 1 and count >= limit:
                ok, retry_after = False, window

        status = 200 if ok else 429
        if api.get("audit", True):
            try:
                store.record_api_call(endpoint, method, status, scope, client,
                                      None if ok else "rate limited")
            except Exception:
                pass

        remaining = None
        if limit is not None:
            remaining = max(0, limit - count - 1) if ok else 0
        return ok, {"retry_after": retry_after, "limit": limit,
                    "remaining": remaining, "scope": scope, "client": client}
    except Exception:
        # Never let auditing/limiting break the endpoint.
        return True, {}
