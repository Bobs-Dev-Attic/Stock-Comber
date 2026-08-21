"""Derived financial metrics computed from raw annual fundamentals + price."""

from __future__ import annotations

import math
from typing import Optional

from .models import AnnualFacts, Company


def _safe_div(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or b is None or b == 0:
        return None
    return a / b


def current_ratio(a: AnnualFacts) -> Optional[float]:
    return _safe_div(a.current_assets, a.current_liabilities)


def working_capital(a: AnnualFacts) -> Optional[float]:
    if a.current_assets is None or a.current_liabilities is None:
        return None
    return a.current_assets - a.current_liabilities


def debt_to_equity(a: AnnualFacts) -> Optional[float]:
    return _safe_div(a.total_liabilities, a.stockholders_equity)


def long_term_debt_to_equity(a: AnnualFacts) -> Optional[float]:
    return _safe_div(a.long_term_debt, a.stockholders_equity)


def roe(a: AnnualFacts) -> Optional[float]:
    """Return on equity as a percentage."""
    r = _safe_div(a.net_income, a.stockholders_equity)
    return r * 100.0 if r is not None else None


def net_margin(a: AnnualFacts) -> Optional[float]:
    """Net profit margin as a percentage."""
    r = _safe_div(a.net_income, a.revenue)
    return r * 100.0 if r is not None else None


def eps(a: AnnualFacts) -> Optional[float]:
    """Reported diluted/basic EPS, falling back to net income / shares."""
    if a.eps is not None:
        return a.eps
    return _safe_div(a.net_income, a.shares_outstanding)


def book_value_per_share(a: AnnualFacts) -> Optional[float]:
    return _safe_div(a.stockholders_equity, a.shares_outstanding)


def free_cash_flow(a: AnnualFacts) -> Optional[float]:
    """Operating cash flow minus capex (capex is reported as a positive outflow)."""
    if a.operating_cash_flow is None or a.capital_expenditures is None:
        return None
    return a.operating_cash_flow - abs(a.capital_expenditures)


def graham_number(a: AnnualFacts) -> Optional[float]:
    """sqrt(22.5 * EPS * BVPS) — Graham's fair-value ceiling."""
    e = eps(a)
    b = book_value_per_share(a)
    if e is None or b is None or e <= 0 or b <= 0:
        return None
    return math.sqrt(22.5 * e * b)


def cumulative_growth_pct(
    annuals: list[AnnualFacts], years: int, attr: str = "net_income"
) -> Optional[float]:
    """Percent growth of ``attr`` from ``years`` ago to the latest year.

    Uses averaged endpoints (3-year averages when available) to damp one-off
    swings, mirroring how Graham smoothed earnings.
    """
    vals = [(a.fiscal_year, getattr(a, attr)) for a in annuals if getattr(a, attr) is not None]
    if len(vals) < 2:
        return None
    vals.sort()
    window = vals[-(years + 1):] if years + 1 <= len(vals) else vals
    start = window[0][1]
    end = window[-1][1]
    if start is None or start <= 0:
        return None
    return 100.0 * (end - start) / start


def return_on_assets(a: AnnualFacts) -> Optional[float]:
    """Return on assets as a percentage."""
    r = _safe_div(a.net_income, a.total_assets)
    return r * 100.0 if r is not None else None


def asset_turnover(a: AnnualFacts) -> Optional[float]:
    """Revenue / total assets."""
    return _safe_div(a.revenue, a.total_assets)


def return_on_capital(a: AnnualFacts) -> Optional[float]:
    """Greenblatt-style return on capital: net income / (equity + long-term debt),
    as a percentage. A pragmatic free-data stand-in for EBIT / (net working
    capital + net fixed assets)."""
    eq = a.stockholders_equity
    ltd = a.long_term_debt or 0.0
    if eq is None:
        return None
    denom = eq + ltd
    if denom <= 0:
        return None
    r = _safe_div(a.net_income, denom)
    return r * 100.0 if r is not None else None


def ncav_per_share(a: AnnualFacts) -> Optional[float]:
    """Net current asset value per share = (current assets − total liabilities)
    / shares. Graham's deep-value 'net-net' anchor."""
    if a.current_assets is None or a.total_liabilities is None:
        return None
    ncav = a.current_assets - a.total_liabilities
    return _safe_div(ncav, a.shares_outstanding)


def market_cap(price: Optional[float], a: AnnualFacts) -> Optional[float]:
    if price is None or a.shares_outstanding is None:
        return None
    return price * a.shares_outstanding


def earnings_yield(price: Optional[float], a: AnnualFacts) -> Optional[float]:
    """Earnings yield as a percentage (net income / market cap ≈ 1/PE)."""
    mc = market_cap(price, a)
    r = _safe_div(a.net_income, mc)
    return r * 100.0 if r is not None else None


def cagr_pct(annuals: list[AnnualFacts], years: int, attr: str = "net_income") -> Optional[float]:
    """Compound annual growth rate of ``attr`` over the window, as a percentage.
    Returns None when the endpoints aren't both positive."""
    vals = [(a.fiscal_year, getattr(a, attr)) for a in annuals if getattr(a, attr) is not None]
    if len(vals) < 2:
        return None
    vals.sort()
    window = vals[-(years + 1):] if years + 1 <= len(vals) else vals
    start = window[0][1]
    end = window[-1][1]
    span = window[-1][0] - window[0][0]
    if start is None or end is None or start <= 0 or end <= 0 or span <= 0:
        return None
    return 100.0 * ((end / start) ** (1.0 / span) - 1.0)


def pe_ratio(price: Optional[float], a: AnnualFacts) -> Optional[float]:
    e = eps(a)
    if price is None or e is None or e <= 0:
        return None
    return price / e


def pb_ratio(price: Optional[float], a: AnnualFacts) -> Optional[float]:
    b = book_value_per_share(a)
    if price is None or b is None or b <= 0:
        return None
    return price / b


def _finnhub_avg_volume(extra: Optional[dict]) -> Optional[float]:
    """Average daily share volume from a Finnhub metric bundle (reported in
    millions of shares), preferring the smoothed 3-month figure. None if absent."""
    if not extra:
        return None
    for key in ("3MonthAverageTradingVolume", "10DayAverageTradingVolume"):
        val = extra.get(key)
        if val:
            try:
                return float(val) * 1e6
            except (TypeError, ValueError):
                pass
    return None


def average_volume(company: Company) -> Optional[float]:
    """Average daily share volume. Uses Finnhub's smoothed 3-month/10-day figure
    when the result is enriched, otherwise the latest day's volume from the price
    quote. None when no volume is available."""
    v = _finnhub_avg_volume(company.extra)
    if v is not None:
        return v
    q = company.quote
    return q.volume if q is not None else None


def dollar_volume(company: Company) -> Optional[float]:
    """Average daily dollar volume (price x average share volume) — the standard
    liquidity gauge: higher means the stock is easier to trade in size."""
    vol = average_volume(company)
    price = company.quote.price if company.quote else None
    if vol is None or price is None:
        return None
    return price * vol


# The metric keys that custom criteria may target (also drives the UI builder).
METRIC_KEYS = [
    "price", "revenue", "net_income", "eps", "book_value_per_share",
    "current_ratio", "working_capital", "debt_to_equity",
    "long_term_debt_to_equity", "roe_pct", "net_margin_pct", "free_cash_flow",
    "graham_number", "pe_ratio", "pb_ratio",
    "earnings_growth_5y_pct", "revenue_growth_5y_pct",
    "roa_pct", "return_on_capital_pct", "earnings_yield_pct",
    "ncav_per_share", "earnings_cagr_5y_pct",
    "avg_volume", "dollar_volume",
]


def compute_metrics(company: Company) -> dict[str, Optional[float]]:
    """Compute the full metric bundle used by the screening strategies."""
    latest = company.latest
    price = company.quote.price if company.quote else None
    if latest is None:
        return {"price": price, "avg_volume": average_volume(company),
                "dollar_volume": dollar_volume(company)}
    return {
        "price": price,
        "revenue": latest.revenue,
        "net_income": latest.net_income,
        "eps": eps(latest),
        "book_value_per_share": book_value_per_share(latest),
        "current_ratio": current_ratio(latest),
        "working_capital": working_capital(latest),
        "debt_to_equity": debt_to_equity(latest),
        "long_term_debt_to_equity": long_term_debt_to_equity(latest),
        "roe_pct": roe(latest),
        "net_margin_pct": net_margin(latest),
        "free_cash_flow": free_cash_flow(latest),
        "graham_number": graham_number(latest),
        "pe_ratio": pe_ratio(price, latest),
        "pb_ratio": pb_ratio(price, latest),
        "earnings_growth_5y_pct": cumulative_growth_pct(company.annuals, 5, "net_income"),
        "revenue_growth_5y_pct": cumulative_growth_pct(company.annuals, 5, "revenue"),
        "roa_pct": return_on_assets(latest),
        "return_on_capital_pct": return_on_capital(latest),
        "earnings_yield_pct": earnings_yield(price, latest),
        "ncav_per_share": ncav_per_share(latest),
        "earnings_cagr_5y_pct": cagr_pct(company.annuals, 5, "net_income"),
        "avg_volume": average_volume(company),
        "dollar_volume": dollar_volume(company),
    }
