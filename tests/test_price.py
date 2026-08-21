from stock_comber.datasources.yahoo import parse_chart
from stock_comber.models import Quote
from stock_comber.screener import Screener


def test_parse_chart_extracts_price():
    data = {"chart": {"result": [{"meta": {
        "regularMarketPrice": 226.5, "regularMarketTime": 1735000000}}], "error": None}}
    assert parse_chart(data) == ("1735000000", 226.5, None)


def test_parse_chart_extracts_volume_from_meta():
    data = {"chart": {"result": [{"meta": {
        "regularMarketPrice": 226.5, "regularMarketTime": 1735000000,
        "regularMarketVolume": 54321000}}], "error": None}}
    assert parse_chart(data) == ("1735000000", 226.5, 54321000.0)


def test_parse_chart_falls_back_to_volume_series():
    data = {"chart": {"result": [{
        "meta": {"regularMarketPrice": 10.0, "regularMarketTime": 1},
        "indicators": {"quote": [{"volume": [100, 200, None]}]}}], "error": None}}
    assert parse_chart(data) == ("1", 10.0, 200.0)


def test_parse_chart_handles_missing():
    assert parse_chart({"chart": {"result": []}}) is None
    assert parse_chart({}) is None
    assert parse_chart({"chart": {"result": [{"meta": {}}]}}) is None


class _Src:
    def __init__(self, price):
        self.price = price
        self.calls = 0

    def fetch_quote(self, ticker):
        self.calls += 1
        return Quote(ticker=ticker.upper(), price=self.price, source="x")


class _Boom:
    def __init__(self):
        self.calls = 0

    def fetch_quote(self, ticker):
        self.calls += 1
        raise RuntimeError("down")


def _screener(sources, config):
    return Screener(config, sec=object(), price_sources=sources)


def test_price_chain_uses_first_with_price(config):
    a, b = _Src(100.0), _Src(200.0)
    q = _screener([a, b], config).fetch_price("AAPL")
    assert q.price == 100.0
    assert b.calls == 0  # short-circuits on first hit


def test_price_chain_falls_back_when_first_has_none(config):
    a, b = _Src(None), _Src(55.0)
    q = _screener([a, b], config).fetch_price("AAPL")
    assert q.price == 55.0


def test_price_chain_survives_exceptions(config):
    boom, ok = _Boom(), _Src(42.0)
    q = _screener([boom, ok], config).fetch_price("AAPL")
    assert q.price == 42.0
    assert boom.calls == 1


def test_price_chain_all_fail_returns_priceless_quote(config):
    q = _screener([_Src(None), _Boom()], config).fetch_price("AAPL")
    assert q.price is None
    assert q.ticker == "AAPL"
