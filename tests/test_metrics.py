import math

from stock_comber import metrics
from stock_comber.models import AnnualFacts


def _facts(**kw):
    return AnnualFacts(fiscal_year=2023, **kw)


def test_current_ratio_and_working_capital():
    a = _facts(current_assets=300, current_liabilities=150)
    assert metrics.current_ratio(a) == 2.0
    assert metrics.working_capital(a) == 150


def test_debt_to_equity_and_roe():
    a = _facts(total_liabilities=200, stockholders_equity=400, net_income=80, revenue=800)
    assert metrics.debt_to_equity(a) == 0.5
    assert metrics.roe(a) == 20.0
    assert metrics.net_margin(a) == 10.0


def test_eps_fallback_to_net_income_over_shares():
    a = _facts(net_income=1000, shares_outstanding=250)
    assert metrics.eps(a) == 4.0
    b = _facts(eps=3.0, net_income=1000, shares_outstanding=250)
    assert metrics.eps(b) == 3.0  # reported EPS wins


def test_graham_number():
    a = _facts(eps=4.0, stockholders_equity=1000, shares_outstanding=100)  # bvps=10
    assert metrics.graham_number(a) == math.sqrt(22.5 * 4.0 * 10.0)


def test_free_cash_flow_handles_capex_sign():
    a = _facts(operating_cash_flow=300, capital_expenditures=50)
    assert metrics.free_cash_flow(a) == 250
    b = _facts(operating_cash_flow=300, capital_expenditures=-50)
    assert metrics.free_cash_flow(b) == 250


def test_safe_div_guards_zero():
    a = _facts(net_income=80, stockholders_equity=0)
    assert metrics.roe(a) is None


def test_cumulative_growth():
    annuals = [
        AnnualFacts(fiscal_year=2021, net_income=100),
        AnnualFacts(fiscal_year=2022, net_income=150),
        AnnualFacts(fiscal_year=2023, net_income=200),
    ]
    assert metrics.cumulative_growth_pct(annuals, 2, "net_income") == 100.0


def test_average_and_dollar_volume_from_quote():
    from stock_comber.models import Company, Quote
    c = Company(ticker="AAA", annuals=[_facts(net_income=100)],
                quote=Quote(ticker="AAA", price=20.0, volume=1_000_000))
    assert metrics.average_volume(c) == 1_000_000
    assert metrics.dollar_volume(c) == 20_000_000
    m = metrics.compute_metrics(c)
    assert m["avg_volume"] == 1_000_000
    assert m["dollar_volume"] == 20_000_000


def test_market_cap_in_compute_metrics():
    from stock_comber.models import Company, Quote
    c = Company(ticker="AAA", annuals=[_facts(net_income=100, shares_outstanding=250)],
                quote=Quote(ticker="AAA", price=20.0))
    m = metrics.compute_metrics(c)
    assert m["market_cap"] == 5000.0            # 20 × 250
    # Missing price or share count → None, not an error.
    c2 = Company(ticker="BBB", annuals=[_facts(net_income=1, shares_outstanding=None)],
                 quote=Quote(ticker="BBB", price=10.0))
    assert metrics.compute_metrics(c2)["market_cap"] is None


def test_average_volume_prefers_finnhub_smoothed_figure():
    from stock_comber.models import Company, Quote
    # Finnhub reports trading volume in millions of shares; 3-month wins.
    c = Company(ticker="BBB", annuals=[_facts(net_income=1)],
                quote=Quote(ticker="BBB", price=5.0, volume=999),
                extra={"3MonthAverageTradingVolume": 2.5,
                       "10DayAverageTradingVolume": 4.0})
    assert metrics.average_volume(c) == 2_500_000
    assert metrics.dollar_volume(c) == 12_500_000


def test_volume_metrics_none_when_unavailable():
    from stock_comber.models import Company, Quote
    c = Company(ticker="CCC", annuals=[_facts(net_income=1)],
                quote=Quote(ticker="CCC", price=5.0))
    assert metrics.average_volume(c) is None
    assert metrics.dollar_volume(c) is None
