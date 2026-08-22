"""Tiingo licensed price source: parsing, fetch, key hygiene, chain wiring."""

from stock_comber.datasources.tiingo import (
    TiingoSource, parse_history, parse_latest, resolve_api_key, tiingo_symbol,
)
from stock_comber.models import Quote


# -- key resolution ---------------------------------------------------------
def test_resolve_api_key_from_config():
    assert resolve_api_key({"data": {"tiingo_api_key": "abc"}}) == "abc"


def test_resolve_api_key_from_env(monkeypatch):
    monkeypatch.delenv("TIINGO_API_KEY", raising=False)
    assert resolve_api_key({"data": {}}) is None
    monkeypatch.setenv("TIINGO_API_KEY", "xyz")
    assert resolve_api_key({"data": {}}) == "xyz"


# -- symbol mapping ---------------------------------------------------------
def test_tiingo_symbol_lowercases_and_maps_dot():
    assert tiingo_symbol("AAPL") == "aapl"
    assert tiingo_symbol("BRK.B") == "brk-b"


def test_tiingo_symbol_rejects_malformed():
    assert tiingo_symbol("../etc/passwd") is None
    assert tiingo_symbol("") is None


# -- payload parsing --------------------------------------------------------
def test_parse_latest_takes_last_row():
    rows = [
        {"date": "2026-08-20T00:00:00.000Z", "close": 100.0, "volume": 10},
        {"date": "2026-08-21T00:00:00.000Z", "close": 101.5, "volume": 20},
    ]
    assert parse_latest(rows) == ("2026-08-21", 101.5, 20.0)


def test_parse_latest_handles_empty_and_bad():
    assert parse_latest([]) is None
    assert parse_latest("nope") is None
    assert parse_latest([{"date": "2026-01-01", "close": None}]) is None


def test_parse_history_keeps_year_end_adjclose():
    rows = [
        {"date": "2024-11-30", "adjClose": 90.0, "close": 91.0},
        {"date": "2024-12-31", "adjClose": 95.0, "close": 96.0},   # year-end wins
        {"date": "2025-12-31", "adjClose": 110.0, "close": 111.0},
    ]
    hist = parse_history(rows)
    assert hist == {2024: 95.0, 2025: 110.0}


def test_parse_history_falls_back_to_close():
    rows = [{"date": "2025-12-31", "close": 50.0}]   # no adjClose
    assert parse_history(rows) == {2025: 50.0}


# -- fetch via a fake session ----------------------------------------------
class _FakeResp:
    def __init__(self, payload):
        self._p = payload
        self.status_code = 200

    def raise_for_status(self):
        pass

    def json(self):
        return self._p


class _RecordingSession:
    """Captures every request's url / params / headers for hygiene assertions."""

    def __init__(self, payload):
        self.payload = payload
        self.requests = []

    def get(self, url, params=None, headers=None, timeout=None):
        self.requests.append({"url": url, "params": params or {},
                              "headers": headers or {}})
        return _FakeResp(self.payload)


def test_fetch_quote_returns_close_and_volume():
    sess = _RecordingSession([{"date": "2026-08-21T00:00:00.000Z",
                               "close": 187.25, "volume": 1234567}])
    src = TiingoSource("secret-key", session=sess)
    q = src.fetch_quote("AAPL")
    assert isinstance(q, Quote)
    assert q.price == 187.25
    assert q.volume == 1234567.0
    assert q.source == "tiingo"
    assert q.ticker == "AAPL"
    assert q.as_of == "2026-08-21"


def test_fetch_history_returns_year_ends():
    sess = _RecordingSession([
        {"date": "2024-12-31", "adjClose": 95.0},
        {"date": "2025-12-31", "adjClose": 110.0},
    ])
    src = TiingoSource("secret-key", session=sess)
    assert src.fetch_history("MSFT", years=5) == {2024: 95.0, 2025: 110.0}


def test_malformed_ticker_never_reaches_the_network():
    sess = _RecordingSession([])
    src = TiingoSource("secret-key", session=sess)
    q = src.fetch_quote("../secrets")
    assert q.price is None
    assert src.fetch_history("../secrets") == {}
    assert sess.requests == []          # no request was ever issued


def test_key_travels_only_in_auth_header_never_url_or_params():
    sess = _RecordingSession([{"date": "2026-08-21", "close": 10.0}])
    src = TiingoSource("super-secret-key", session=sess)
    src.fetch_quote("AAPL")
    req = sess.requests[0]
    assert "super-secret-key" not in req["url"]
    assert "super-secret-key" not in repr(req["params"])
    assert req["headers"]["Authorization"] == "Token super-secret-key"


# -- screener chain wiring --------------------------------------------------
def test_tiingo_leads_price_chain_when_key_present(config):
    config["data"]["tiingo_api_key"] = "abc"
    from stock_comber.datasources import StooqSource, TiingoSource, YahooSource
    from stock_comber.screener import Screener
    scr = Screener(config, sec=object())
    assert isinstance(scr.price_sources[0], TiingoSource)   # primary
    assert isinstance(scr.price_sources[1], YahooSource)    # then free chain
    assert isinstance(scr.price_sources[2], StooqSource)


def test_no_tiingo_source_without_key(config):
    from stock_comber.datasources import TiingoSource, YahooSource
    from stock_comber.screener import Screener
    scr = Screener(config, sec=object())
    assert isinstance(scr.price_sources[0], YahooSource)    # unchanged free chain
    assert not any(isinstance(s, TiingoSource) for s in scr.price_sources)
