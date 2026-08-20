from stock_comber.models import Quote
from stock_comber.screener import Screener


class FakeSec:
    def __init__(self, companies):
        self._c = {c.ticker: c for c in companies}

    def fetch_company(self, ticker):
        return self._c.get(ticker.upper())

    def list_tickers(self, limit=None):
        ts = sorted(self._c)
        return ts[:limit] if limit else ts


class FakeStooq:
    def fetch_quote(self, ticker):
        return Quote(ticker=ticker.upper(), price=40.0, source="fake")


def test_run_ranks_passing_first(strong_company, weak_company, config):
    config["universe"]["tickers"] = ["STRONG", "WEAK"]
    config["strategies"] = ["graham"]
    screener = Screener(config, sec=FakeSec([strong_company, weak_company]),
                        stooq=FakeStooq())
    results = screener.run()
    assert results[0].ticker == "STRONG"
    assert results[0].passed
    assert not results[-1].passed


def test_rank_attaches_health_and_can_sort_by_it(strong_company, weak_company, config):
    config["universe"]["tickers"] = ["STRONG", "WEAK"]
    config["strategies"] = ["graham"]
    config["output"]["sort_by"] = "health"
    screener = Screener(config, sec=FakeSec([strong_company, weak_company]),
                        stooq=FakeStooq())
    results = screener.run()
    # Every result carries a composite health score in its metrics.
    assert all("health_score" in r.metrics for r in results)
    strong = next(r for r in results if r.ticker == "STRONG")
    weak = next(r for r in results if r.ticker == "WEAK")
    assert strong.metrics["health_score"] > weak.metrics["health_score"]
    # The healthier company ranks first.
    assert results[0].ticker == "STRONG"


def test_unknown_ticker_is_reported_not_fatal(config):
    config["universe"]["tickers"] = ["GHOST"]
    config["strategies"] = ["graham"]
    screener = Screener(config, sec=FakeSec([]), stooq=FakeStooq())
    results = screener.run()
    assert len(results) == 1
    assert not results[0].passed
    assert any("not found" in e for e in results[0].errors)


def test_resolve_universe_uses_explicit_tickers(config):
    config["universe"]["tickers"] = ["aapl", "msft"]
    screener = Screener(config, sec=FakeSec([]), stooq=FakeStooq())
    assert screener.resolve_universe() == ["AAPL", "MSFT"]
