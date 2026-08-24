"""Fund X-ray: bundled snapshots + fund-weighted scoring / diversity metrics."""

from stock_comber import funds


def _res(ticker, strategy, passed, score_pct, price=None, gn=None, sector=None):
    return {"ticker": ticker, "strategy": strategy, "passed": passed,
            "score_pct": score_pct, "sector": sector,
            "metrics": {"price": price, "graham_number": gn}}


# -- catalog ---------------------------------------------------------------
def test_list_funds_nonempty_and_shaped():
    fs = funds.list_funds()
    assert fs and all({"symbol", "name", "category", "holdings_count", "coverage"} <= set(f) for f in fs)
    # sorted by symbol
    assert [f["symbol"] for f in fs] == sorted(f["symbol"] for f in fs)


def test_get_fund_known_and_unknown():
    spy = funds.get_fund("spy")
    assert spy and spy["symbol"] == "SPY" and spy["holdings"]
    assert all("ticker" in h and "weight" in h for h in spy["holdings"])
    assert funds.get_fund("NOPE") is None


def test_snapshot_weights_are_fractions_under_one():
    spy = funds.get_fund("SPY")
    total = sum(h["weight"] for h in spy["holdings"])
    assert 0 < total < 1.0   # top-holdings snapshot, not the whole fund


# -- analysis --------------------------------------------------------------
def test_fund_weighted_score_weights_bigger_positions_more():
    holdings = [{"ticker": "AAA", "weight": 0.30}, {"ticker": "BBB", "weight": 0.10}]
    results = [_res("AAA", "graham", True, 90, price=100, sector="Information Technology"),
               _res("BBB", "graham", False, 10, price=50, sector="Health Care")]
    a = funds.analyze_fund(holdings, results, ["graham"], meta={"symbol": "X"})
    # fund-weighted: (0.3*90 + 0.1*10)/0.4 = 70, not the equal-weight 50
    assert a["quality_score"] == 70.0
    assert a["covered_count"] == 2 and a["coverage"] == 1.0
    assert a["passing"] == 1


def test_uncovered_holdings_become_pending_and_lower_coverage():
    holdings = [{"ticker": "AAA", "weight": 0.20}, {"ticker": "ZZZ", "weight": 0.20}]
    results = [_res("AAA", "graham", True, 80, price=100, sector="Financials")]
    a = funds.analyze_fund(holdings, results, ["graham"])
    assert a["pending"] == ["ZZZ"]
    assert a["covered_count"] == 1
    assert a["coverage"] == 0.5           # 0.20 covered of 0.40 total
    assert a["quality_score"] == 80.0      # scored only over covered weight


def test_sector_breakdown_uses_results_then_bundled_map():
    # AAPL has no sector in results -> falls back to the bundled SP500 map (IT).
    holdings = [{"ticker": "AAPL", "weight": 0.5}, {"ticker": "JPM", "weight": 0.5}]
    results = [_res("AAPL", "graham", True, 60, price=100),
               _res("JPM", "graham", True, 60, price=100, sector="Financials")]
    a = funds.analyze_fund(holdings, results, ["graham"])
    assert a["sectors"].get("Information Technology") == 0.5
    assert a["sectors"].get("Financials") == 0.5
    assert a["sector_count"] == 2


def test_concentration_flag_and_top10_weight():
    # One dominant name -> concentrated top-10, sector-heavy suggestion.
    holdings = [{"ticker": "AAA", "weight": 0.80}, {"ticker": "BBB", "weight": 0.20}]
    results = [_res("AAA", "graham", True, 50, price=10, sector="Information Technology"),
               _res("BBB", "graham", True, 50, price=10, sector="Information Technology")]
    a = funds.analyze_fund(holdings, results, ["graham"])
    assert a["top10_weight"] == 1.0
    types = {s["type"] for s in a["suggestions"]}
    assert "sector" in types                     # 100% IT
    assert a["effective_holdings"] < 2           # concentrated -> below the 2 names


def test_overall_blends_quality_and_diversification_and_grades():
    holdings = [{"ticker": "AAA", "weight": 0.5}, {"ticker": "BBB", "weight": 0.5}]
    results = [_res("AAA", "graham", True, 100, price=10, sector="Financials"),
               _res("BBB", "graham", True, 100, price=10, sector="Health Care")]
    a = funds.analyze_fund(holdings, results, ["graham"])
    assert a["quality_score"] == 100.0
    # overall = 0.65*quality + 0.35*diversification, so between them
    assert a["diversification_score"] <= a["score"] <= a["quality_score"]
    assert a["grade"] in {"A", "B", "C", "D", "F"}


def test_empty_holdings_safe():
    a = funds.analyze_fund([], [], ["graham"])
    assert a["count"] == 0 and a["score"] is None and a["grade"] == "n/a"
    assert a["pending"] == [] and a["suggestions"]


def test_no_screened_data_falls_back_to_diversification_only():
    holdings = [{"ticker": "AAA", "weight": 0.5}, {"ticker": "BBB", "weight": 0.5}]
    a = funds.analyze_fund(holdings, [], ["graham"])
    assert a["quality_score"] is None
    assert a["score"] == a["diversification_score"]   # no quality -> diversification alone
    assert a["coverage"] == 0.0 and len(a["pending"]) == 2
