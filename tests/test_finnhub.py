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


def test_price_chain_order_finnhub_last(config):
    config["data"]["finnhub_api_key"] = "abc"
    from stock_comber.screener import Screener
    from stock_comber.datasources import YahooSource, StooqSource, FinnhubSource
    scr = Screener(config, sec=object())
    assert isinstance(scr.price_sources[0], YahooSource)   # primary
    assert isinstance(scr.price_sources[1], StooqSource)   # fallback
    assert isinstance(scr.price_sources[-1], FinnhubSource)  # last resort


class _FakeResp:
    def __init__(self, payload):
        self._p = payload
        self.status_code = 200

    def raise_for_status(self):
        pass

    def json(self):
        return self._p


class _FakeSession:
    def __init__(self, payload):
        self.payload = payload
        self.calls = 0

    def get(self, *a, **k):
        self.calls += 1
        return _FakeResp(self.payload)


def test_fetch_profile_is_single_call_by_default():
    from stock_comber.datasources.finnhub import FinnhubSource
    sess = _FakeSession({"name": "X", "finnhubIndustry": "Tech",
                         "country": "US", "exchange": "NASDAQ",
                         "marketCapitalization": 1500})  # millions
    fh = FinnhubSource("k", session=sess)
    prof = fh.fetch_profile("XYZ")
    assert sess.calls == 1               # profile only, no metric call
    assert prof["market_cap"] == 1.5e9   # normalised to dollars
    assert prof["avg_volume"] is None


def test_fetch_peers_drops_self_and_caps():
    from stock_comber.datasources.finnhub import FinnhubSource
    # Finnhub lists the company itself first; we drop it and de-dup.
    sess = _FakeSession(["XOM", "CVX", "COP", "cvx", "SHEL", "BP", "TTE", "E", "EQNR", "IMO"])
    fh = FinnhubSource("k", session=sess)
    peers = fh.fetch_peers("XOM", limit=8)
    assert "XOM" not in peers            # self dropped
    assert peers[0] == "CVX"
    assert len(peers) == 8               # capped
    assert peers.count("CVX") == 1       # de-duplicated (case-insensitive)


def test_fetch_peers_handles_bad_payload():
    from stock_comber.datasources.finnhub import FinnhubSource
    fh = FinnhubSource("k", session=_FakeSession({"not": "a list"}))
    assert fh.fetch_peers("XOM") == []
