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


def compute_metrics(company: Company) -> dict[str, Optional[float]]:
    """Compute the full metric bundle used by the screening strategies."""
    latest = company.latest
    price = company.quote.price if company.quote else None
    if latest is None:
        return {"price": price}
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
    }
