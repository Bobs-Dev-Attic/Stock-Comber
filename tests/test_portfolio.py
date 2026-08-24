"""Portfolio Advisor scoring, targets and balance suggestions (pure functions)."""

from stock_comber import portfolio as pf


def _res(ticker, strategy, passed, score_pct, price=None, gn=None, sector=None):
    return {"ticker": ticker, "strategy": strategy, "passed": passed,
            "score_pct": score_pct, "sector": sector,
            "metrics": {"price": price, "graham_number": gn}}


# -- targets ---------------------------------------------------------------
def test_targets_no_price_and_no_fair_value_is_na():
    t = pf.targets(None, None)
    assert t["verdict"] == "n/a" and t["buy_below"] is None and t["sell_above"] is None


def test_targets_anchor_to_price_when_no_fair_value():
    # No fair value -> verdict n/a, but bands are still anchored close to price.
    t = pf.targets(100, None)
    assert t["verdict"] == "n/a"
    assert t["buy_below"] == 95.0 and t["sell_above"] == 110.0   # 5% below / 10% above


def test_targets_bands_are_close_to_price_with_valuation_tilt():
    # fair value 100: verdict from the deep-value test, bands anchored to price.
    fair = pf.targets(90, 100)      # 90 is between 75 and 110 -> fair
    assert fair["verdict"] == "fair"
    assert fair["buy_below"] == 85.5 and fair["sell_above"] == 99.0   # 5% below / 10% above 90
    assert fair["fair_value"] == 100.0

    under = pf.targets(70, 100)     # 70 <= 75 -> undervalued: tighter buy, wider sell
    assert under["verdict"] == "undervalued"
    assert under["buy_below"] == 68.25 and under["sell_above"] == 80.5   # 2.5% below / 15% above 70

    over = pf.targets(120, 100)     # 120 >= 110 -> overvalued: deeper buy, tighter sell
    assert over["verdict"] == "overvalued"
    assert over["buy_below"] == 111.0 and over["sell_above"] == 126.0    # 7.5% below / 5% above 120


def test_targets_stay_within_15pct_of_price():
    for price in (12.34, 50, 100, 371.5):
        for fv in (None, price * 0.5, price, price * 2):
            t = pf.targets(price, fv)
            if t["buy_below"] is not None:
                assert 0.84 * price <= t["buy_below"] <= price
                assert price <= t["sell_above"] <= 1.16 * price


# -- scoring ---------------------------------------------------------------
def test_holding_score_averages_selected_strategies():
    results = [_res("AAPL", "graham", True, 80), _res("AAPL", "buffett", False, 40),
               _res("KO", "graham", True, 60)]
    assert pf.holding_score("AAPL", results, ["graham", "buffett"]) == 60.0
    assert pf.holding_score("AAPL", results, ["graham"]) == 80.0
    assert pf.holding_score("NVDA", results, []) is None


def test_holding_passes_any_strategy():
    results = [_res("AAPL", "graham", False, 40), _res("AAPL", "buffett", True, 55)]
    assert pf.holding_passes("AAPL", results) is True
    assert pf.holding_passes("KO", results) is False


# -- analyze ---------------------------------------------------------------
def test_analyze_weights_value_and_score():
    results = [
        _res("AAPL", "graham", True, 80, price=100, gn=200, sector="Tech"),   # undervalued
        _res("KO", "graham", True, 60, price=50, gn=40, sector="Consumer"),   # overvalued (50>=44)
    ]
    out = pf.analyze([{"ticker": "AAPL", "shares": 10}, {"ticker": "KO", "shares": 10}],
                     results, ["graham"])
    assert out["count"] == 2 and out["passing"] == 2
    # values: AAPL 1000, KO 500 -> total 1500; weights .667/.333
    assert out["total_value"] == 1500.0
    a = next(r for r in out["holdings"] if r["ticker"] == "AAPL")
    k = next(r for r in out["holdings"] if r["ticker"] == "KO")
    assert round(a["weight"], 2) == 0.67 and round(k["weight"], 2) == 0.33
    assert a["verdict"] == "undervalued" and k["verdict"] == "overvalued"
    assert a["action"] == "buy" and k["action"] == "trim"
    # value-weighted score = (1000*80 + 500*60)/1500 = 73.3
    assert out["score"] == 73.3


def test_analyze_flags_concentration_and_sector():
    results = [
        _res("AAPL", "graham", True, 80, price=100, gn=90, sector="Tech"),
        _res("MSFT", "graham", True, 70, price=100, gn=90, sector="Tech"),
    ]
    # AAPL 90% of value, and Tech = 100% of value -> both flags
    out = pf.analyze([{"ticker": "AAPL", "shares": 90}, {"ticker": "MSFT", "shares": 10}],
                     results, ["graham"])
    kinds = {s["type"] for s in out["suggestions"]}
    assert "concentration" in kinds and "sector" in kinds


def test_target_weights_capped_and_drops_weak():
    results = [
        _res("AAPL", "graham", True, 90, price=100, gn=90),
        _res("KO", "graham", True, 60, price=100, gn=90),
        _res("XYZ", "graham", False, 20, price=100, gn=90),   # weak -> excluded
    ]
    out = pf.analyze([{"ticker": "AAPL", "shares": 1}, {"ticker": "KO", "shares": 1},
                      {"ticker": "XYZ", "shares": 1}], results, ["graham"])
    tw = out["target_weights"]
    assert "XYZ" not in tw                       # weak scorer dropped
    assert set(tw) == {"AAPL", "KO"}
    assert abs(sum(tw.values()) - 1.0) < 1e-6    # normalized
    assert tw["AAPL"] > tw["KO"]                 # tilted toward the higher score


def test_analyze_empty_is_safe():
    out = pf.analyze([], [], ["graham"])
    assert out["count"] == 0 and out["total_value"] == 0.0 and out["score"] is None
    assert out["suggestions"]  # never empty
