"""Tests for the shared ticker validator (SSRF / path-injection guard)."""

import pytest

from stock_comber.validation import is_valid_ticker, normalize_ticker


@pytest.mark.parametrize("good", ["AAPL", "aapl", "BRK.B", "RDS-A", "F", "GOOGL",
                                  " msft ", "A1", "ABCDEFGHIJ"])
def test_accepts_well_formed_symbols(good):
    assert is_valid_ticker(good)
    assert normalize_ticker(good) == good.strip().upper()


@pytest.mark.parametrize("bad", [
    "", "   ", None, 123, "1AAPL", ".AAPL", "-X",           # must start with a letter
    "ABCDEFGHIJK",                                           # 11 chars, too long
    "AA PL", "AA/PL", "AA;PL", "A%00", "A/../etc",           # illegal chars
    "http://evil", "AAPL?x=1", "AAPL#frag", "AA\nPL",
])
def test_rejects_malformed_or_injection_symbols(bad):
    assert not is_valid_ticker(bad)
    assert normalize_ticker(bad) is None


def test_sec_and_yahoo_reject_bad_ticker_without_network(monkeypatch):
    # The data sources must short-circuit before building any URL.
    from stock_comber.datasources.yahoo import YahooSource
    from stock_comber.datasources.sec_edgar import SecEdgarSource

    y = YahooSource(session=object())  # a session that would explode if used
    q = y.fetch_quote("A/../secret")
    assert q.price is None
    assert y.fetch_history("bad ticker") == {}

    sec = SecEdgarSource(user_agent="test")
    assert sec.fetch_company("evil/path") is None
    assert sec.filer_cik("../../x") is None
