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
