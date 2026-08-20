from stock_comber.sentiment import compute_sentiment
from stock_comber.storage import NullStorage
from stock_comber.analysis import process_queue, _full_config
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


def test_process_queue_noop_without_db():
    out = process_queue(load_config(), NullStorage(), limit=5)
    assert out["processed"] == 0


def test_null_storage_queue_stubs():
    s = NullStorage()
    assert s.enqueue(["AAPL"]) == 0
    assert s.list_queue() == []
    assert s.pop_pending() == []
    assert s.mark_queue("AAPL", "done") is None
