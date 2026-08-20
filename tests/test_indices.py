"""Index universe templates (Dow / Nasdaq-100 / S&P 500)."""

import copy

from stock_comber.config import DEFAULT_CONFIG, validate_config
from stock_comber.indices import INDEXES, index_keys, index_rows
from stock_comber.universe import _candidates, _passes, build_nightly


def test_index_lists_present_and_sized():
    assert set(index_keys()) == {"sp500", "dow", "nasdaq100"}
    assert len(INDEXES["dow"]["tickers"]) == 30
    assert 90 <= len(INDEXES["nasdaq100"]["tickers"]) <= 110
    assert len(INDEXES["sp500"]["tickers"]) >= 490


def test_index_rows_carry_sector_and_industry():
    rows = dict((t, (s, i)) for t, s, i in index_rows("dow"))
    assert rows["AAPL"][0] == "Information Technology"
    assert "Biotechnology" == dict((t, i) for t, s, i in index_rows("dow"))["AMGN"]


def test_index_becomes_candidate_pool():
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    cfg["universe"]["index"] = "dow"
    cands, meta = _candidates(cfg, None)
    assert len(cands) == 30
    assert meta["AAPL"]["industry"].startswith("Technology Hardware")
    assert meta["AAPL"]["country"] == "US"


def test_industry_filter():
    n = {"industries": ["Biotechnology"], "include_unknown": True}
    assert _passes({"industry": "Biotechnology"}, n) is True
    assert _passes({"industry": "Semiconductors"}, n) is False


def test_sector_filtered_nightly_from_index():
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    cfg["universe"]["index"] = "sp500"
    cfg["universe"]["nightly"]["sectors"] = ["Energy"]
    picks = build_nightly(cfg, store=None, finnhub=None, day_ordinal=0)
    assert picks and "CVX" in picks       # Chevron is S&P Energy
    assert "AAPL" not in picks            # tech excluded by the sector filter


def test_unknown_index_rejected():
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    cfg["universe"]["index"] = "wilshire5000"
    problems = validate_config(cfg)
    assert any("universe.index" in p for p in problems)
