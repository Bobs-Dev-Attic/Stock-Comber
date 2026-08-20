from stock_comber.scoring import compute_scores


def test_strong_company_scores_high():
    m = {
        "pe_ratio": 9.0, "pb_ratio": 2.0, "earnings_yield_pct": 11.0,
        "roe_pct": 24.0, "return_on_capital_pct": 20.0, "net_margin_pct": 18.0,
        "roa_pct": 10.0, "debt_to_equity": 0.2, "current_ratio": 3.0,
        "earnings_cagr_5y_pct": 20.0, "earnings_growth_5y_pct": 90.0,
        "revenue_growth_5y_pct": 50.0,
    }
    s = compute_scores(m)
    assert 70 <= s["value"]["score"] <= 100
    assert 75 <= s["quality"]["score"] <= 100
    assert s["overall"]["score"] >= 70
    assert s["overall"]["grade"] in ("A", "B")
    # every category carries an explainable breakdown
    assert s["quality"]["components"] and "points" in s["quality"]["components"][0]


def test_weak_company_scores_low():
    m = {
        "pe_ratio": 45.0, "pb_ratio": 9.0, "earnings_yield_pct": 1.0,
        "roe_pct": 2.0, "return_on_capital_pct": 1.0, "net_margin_pct": 1.0,
        "roa_pct": 0.5, "debt_to_equity": 3.0, "current_ratio": 1.0,
        "earnings_cagr_5y_pct": 0.0, "earnings_growth_5y_pct": 0.0,
        "revenue_growth_5y_pct": 0.0,
    }
    s = compute_scores(m)
    assert s["value"]["score"] <= 25
    assert s["growth"]["score"] <= 15
    assert s["overall"]["grade"] in ("D", "F")


def test_missing_metrics_yield_none_not_crash():
    s = compute_scores({"pe_ratio": 10.0})   # only one value metric present
    assert s["value"] is not None            # value measurable from P/E alone
    assert s["quality"] is None              # nothing quality-related
    assert s["growth"] is None
    assert s["overall"] is not None          # overall from the one present category


def test_empty_metrics_all_none():
    s = compute_scores({})
    assert s == {"value": None, "quality": None, "growth": None, "overall": None}


def test_weights_renormalise_when_partial():
    # Quality with only ROE present should equal that metric's own 0–100 points.
    s = compute_scores({"roe_pct": 12.5})    # midpoint of 0..25 → 50
    assert abs(s["quality"]["score"] - 50.0) < 0.1
