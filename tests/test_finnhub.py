from stock_comber.datasources.finnhub import parse_quote, resolve_api_key
from stock_comber.models import Quote


def test_parse_quote():
    assert parse_quote({"c": 226.5}) == 226.5
    assert parse_quote({"c": 0}) is None      # 0 means no data
    assert parse_quote({}) is None


def test_resolve_api_key_from_config():
    assert resolve_api_key({"data": {"finnhub_api_key": "abc"}}) == "abc"


def test_resolve_api_key_from_env(monkeypatch):
    monkeypatch.delenv("FINNHUB_API_KEY", raising=False)
    assert resolve_api_key({"data": {}}) is None
    monkeypatch.setenv("FINNHUB_API_KEY", "xyz")
    assert resolve_api_key({"data": {}}) == "xyz"


class _FakeFinnhub:
    def fetch_quote(self, ticker):
        return Quote(ticker=ticker.upper(), price=123.0, source="finnhub")

    def fetch_metrics(self, ticker):
        return {"peBasicExclExtraTTM": 20.0}


def test_finnhub_added_to_price_chain(config):
    config["data"]["finnhub_api_key"] = "abc"
    from stock_comber.screener import Screener
    scr = Screener(config, sec=object(),
                   price_sources=[_FakeFinnhub()])
    q = scr.fetch_price("AAPL")
    assert q.price == 123.0
