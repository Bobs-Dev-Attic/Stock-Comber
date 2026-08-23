from stock_comber.datasources.polygon import (
    PolygonSource, parse_details, parse_prev_volume, resolve_api_key,
)


def test_parse_details_normalises_fields():
    data = {"results": {
        "name": "Acme Corp", "market_cap": 1.5e9,
        "sic_description": "Metal Mining", "primary_exchange": "XNYS",
        "locale": "us",
    }}
    d = parse_details(data)
    assert d["market_cap"] == 1.5e9
    assert d["sector"] == "Metal Mining"
    assert d["name"] == "Acme Corp"
    assert d["exchange"] == "XNYS"
    assert d["country"] == "US"          # locale upper-cased


def test_parse_details_handles_missing():
    assert parse_details({}) == {}
    assert parse_details({"results": None}) == {}
    assert parse_details({"results": {"market_cap": "oops"}}) == {}   # unparseable dropped


def test_parse_prev_volume():
    assert parse_prev_volume({"results": [{"v": 123456}]}) == 123456.0
    assert parse_prev_volume({"results": []}) is None
    assert parse_prev_volume({}) is None
    assert parse_prev_volume({"results": [{"c": 1}]}) is None   # no volume key


def test_resolve_api_key_from_config():
    assert resolve_api_key({"data": {"polygon_api_key": "pg"}}) == "pg"


def test_resolve_api_key_from_env(monkeypatch):
    monkeypatch.delenv("POLYGON_API_KEY", raising=False)
    assert resolve_api_key({"data": {}}) is None
    monkeypatch.setenv("POLYGON_API_KEY", "envpg")
    assert resolve_api_key({"data": {}}) == "envpg"


class _FakeResp:
    def __init__(self, payload, status=200):
        self._p = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._p


class _RoutingSession:
    """Returns a payload chosen by URL path; records every URL requested."""

    def __init__(self, details, prev):
        self.details = details
        self.prev = prev
        self.urls = []
        self.headers_seen = []

    def get(self, url, headers=None, timeout=None):
        self.urls.append(url)
        self.headers_seen.append(headers or {})
        if "/aggs/" in url:
            return _FakeResp(self.prev)
        return _FakeResp(self.details)


def _details_payload():
    return {"results": {"name": "X", "market_cap": 2.0e8,
                        "sic_description": "Software", "primary_exchange": "XNAS",
                        "locale": "us"}}


def test_fetch_profile_with_volume_makes_two_calls():
    sess = _RoutingSession(_details_payload(), {"results": [{"v": 9000}]})
    pg = PolygonSource("k", session=sess, delay=0.0, with_volume=True)
    prof = pg.fetch_profile("xyz")
    assert prof["market_cap"] == 2.0e8
    assert prof["sector"] == "Software"
    assert prof["avg_volume"] == 9000.0
    assert len(sess.urls) == 2                    # details + prev-close


def test_fetch_profile_details_only():
    sess = _RoutingSession(_details_payload(), {"results": [{"v": 9000}]})
    pg = PolygonSource("k", session=sess, delay=0.0, with_volume=False)
    prof = pg.fetch_profile("xyz")
    assert "avg_volume" not in prof
    assert len(sess.urls) == 1                    # details only


def test_key_travels_in_authorization_header_only():
    sess = _RoutingSession(_details_payload(), {"results": [{"v": 1}]})
    pg = PolygonSource("secret-key", session=sess, delay=0.0, with_volume=True)
    pg.fetch_profile("xyz")
    for url in sess.urls:
        assert "secret-key" not in url            # never in the URL
    assert sess.headers_seen[0]["Authorization"] == "Bearer secret-key"


class _429Session:
    def __init__(self):
        self.calls = 0

    def get(self, *a, **k):
        self.calls += 1
        return _FakeResp({}, status=429)


def test_circuit_breaker_trips_after_repeated_429():
    sess = _429Session()
    pg = PolygonSource("k", session=sess, delay=0.0, with_volume=False)
    for _ in range(5):
        pg.fetch_profile("aaa")                   # each 429 → None, swallowed
    # After 3 strikes the breaker trips and stops issuing further requests.
    assert pg._rate_limited is True
    assert sess.calls == 3


def test_screener_prefers_polygon_as_enricher(config):
    config["data"]["polygon_api_key"] = "pg"
    from stock_comber.screener import Screener
    scr = Screener(config, sec=object())
    assert scr.polygon is not None
    # resolve_universe (nightly) uses polygon over finnhub as the enricher.
    assert (scr.polygon or scr.finnhub) is scr.polygon
