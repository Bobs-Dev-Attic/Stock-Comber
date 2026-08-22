"""Tests for the shared API audit + rate-limit guard."""

from stock_comber import apiguard


class FakeHeaders(dict):
    def get(self, k, default=None):
        return dict.get(self, k, default)


class FakeHandler:
    def __init__(self, path="/api/screen?tickers=AAPL", headers=None, command="GET"):
        self.path = path
        self.headers = FakeHeaders(headers or {"X-Forwarded-For": "9.9.9.9"})
        self.command = command
        self.client_address = ("9.9.9.9", 12345)


class FakeStore:
    """In-memory stand-in with the same audit interface as the real storage."""
    enabled = True

    def __init__(self, count=0):
        self._count = count
        self.recorded = []

    def count_api_calls(self, client, window_seconds):
        return self._count

    def record_api_call(self, endpoint, method, status, scope=None,
                        client=None, note=None):
        self.recorded.append({"endpoint": endpoint, "method": method,
                              "status": status, "scope": scope,
                              "client": client, "note": note})


def _cfg(**rl):
    base = {"enabled": True, "max_requests": 5, "window_seconds": 60, "scope": "ip"}
    base.update(rl)
    return {"api": {"audit": True, "rate_limit": base}}


def test_guard_allows_under_limit_and_audits():
    store = FakeStore(count=2)
    ok, meta = apiguard.guard(FakeHandler(), "screen", store=store, cfg=_cfg())
    assert ok is True
    assert meta["limit"] == 5 and meta["remaining"] == 2  # 5 - 2 - 1
    assert store.recorded and store.recorded[-1]["status"] == 200
    assert store.recorded[-1]["client"] == "ip:9.9.9.9"
    assert store.recorded[-1]["endpoint"] == "screen"


def test_guard_blocks_at_limit_and_records_429():
    store = FakeStore(count=5)
    ok, meta = apiguard.guard(FakeHandler(), "screen", store=store, cfg=_cfg())
    assert ok is False
    assert meta["retry_after"] == 60 and meta["remaining"] == 0
    assert store.recorded[-1]["status"] == 429
    assert store.recorded[-1]["note"] == "rate limited"


def test_guard_disabled_rate_limit_still_audits():
    store = FakeStore(count=1000)
    ok, meta = apiguard.guard(FakeHandler(), "runs", store=store,
                              cfg=_cfg(enabled=False))
    assert ok is True                       # never blocked when disabled
    assert store.recorded[-1]["status"] == 200


def test_guard_audit_off_records_nothing():
    store = FakeStore(count=0)
    cfg = _cfg()
    cfg["api"]["audit"] = False
    ok, _ = apiguard.guard(FakeHandler(), "runs", store=store, cfg=cfg)
    assert ok is True
    assert store.recorded == []


def test_guard_fails_open_without_database():
    class Disabled:
        enabled = False
    ok, meta = apiguard.guard(FakeHandler(), "screen", store=Disabled(), cfg=_cfg())
    assert ok is True and meta == {}


def test_key_scope_uses_non_secret_fingerprint():
    store = FakeStore(count=0)
    h = FakeHandler(path="/api/settings?key=supersecret", command="POST")
    ok, meta = apiguard.guard(h, "settings", store=store, cfg=_cfg(scope="key"))
    assert ok is True
    client = store.recorded[-1]["client"]
    assert client.startswith("key:") and "supersecret" not in client
    assert len(client) == len("key:") + 12


def test_client_ip_prefers_forwarded_header():
    h = FakeHandler(headers={"X-Forwarded-For": "1.2.3.4, 5.6.7.8"})
    assert apiguard._client_ip(h) == "1.2.3.4"


def test_guard_never_raises_on_storage_error():
    class Boom:
        enabled = True
        def count_api_calls(self, *a):
            raise RuntimeError("db down")
        def record_api_call(self, *a, **k):
            raise RuntimeError("db down")
    ok, meta = apiguard.guard(FakeHandler(), "screen", store=Boom(), cfg=_cfg())
    assert ok is True   # count error -> treated as 0 -> allowed; record error swallowed
