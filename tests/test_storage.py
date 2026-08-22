import json

from stock_comber.criteria import evaluate_graham
from stock_comber.storage import (
    NullStorage, PostgresStorage, _raw_row, _result_row, get_storage, resolve_dsn,
)


def test_get_storage_null_without_dsn(monkeypatch, config):
    for var in ("DATABASE_URL", "POSTGRES_URL", "POSTGRES_PRISMA_URL",
                "STOCK_COMBER_DATABASE_URL"):
        monkeypatch.delenv(var, raising=False)
    store = get_storage(config)
    assert isinstance(store, NullStorage)
    assert store.enabled is False
    assert store.save_run([], {}) is None
    assert store.latest_run() is None


def test_get_storage_postgres_with_env(monkeypatch, config):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@host/db")
    store = get_storage(config)
    assert isinstance(store, PostgresStorage)
    assert store.enabled is True
    assert store.dsn.endswith("/db")


def test_config_dsn_takes_precedence(monkeypatch, config):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    config["storage"]["dsn"] = "postgresql://from/config"
    assert resolve_dsn(config) == "postgresql://from/config"


def test_result_row_shape_and_json(strong_company, config):
    res = evaluate_graham(strong_company, config)
    row = _result_row(7, res)
    assert row[0] == 7
    assert row[1] == "STRONG"
    assert row[4] == "graham"
    # metrics/criteria/errors are JSON-encoded strings
    assert isinstance(row[9], str) and json.loads(row[9])["revenue"] is not None
    assert isinstance(json.loads(row[10]), list)
    assert isinstance(json.loads(row[11]), list)


def test_raw_row_serializes_company(strong_company):
    row = _raw_row(3, strong_company)
    assert row[0] == 3 and row[1] == "STRONG"
    annuals = json.loads(row[3])
    assert len(annuals) == len(strong_company.annuals)
    quote = json.loads(row[4])
    assert quote["price"] == 40.0


def test_null_storage_analytics_shape():
    data = NullStorage().analytics()
    assert set(data) == {"runs", "top_tickers", "sectors", "sentiment", "health"}
    assert all(data[k] == [] for k in data)


def test_null_storage_list_all_results_empty():
    assert NullStorage().list_all_results() == []
    assert NullStorage().list_all_results(limit=10) == []


def test_null_storage_api_audit_noop():
    s = NullStorage()
    assert s.record_api_call("screen", "GET", 200, "ip", "ip:1.2.3.4") is None
    assert s.list_api_audit() == []
    assert s.count_api_calls("ip:1.2.3.4", 60) == 0


def test_null_storage_recently_screened_empty():
    assert NullStorage().recently_screened(90) == set()


def test_resolve_dsn_prefers_pooled_endpoint(monkeypatch):
    for var in ("DATABASE_URL", "POSTGRES_URL", "POSTGRES_PRISMA_URL",
                "STOCK_COMBER_DATABASE_URL", "STOCK_COMBER_DATABASE_URL_POOLED"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://direct/db")
    monkeypatch.setenv("STOCK_COMBER_DATABASE_URL_POOLED", "postgresql://pooler/db")
    assert resolve_dsn() == "postgresql://pooler/db"
    # Without the pooled var, the usual DATABASE_URL still wins.
    monkeypatch.delenv("STOCK_COMBER_DATABASE_URL_POOLED", raising=False)
    assert resolve_dsn() == "postgresql://direct/db"


class _FakeCursor:
    def __init__(self, row):
        self._row = row
    def __enter__(self):
        return self
    def __exit__(self, *a):
        return False
    def execute(self, *a, **k):
        return None
    def fetchone(self):
        return self._row


class _FakeConn:
    def __init__(self, row):
        self._row = row
    def __enter__(self):
        return self
    def __exit__(self, *a):
        return False
    def cursor(self):
        return _FakeCursor(self._row)
    def commit(self):
        return None


def test_settings_cache_serves_and_refreshes(monkeypatch):
    from stock_comber import storage
    storage._SETTINGS_CACHE.clear()
    monkeypatch.setattr(storage, "_SETTINGS_TTL", 30.0)
    store = PostgresStorage("postgresql://u:p@host/cachedb")
    store._schema_ready = True

    calls = {"n": 0}

    def fake_connect():
        calls["n"] += 1
        return _FakeConn(({"strategies": ["graham"]},))
    monkeypatch.setattr(store, "_connect", fake_connect)

    first = store.get_settings()
    assert first == {"strategies": ["graham"]}
    assert calls["n"] == 1
    # Second read within the TTL is served from cache — no new DB hit.
    second = store.get_settings()
    assert second == {"strategies": ["graham"]}
    assert calls["n"] == 1
    # Mutating the returned dict must not corrupt the cache.
    second["strategies"].append("buffett")
    assert store.get_settings()["strategies"] == ["graham"]

    # A save refreshes the cache so the next read sees the new value (no DB hit).
    store.save_settings({"strategies": ["lynch"]})
    assert store.get_settings() == {"strategies": ["lynch"]}
    assert calls["n"] == 2  # only the save connected; the read was cached
