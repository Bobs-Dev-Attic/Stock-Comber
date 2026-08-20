from stock_comber.criteria import evaluate_buffett, evaluate_graham


def test_graham_strong_passes(strong_company, config):
    res = evaluate_graham(strong_company, config)
    assert res.strategy == "graham"
    assert res.passed, [c.name for c in res.criteria if not c.passed]


def test_graham_weak_fails(weak_company, config):
    res = evaluate_graham(weak_company, config)
    assert not res.passed


def test_buffett_strong_passes(strong_company, config):
    res = evaluate_buffett(strong_company, config)
    assert res.passed, [c.name for c in res.criteria if not c.passed]


def test_buffett_weak_fails(weak_company, config):
    res = evaluate_buffett(weak_company, config)
    assert not res.passed


def test_thresholds_are_adjustable(weak_company, config):
    # Loosen every Buffett threshold to the floor; the weak company should
    # then clear the (now trivial) bar, proving the knobs actually drive scoring.
    config["buffett"].update({
        "min_roe_pct": -1e9, "max_debt_to_equity": 1e9,
        "min_net_margin_pct": -1e9, "min_earnings_growth_pct": -1e9,
        "require_positive_fcf": False, "roe_consistency_years": 1,
        "pass_ratio": 0.5,
    })
    res = evaluate_buffett(weak_company, config)
    assert res.passed


def test_missing_fundamentals_do_not_crash(config):
    from stock_comber.models import Company
    res = evaluate_graham(Company(ticker="NADA"), config)
    assert not res.passed
    assert res.errors
