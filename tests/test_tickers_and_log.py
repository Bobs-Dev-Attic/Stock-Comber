from stock_comber.datasources.sec_edgar import match_tickers
from stock_comber.storage import NullStorage

MAP = {
    "AAPL": {"cik": 320193, "name": "Apple Inc."},
    "AAP": {"cik": 1158449, "name": "Advance Auto Parts"},
    "MSFT": {"cik": 789019, "name": "Microsoft Corp"},
    "APP": {"cik": 1751008, "name": "Applovin Corp"},
}


def test_match_tickers_prefix_ranks_first():
    out = match_tickers(MAP, "aap", limit=10)
    tickers = [o["ticker"] for o in out]
    assert tickers[:2] == ["AAP", "AAPL"]  # ticker-prefix matches, sorted
    assert all("ticker" in o and "name" in o for o in out)


def test_match_tickers_matches_name_substring():
    out = match_tickers(MAP, "microsoft", limit=10)
    assert [o["ticker"] for o in out] == ["MSFT"]


def test_match_tickers_empty_query():
    assert match_tickers(MAP, "", limit=10) == []
    assert match_tickers(MAP, "   ", limit=10) == []


def test_match_tickers_respects_limit():
    out = match_tickers(MAP, "a", limit=2)
    assert len(out) == 2


def test_null_storage_search_log_is_noop():
    s = NullStorage()
    assert s.log_search("live", ["AAPL"], ["graham"], None, 1, 0) is None
    assert s.list_searches() == []
