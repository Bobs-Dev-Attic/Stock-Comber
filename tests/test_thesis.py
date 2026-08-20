from stock_comber.thesis import (
    BROKEN, INTACT, WEAKENING, evaluate_thesis, snapshot_metrics, validate_thesis)


CONDS = [
    {"metric": "revenue_growth_5y_pct", "op": ">=", "value": 20},
    {"metric": "net_margin_pct", "op": ">=", "value": 15},
    {"metric": "debt_to_equity", "op": "<=", "value": 0.5},
]


def test_validate_thesis():
    assert validate_thesis("AAPL", CONDS) == []
    assert "thesis.ticker is required" in validate_thesis("", CONDS)
    assert validate_thesis("AAPL", []) == ["thesis needs at least one condition"]
    bad = validate_thesis("AAPL", [{"metric": "nope", "op": ">=", "value": 1}])
    assert any("metric must be one of" in p for p in bad)


def test_intact_when_all_pass():
    m = {"revenue_growth_5y_pct": 25, "net_margin_pct": 18, "debt_to_equity": 0.3}
    ev = evaluate_thesis(CONDS, m, m)
    assert ev["status"] == INTACT
    assert ev["met"] == 3 and ev["total"] == 3
    assert all(c["passed"] for c in ev["checks"])


def test_broken_when_a_condition_fails():
    base = {"revenue_growth_5y_pct": 25, "net_margin_pct": 18, "debt_to_equity": 0.3}
    now = {"revenue_growth_5y_pct": 8, "net_margin_pct": 18, "debt_to_equity": 0.3}
    ev = evaluate_thesis(CONDS, now, base)
    assert ev["status"] == BROKEN
    assert ev["met"] == 2
    failing = [c for c in ev["checks"] if not c["passed"]]
    assert failing[0]["metric"] == "revenue_growth_5y_pct"
    assert failing[0]["drift"] == -17  # 8 - 25


def test_weakening_when_passing_but_slipping():
    base = {"revenue_growth_5y_pct": 40, "net_margin_pct": 18, "debt_to_equity": 0.3}
    # revenue growth still ≥ 20 but fell well below baseline (40 → 22, -45%)
    now = {"revenue_growth_5y_pct": 22, "net_margin_pct": 18, "debt_to_equity": 0.3}
    ev = evaluate_thesis(CONDS, now, base)
    assert ev["status"] == WEAKENING
    assert ev["met"] == 3  # nothing has broken yet


def test_missing_metric_counts_as_failed():
    ev = evaluate_thesis(CONDS, {"net_margin_pct": 18, "debt_to_equity": 0.3})
    assert ev["status"] == BROKEN
    miss = [c for c in ev["checks"] if c["metric"] == "revenue_growth_5y_pct"][0]
    assert miss["passed"] is False and miss["actual"] is None


def test_snapshot_keeps_numeric_metric_keys_only():
    snap = snapshot_metrics({"pe_ratio": 12.0, "price": None, "junk": "x", "roe_pct": 20})
    assert snap == {"pe_ratio": 12.0, "roe_pct": 20}
