from stock_comber.signals import compute_signal


def _r(strategy, passed, score_pct, max_score=9.0):
    return {"strategy": strategy, "passed": passed,
            "max_score": max_score, "score_pct": score_pct}


def test_na_when_nothing_evaluated():
    sig = compute_signal([_r("graham", False, 0.0, max_score=0.0)])
    assert sig["action"] == "N/A"
    assert sig["evaluated"] == 0


def test_buy_on_broad_agreement():
    rows = [_r("graham", True, 80), _r("buffett", True, 90),
            _r("piotroski", True, 78), _r("lynch", False, 40)]
    sig = compute_signal(rows)
    assert sig["action"] == "BUY"
    assert sig["passed"] == 3 and sig["evaluated"] == 4
    assert set(sig["passing_strategies"]) == {"graham", "buffett", "piotroski"}
    assert 0 <= sig["score"] <= 100


def test_avoid_when_weak():
    rows = [_r("graham", False, 20), _r("buffett", False, 15),
            _r("piotroski", False, 30), _r("netnet", False, 10)]
    sig = compute_signal(rows)
    assert sig["action"] == "AVOID"
    assert sig["passed"] == 0


def test_watch_in_between():
    rows = [_r("graham", True, 55), _r("buffett", False, 48),
            _r("piotroski", False, 44), _r("netnet", False, 30)]
    sig = compute_signal(rows)
    assert sig["action"] == "WATCH"


def test_custom_strategy_is_ignored():
    # A user's custom lens must not sway the signal.
    rows = [_r("graham", False, 10), _r("custom", True, 100)]
    sig = compute_signal(rows)
    assert sig["evaluated"] == 1
    assert "custom" not in sig["passing_strategies"]
