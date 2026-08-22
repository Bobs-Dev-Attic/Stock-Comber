"""Tests for SEC 10-Q quarterly extraction and the derived quarterly metrics."""

from stock_comber.datasources.sec_edgar import extract_quarters
from stock_comber.metrics import compute_metrics, quarterly_metrics
from stock_comber.models import Company, QuarterFacts, Quote


def _facts():
    """A minimal companyfacts doc: two quarterly revenue/NI periods (3-month
    10-Q flows), plus balance-sheet snapshots and a full-year 10-K flow to prove
    the annual period is excluded from the quarterly series."""
    return {"facts": {"us-gaap": {
        "Revenues": {"units": {"USD": [
            # 3-month quarterly flows (10-Q)
            {"start": "2024-01-01", "end": "2024-03-31", "val": 100, "form": "10-Q", "filed": "2024-04-30"},
            {"start": "2024-04-01", "end": "2024-06-30", "val": 120, "form": "10-Q", "filed": "2024-07-30"},
            # a YTD (6-month) 10-Q entry — must be ignored (not ~one quarter)
            {"start": "2024-01-01", "end": "2024-06-30", "val": 220, "form": "10-Q", "filed": "2024-07-30"},
            # a full-year 10-K flow — must be ignored for quarters
            {"start": "2023-01-01", "end": "2023-12-31", "val": 400, "form": "10-K", "filed": "2024-02-15"},
        ]}},
        "NetIncomeLoss": {"units": {"USD": [
            {"start": "2024-01-01", "end": "2024-03-31", "val": 10, "form": "10-Q", "filed": "2024-04-30"},
            {"start": "2024-04-01", "end": "2024-06-30", "val": 12, "form": "10-Q", "filed": "2024-07-30"},
        ]}},
        "EarningsPerShareDiluted": {"units": {"USD/shares": [
            {"start": "2024-04-01", "end": "2024-06-30", "val": 0.12, "form": "10-Q", "filed": "2024-07-30"},
        ]}},
        "AssetsCurrent": {"units": {"USD": [
            {"end": "2024-03-31", "val": 500, "form": "10-Q", "filed": "2024-04-30"},
            {"end": "2024-06-30", "val": 550, "form": "10-Q", "filed": "2024-07-30"},
        ]}},
        "LiabilitiesCurrent": {"units": {"USD": [
            {"end": "2024-06-30", "val": 220, "form": "10-Q", "filed": "2024-07-30"},
        ]}},
    }}}


def test_extract_quarters_flows_and_snapshot():
    qs = extract_quarters(_facts())
    assert [q.period_end for q in qs] == ["2024-03-31", "2024-06-30"]
    q1, q2 = qs
    assert q1.revenue == 100 and q1.net_income == 10
    assert q2.revenue == 120 and q2.net_income == 12 and q2.eps == 0.12
    # Balance-sheet snapshot is as-of the quarter end.
    assert q2.current_assets == 550 and q2.current_liabilities == 220
    # Q1 has no current-liabilities datapoint at/2024-03-31 → None (no look-ahead).
    assert q1.current_liabilities is None
    assert q2.fiscal_year == 2024


def test_extract_quarters_ignores_ytd_and_annual():
    qs = extract_quarters(_facts())
    # 220 (6-month YTD) and 400 (full-year) must never appear as a quarter.
    assert all(q.revenue in (100, 120) for q in qs)


def test_extract_quarters_empty():
    assert extract_quarters({}) == []
    assert extract_quarters({"facts": {"us-gaap": {}}}) == []


def test_quarterly_metrics_surface_latest_quarter():
    c = Company(ticker="TST", quarters=[
        QuarterFacts(period_end="2024-03-31", revenue=100, net_income=10),
        QuarterFacts(period_end="2024-06-30", revenue=120, net_income=12, eps=0.12,
                     current_assets=550, current_liabilities=220),
    ])
    m = quarterly_metrics(c)
    assert m["latest_quarter"] == "2024-06-30"
    assert m["q_revenue"] == 120 and m["q_net_income"] == 12 and m["q_eps"] == 0.12
    assert round(m["q_current_ratio"], 2) == 2.5


def test_compute_metrics_includes_quarter_without_annual():
    # No annuals → still surfaces quarterly keys (doesn't crash).
    c = Company(ticker="TST", quote=Quote(ticker="TST", price=5.0),
                quarters=[QuarterFacts(period_end="2024-06-30", revenue=120)])
    m = compute_metrics(c)
    assert m["q_revenue"] == 120 and m["latest_quarter"] == "2024-06-30"
