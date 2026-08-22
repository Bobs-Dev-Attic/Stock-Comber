from stock_comber.backtest import backtest_strategy, backtest_all
from stock_comber.datasources.yahoo import parse_history
from stock_comber.models import AnnualFacts, Company


def _company():
    # Five years of steadily strong fundamentals (passes Graham-ish rules).
    annuals = []
    for i, fy in enumerate(range(2019, 2024)):
        annuals.append(AnnualFacts(
            fiscal_year=fy, revenue=2_000_000_000 + i * 1e8,
            net_income=3e8 + i * 2e7, total_assets=4e9, total_liabilities=1e9,
            stockholders_equity=3e9, current_assets=2.5e9, current_liabilities=5e8,
            long_term_debt=2e8, eps=3.0 + i * 0.2, shares_outstanding=1e8,
            operating_cash_flow=4e8, capital_expenditures=1e8,
        ))
    return Company(ticker="TEST", cik="1", name="Test Co", annuals=annuals)


def test_backtest_strategy_lines_up_years(config):
    prices = {2019: 30.0, 2020: 36.0, 2021: 40.0, 2022: 44.0, 2023: 50.0}
    bt = backtest_strategy(_company(), prices, "graham", config)
    # Years with both a price and a following-year price → 2019..2022 (2023 has no 2024 price).
    assert bt["strategy"] == "graham"
    assert [y["year"] for y in bt["years"]] == [2019, 2020, 2021, 2022]
    # 2019 → 2020 forward return = 36/30 - 1 = 20%.
    assert bt["years"][0]["forward_return_pct"] == 20.0
    assert bt["summary"]["evaluated_years"] == 4


def test_backtest_skips_years_without_forward_price(config):
    prices = {2019: 30.0, 2021: 40.0}  # gaps → no consecutive pair
    bt = backtest_strategy(_company(), prices, "graham", config)
    assert bt["years"] == []
    assert bt["summary"]["evaluated_years"] == 0


def test_backtest_all_covers_value_lenses(config):
    prices = {2019: 30.0, 2020: 36.0, 2021: 40.0, 2022: 44.0, 2023: 50.0}
    out = backtest_all(_company(), prices, config)
    assert set(out["strategies"]) == {"graham", "buffett", "piotroski",
                                      "greenblatt", "lynch", "netnet"}
    assert out["ticker"] == "TEST"
    assert len(out["price_years"]) == 5


def test_unknown_strategy_returns_error(config):
    bt = backtest_strategy(_company(), {2019: 1.0, 2020: 1.1}, "nope", config)
    assert "error" in bt


def test_parse_history_keeps_year_end_close():
    # Two months in 2020, one in 2021; keep the latest (year-end) close per year.
    import calendar
    def ts(y, m):  # epoch for the 1st of month, UTC
        return calendar.timegm((y, m, 1, 0, 0, 0))
    data = {"chart": {"result": [{
        "timestamp": [ts(2020, 6), ts(2020, 12), ts(2021, 12)],
        "indicators": {"quote": [{"close": [10.0, 15.0, 20.0]}]},
    }]}}
    hist = parse_history(data)
    assert hist == {2020: 15.0, 2021: 20.0}


def test_parse_history_bad_payload():
    assert parse_history({}) == {}
    assert parse_history({"chart": {"result": []}}) == {}


def test_overall_edge_averages_measurable_lenses(config):
    from stock_comber.backtest import overall_edge, VALUE_STRATEGIES, backtest_strategy
    prices = {2019: 30.0, 2020: 36.0, 2021: 40.0, 2022: 44.0, 2023: 50.0}
    edge = overall_edge(_company(), prices, config)
    # Mean of each lens's edge_pct across lenses that produced one.
    got = [backtest_strategy(_company(), prices, s, config)["summary"].get("edge_pct")
           for s in VALUE_STRATEGIES]
    got = [e for e in got if e is not None]
    if got:
        assert edge == round(sum(got) / len(got), 2)
    else:
        assert edge is None


def test_overall_edge_none_without_history(config):
    from stock_comber.backtest import overall_edge
    assert overall_edge(_company(), {2019: 30.0, 2021: 40.0}, config) is None
