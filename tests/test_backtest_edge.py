"""The nightly backtest-edge attachment: bounded-concurrency fetch + failure isolation."""

from types import SimpleNamespace

from stock_comber.cli import _attach_backtest_edge
from stock_comber.models import AnnualFacts, Company, ScreenResult


def _company(ticker):
    annuals = [AnnualFacts(
        fiscal_year=fy, revenue=2e9 + i * 1e8, net_income=3e8 + i * 2e7,
        total_assets=4e9, total_liabilities=1e9, stockholders_equity=3e9,
        current_assets=2.5e9, current_liabilities=5e8, long_term_debt=2e8,
        eps=3.0 + i * 0.2, shares_outstanding=1e8,
        operating_cash_flow=4e8, capital_expenditures=1e8,
    ) for i, fy in enumerate(range(2019, 2024))]
    return Company(ticker=ticker, cik="1", name=ticker, annuals=annuals)


def _result(ticker):
    return ScreenResult(ticker=ticker, name=ticker, strategy="graham",
                        passed=True, score=8, max_score=10, metrics={})


class _FakeYahoo:
    """Returns a rising price history for good tickers; raises for BAD."""
    calls = []

    def __init__(self, *a, **k):
        pass

    def fetch_history(self, ticker, years=10):
        _FakeYahoo.calls.append(ticker)
        if ticker == "BAD":
            raise RuntimeError("network boom")
        return {2019: 30.0, 2020: 36.0, 2021: 40.0, 2022: 44.0, 2023: 50.0}


def _screener():
    return SimpleNamespace(
        sec=SimpleNamespace(cache=None),
        last_companies={t: _company(t) for t in ("AAA", "BBB", "BAD")},
    )


def _run(monkeypatch, config, workers):
    monkeypatch.setattr("stock_comber.datasources.YahooSource", _FakeYahoo)
    _FakeYahoo.calls = []
    results = [_result(t) for t in ("AAA", "BBB", "BAD")]
    config["data"]["backtest_fetch_workers"] = workers
    _attach_backtest_edge(results, _screener(), config)
    return {r.ticker: r.metrics.get("backtest_edge_pct") for r in results}


def test_concurrent_fetch_attaches_edges_and_isolates_failures(monkeypatch, config):
    edges = _run(monkeypatch, config, workers=4)
    assert edges["AAA"] is not None and edges["BBB"] is not None
    assert edges["BAD"] is None                 # failure skipped, not fatal
    assert set(_FakeYahoo.calls) == {"AAA", "BBB", "BAD"}


def test_serial_path_matches_concurrent(monkeypatch, config):
    serial = _run(monkeypatch, config, workers=1)
    concurrent = _run(monkeypatch, config, workers=8)
    assert serial == concurrent
    assert serial["AAA"] == concurrent["AAA"]


def test_skips_tickers_without_fundamentals(monkeypatch, config):
    monkeypatch.setattr("stock_comber.datasources.YahooSource", _FakeYahoo)
    _FakeYahoo.calls = []
    results = [_result("AAA"), _result("EMPTY")]
    screener = SimpleNamespace(
        sec=SimpleNamespace(cache=None),
        last_companies={"AAA": _company("AAA"),
                        "EMPTY": Company(ticker="EMPTY")},  # no annuals
    )
    config["data"]["backtest_fetch_workers"] = 4
    _attach_backtest_edge(results, screener, config)
    assert "EMPTY" not in _FakeYahoo.calls        # never fetched
    assert results[0].metrics.get("backtest_edge_pct") is not None
