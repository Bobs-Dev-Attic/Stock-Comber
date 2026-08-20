from stock_comber.config import load_config, validate_config
from stock_comber.criteria import STRATEGIES
from stock_comber.criteria.custom import evaluate_custom, validate_criteria


def test_custom_registered():
    assert "custom" in STRATEGIES


def test_custom_all_pass(strong_company):
    cfg = load_config()
    cfg["custom"]["criteria"] = [
        {"name": "Profitable", "metric": "roe_pct", "op": ">=", "value": 5},
        {"metric": "current_ratio", "op": ">=", "value": 1.0},
    ]
    res = evaluate_custom(strong_company, cfg)
    assert res.strategy == "custom"
    assert res.passed
    assert len(res.criteria) == 2
    assert all(c.passed for c in res.criteria)


def test_custom_partial_fails_by_default(strong_company):
    cfg = load_config()
    cfg["custom"]["criteria"] = [
        {"metric": "roe_pct", "op": ">=", "value": 5},        # passes
        {"metric": "pe_ratio", "op": "<=", "value": 0.01},    # fails
    ]
    res = evaluate_custom(strong_company, cfg)
    assert not res.passed  # default pass_ratio 1.0 requires all


def test_custom_pass_ratio_adjustable(strong_company):
    cfg = load_config()
    cfg["custom"]["pass_ratio"] = 0.5
    cfg["custom"]["criteria"] = [
        {"metric": "roe_pct", "op": ">=", "value": 5},        # passes
        {"metric": "pe_ratio", "op": "<=", "value": 0.01},    # fails
    ]
    res = evaluate_custom(strong_company, cfg)
    assert res.passed  # half is enough now


def test_custom_missing_metric_does_not_pass(strong_company):
    cfg = load_config()
    cfg["custom"]["criteria"] = [{"metric": "graham_number", "op": ">=", "value": 1e12}]
    res = evaluate_custom(strong_company, cfg)
    assert not res.passed


def test_empty_custom_reports_error(strong_company):
    cfg = load_config()
    res = evaluate_custom(strong_company, cfg)
    assert not res.passed
    assert any("no custom criteria" in e for e in res.errors)


def test_validate_criteria_flags_bad_metric_op_value():
    problems = validate_criteria([
        {"metric": "nonsense", "op": ">=", "value": 1},
        {"metric": "pe_ratio", "op": "=>", "value": 1},
        {"metric": "pe_ratio", "op": ">=", "value": "abc"},
    ])
    assert len(problems) == 3


def test_config_validation_runs_custom_checks():
    cfg = load_config()
    cfg["strategies"] = ["custom"]
    cfg["custom"]["criteria"] = [{"metric": "bad", "op": ">=", "value": 1}]
    assert any("metric" in p for p in validate_config(cfg))


def test_result_includes_cik(strong_company):
    cfg = load_config()
    from stock_comber.criteria import evaluate_graham
    strong_company.cik = "320193"
    res = evaluate_graham(strong_company, cfg)
    assert res.to_dict()["cik"] == "320193"
