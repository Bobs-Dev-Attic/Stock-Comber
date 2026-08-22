"""Shared API audit + rate-limit guard for the serverless handlers.

This is a library (not a serverless function), imported by the ``api/*.py``
handlers. A single call at the top of each handler both records the request in
the ``api_audit`` table and enforces the configured per-client rate limit:

    from stock_comber.apiguard import guard
    ok, rl = guard(self, "screen")
    if not ok:
        self._send(429, {"error": "rate limit exceeded", **rl}); return

Both the audit log and the *precise* cross-instance limit are backed by
Postgres, so they are active only when a database is configured. But the guard
must never take the API down, so on any storage error it **fails open** — with
one safety net: a per-warm-instance in-memory limiter still enforces a floor
when the database round-trip fails, so a database outage can't turn the limiter
fully off. Secrets are never stored: an API key is bucketed only by a short,
non-reversible fingerprint, and keyless (anonymous) requests are bucketed by
client IP so one flood can't exhaust a shared bucket for everyone.
"""

from __future__ import annotations

import hashlib
import logging
import time
from collections import OrderedDict, deque
from typing import Any
from urllib.parse import urlparse, parse_qs

log = logging.getLogger("stock_comber.apiguard")

# Defaults used for the in-memory floor when no config is loaded.
DEFAULT_LIMIT = 120
DEFAULT_WINDOW = 60


class _MemoryLimiter:
    """A tiny per-process sliding-window limiter used only as a fallback when
    the database count is unavailable. Bounded in memory: timestamps outside the
    window are pruned on access and the number of tracked buckets is capped, so
    it can't grow without limit on a warm serverless instance."""

    MAX_BUCKETS = 4096

    def __init__(self) -> None:
        self._buckets: "OrderedDict[str, deque]" = OrderedDict()

    def hit(self, client: str, limit: int, window: int, now: float = None):
        """Record a request for ``client`` and report ``(over_limit, count)``.

        A request that is already over the limit is *not* recorded, so a
        sustained flood stays pinned at the limit rather than growing the deque.
        """
        now = time.monotonic() if now is None else now
        dq = self._buckets.get(client)
        if dq is None:
            dq = deque()
            self._buckets[client] = dq
        cutoff = now - window
        while dq and dq[0] <= cutoff:
            dq.popleft()
        over = limit is not None and limit >= 1 and len(dq) >= limit
        if not over:
            dq.append(now)
        self._buckets.move_to_end(client)
        self._evict()
        return over, len(dq)

    def _evict(self) -> None:
        if len(self._buckets) <= self.MAX_BUCKETS:
            return
        # Drop drained buckets first, then the oldest, until back under the cap.
        for k in list(self._buckets.keys()):
            if not self._buckets[k]:
                del self._buckets[k]
            if len(self._buckets) <= self.MAX_BUCKETS:
                return
        while len(self._buckets) > self.MAX_BUCKETS:
            self._buckets.popitem(last=False)

    def reset(self) -> None:
        self._buckets.clear()


# Module-level fallback limiter (per warm serverless instance) and a counter of
# how often we've had to fall back — surfaced so a silent DB outage is visible
# rather than looking like "no rate limiting."
_FALLBACK = _MemoryLimiter()
_DEGRADED = {"count": 0}


def degraded_count() -> int:
    """How many times the guard has fallen back to the in-memory limiter."""
    return _DEGRADED["count"]


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
    """The rate-limit bucket id for this request under the given scope.

    Under the ``key`` scope a keyless (anonymous) request falls back to its IP,
    so anonymous callers are each limited on their own bucket rather than
    sharing (or bypassing) one.
    """
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
    ``remaining``/``scope``/``client`` for the response and headers. Fails open,
    but with an in-memory floor when the database count is unavailable.
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
            limit = int(rl.get("max_requests", DEFAULT_LIMIT))
            window = int(rl.get("window_seconds", DEFAULT_WINDOW))
            try:
                count = store.count_api_calls(client, window)
            except Exception as exc:
                # DB count failed — fall back to the per-instance memory limiter
                # so a database hiccup can't disable rate limiting entirely.
                _DEGRADED["count"] += 1
                log.warning("rate-limit DB count failed for %s; using in-memory "
                            "fallback (degraded=%d): %s",
                            endpoint, _DEGRADED["count"], exc)
                over, count = _FALLBACK.hit(client, limit, window)
                # hit() counts the in-flight request; the DB path counts only
                # prior calls, so drop 1 for a consistent `remaining` reading.
                count = max(0, count - 1)
                if over:
                    ok, retry_after = False, window
            else:
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
