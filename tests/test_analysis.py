from stock_comber.sentiment import compute_sentiment
from stock_comber.storage import NullStorage
from stock_comber.analysis import process_queue, _full_config, _jobs_criteria_for
from stock_comber.config import load_config


def test_sentiment_positive():
    s = compute_sentiment(["Company beats estimates, profit surges to record high",
                           "Analyst upgrades stock, raises guidance"])
    assert s["grade"] in ("A", "B")
    assert s["score"] > 0 and s["positive"] > s["negative"]


def test_sentiment_negative():
    s = compute_sentiment(["Shares plunge after earnings miss and downgrade",
                           "Company warns of weak outlook amid lawsuit"])
    assert s["grade"] in ("D", "F")
    assert s["score"] < 0


def test_sentiment_neutral_when_no_cues():
    s = compute_sentiment(["Company holds annual meeting on Tuesday"])
    assert s["grade"] == "C" and s["score"] == 0.0
    assert s["article_count"] == 1


def test_sentiment_empty():
    s = compute_sentiment([])
    assert s == {"score": 0.0, "grade": "C", "positive": 0,
                 "negative": 0, "article_count": 0}


def test_full_config_enables_enrichment():
    cfg = _full_config(load_config())
    assert cfg["data"]["finnhub_enrich_results"] is True
    assert cfg["universe"]["mode"] == "list"
    assert {"graham", "buffett", "piotroski", "greenblatt", "lynch", "netnet"} <= set(cfg["strategies"])


def test_full_config_without_criteria_has_no_custom_lens():
    cfg = _full_config(load_config())
    assert "custom" not in cfg["strategies"]


def test_full_config_appends_custom_when_criteria_given():
    crit = [{"metric": "pe_ratio", "op": "<=", "value": 15}]
    cfg = _full_config(load_config(), criteria=crit)
    # The six built-ins remain, plus the custom lens, with the criteria attached.
    assert {"graham", "buffett", "piotroski", "greenblatt", "lynch", "netnet"} <= set(cfg["strategies"])
    assert cfg["strategies"][-1] == "custom"
    assert cfg["custom"]["criteria"] == crit


def test_jobs_criteria_for_matches_pool_and_dedupes():
    c1 = {"metric": "pe_ratio", "op": "<=", "value": 15}
    c2 = {"metric": "roe_pct", "op": ">=", "value": 20}
    cfg = {"jobs": [
        {"name": "cheap", "tickers": "aapl, msft", "criteria": [c1]},
        {"name": "quality", "tickers": "MSFT , KO", "criteria": [c2, c1]},
        {"name": "other", "tickers": "TSLA", "criteria": [{"metric": "pb_ratio", "op": "<", "value": 1}]},
    ]}
    # MSFT is in two pools -> union of both jobs' criteria, de-duplicated, order-kept.
    assert _jobs_criteria_for("msft", cfg) == [c1, c2]
    assert _jobs_criteria_for("AAPL", cfg) == [c1]
    assert _jobs_criteria_for("NVDA", cfg) == []   # in no pool


def test_process_queue_noop_without_db():
    out = process_queue(load_config(), NullStorage(), limit=5)
    assert out["processed"] == 0


def test_analyze_queue_reseed_strategy_enqueues_matches(monkeypatch):
    """`analyze-queue --reseed-strategy custom` enqueues every ticker on that
    strategy and processes at least that many."""
    from types import SimpleNamespace
    from stock_comber import cli
    import stock_comber.storage as storage

    class _Store:
        enabled = True

        def __init__(self):
            self.enqueued = []

        def tickers_with_strategy(self, strategy, limit=500):
            assert strategy == "custom"
            return ["CVX", "HON", "IBM"]

        def enqueue(self, tickers):
            self.enqueued.extend(tickers)
            return len(tickers)

    store = _Store()
    captured = {}
    monkeypatch.setattr(cli, "_load", lambda args: {})
    monkeypatch.setattr(storage, "get_storage", lambda cfg=None: store)

    def _fake_process(cfg, st, limit=5):
        captured["limit"] = limit
        return {"processed": len(store.enqueued), "tickers": []}

    monkeypatch.setattr("stock_comber.analysis.process_queue", _fake_process)

    args = SimpleNamespace(config=None, limit=5, seed=None, reseed_strategy="custom")
    assert cli.cmd_analyze_queue(args) == 0
    assert store.enqueued == ["CVX", "HON", "IBM"]
    assert captured["limit"] >= 3   # limit widened to cover all reseeded tickers


def test_purge_strategy_requires_confirmation(monkeypatch):
    from types import SimpleNamespace
    from stock_comber import cli
    import stock_comber.storage as storage

    class _Store:
        enabled = True

        def __init__(self):
            self.purged = None

        def delete_results_by_strategy(self, strategy):
            self.purged = strategy
            return {"results_deleted": 7, "empty_runs_deleted": 2}

    store = _Store()
    monkeypatch.setattr(cli, "_load", lambda args: {})
    monkeypatch.setattr(storage, "get_storage", lambda cfg=None: store)

    # Without --yes it refuses and deletes nothing.
    no = SimpleNamespace(config=None, strategy="custom", yes=False)
    assert cli.cmd_purge_strategy(no) == 2
    assert store.purged is None

    # With --yes it deletes.
    yes = SimpleNamespace(config=None, strategy="custom", yes=True)
    assert cli.cmd_purge_strategy(yes) == 0
    assert store.purged == "custom"


def test_null_storage_purge_stub():
    assert NullStorage().delete_results_by_strategy("custom") == {
        "results_deleted": 0, "empty_runs_deleted": 0}


def test_null_storage_queue_stubs():
    s = NullStorage()
    assert s.enqueue(["AAPL"]) == 0
    assert s.list_queue() == []
    assert s.pop_pending() == []
    assert s.mark_queue("AAPL", "done") is None
