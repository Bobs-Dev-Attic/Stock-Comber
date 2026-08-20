"""Smoke + behaviour tests for the added investor strategies."""

import pytest

from stock_comber.config import load_config
from stock_comber.criteria import STRATEGIES
from stock_comber.criteria.greenblatt import evaluate_greenblatt
from stock_comber.criteria.lynch import evaluate_lynch
from stock_comber.criteria.netnet import evaluate_netnet
from stock_comber.criteria.piotroski import evaluate_piotroski
from stock_comber.models import Company


@pytest.fixture
def cfg():
    return load_config()


def test_all_strategies_registered():
    for key in ("piotroski", "greenblatt", "lynch", "netnet"):
        assert key in STRATEGIES


@pytest.mark.parametrize("fn,strat", [
    (evaluate_piotroski, "piotroski"), (evaluate_greenblatt, "greenblatt"),
    (evaluate_lynch, "lynch"), (evaluate_netnet, "netnet"),
])
def test_strategies_run_and_shape(fn, strat, strong_company, cfg):
    res = fn(strong_company, cfg)
    assert res.strategy == strat
    assert res.max_score > 0
    assert res.criteria and all(hasattr(c, "passed") for c in res.criteria)
    assert 0.0 <= res.score <= res.max_score


@pytest.mark.parametrize("fn", [
    evaluate_piotroski, evaluate_greenblatt, evaluate_lynch, evaluate_netnet])
def test_strategies_handle_no_fundamentals(fn, cfg):
    empty = Company(ticker="ZZZ", cik="9", name="Empty")
    res = fn(empty, cfg)
    assert res.passed is False
    assert res.max_score == 0.0
    assert res.errors == ["no annual fundamentals available"]


def test_piotroski_score_counts_signals(strong_company, cfg):
    res = evaluate_piotroski(strong_company, cfg)
    assert res.metrics.get("piotroski_f_score") == res.score
    assert res.max_score == 9.0


def test_netnet_rejects_expensive_large_cap(strong_company, cfg):
    # A profitable large cap trading well above NCAV must not be a net-net.
    res = evaluate_netnet(strong_company, cfg)
    assert res.passed is False


def test_lynch_reports_peg(strong_company, cfg):
    res = evaluate_lynch(strong_company, cfg)
    assert "peg_ratio" in res.metrics
