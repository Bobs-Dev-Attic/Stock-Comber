"""Benjamin Graham's "defensive investor" criteria.

From *The Intelligent Investor* (Ch. 14). Each rule is expressed against
adjustable thresholds in ``config["graham"]`` so scheduled jobs can be tuned.
"""

from __future__ import annotations

from typing import Any

from .. import metrics
from ..models import Company, CriterionResult, ScreenResult


def _series(company: Company, attr: str) -> list[float]:
    return [getattr(a, attr) for a in company.annuals if getattr(a, attr) is not None]


def evaluate_graham(company: Company, cfg: dict[str, Any]) -> ScreenResult:
    g = cfg["graham"]
    latest = company.latest
    results: list[CriterionResult] = []
    errors: list[str] = []
    m = metrics.compute_metrics(company)

    if latest is None:
        return ScreenResult(
            ticker=company.ticker, name=company.name, cik=company.cik, strategy="graham",
            passed=False, score=0.0, max_score=0.0, metrics=m,
            errors=["no annual fundamentals available"],
        )

    # 1. Adequate size (revenue).
    rev = latest.revenue
    results.append(CriterionResult(
        "adequate_size", passed=(rev is not None and rev >= g["min_revenue"]),
        actual=rev, threshold=g["min_revenue"],
        detail="Annual revenue above the minimum size floor.",
    ))

    # 2. Strong current ratio.
    cr = m.get("current_ratio")
    results.append(CriterionResult(
        "current_ratio", passed=(cr is not None and cr >= g["min_current_ratio"]),
        actual=cr, threshold=g["min_current_ratio"],
        detail="Current assets at least N times current liabilities.",
    ))

    # 3. Long-term debt below working capital (conservative leverage).
    if g.get("long_term_debt_under_working_capital", True):
        wc = m.get("working_capital")
        ltd = latest.long_term_debt
        passed = (wc is not None and ltd is not None and ltd <= wc)
        # If a company simply reports no long-term debt, that passes.
        if ltd is None and wc is not None and wc > 0:
            passed = True
        results.append(CriterionResult(
            "ltd_under_working_capital", passed=passed,
            actual=ltd, threshold=wc,
            detail="Long-term debt does not exceed working capital.",
        ))
    else:
        de = m.get("debt_to_equity")
        results.append(CriterionResult(
            "debt_to_equity", passed=(de is not None and de <= g["max_debt_to_equity"]),
            actual=de, threshold=g["max_debt_to_equity"],
            detail="Total liabilities within a multiple of equity.",
        ))

    # 4. Earnings stability: positive earnings for N consecutive recent years.
    need = g["positive_earnings_years"]
    ni = _series(company, "net_income")
    recent = ni[-need:]
    stable = len(ni) >= need and all(x > 0 for x in recent)
    results.append(CriterionResult(
        "earnings_stability", passed=stable,
        actual=float(sum(1 for x in recent if x > 0)), threshold=float(need),
        detail=f"Positive net income in each of the last {need} years.",
    ))

    # 5. Dividend record (optional).
    if g.get("require_dividend", False):
        divs = _series(company, "dividends_paid")
        paid = any(d and d != 0 for d in divs)
        results.append(CriterionResult(
            "dividend_record", passed=paid, actual=float(len(divs)),
            detail="Company has a record of paying dividends.",
        ))

    # 6. Earnings growth over the window.
    growth = metrics.cumulative_growth_pct(
        company.annuals, g["earnings_growth_years"], "net_income"
    )
    results.append(CriterionResult(
        "earnings_growth", passed=(growth is not None and growth >= g["min_earnings_growth_pct"]),
        actual=growth, threshold=g["min_earnings_growth_pct"],
        detail=f"Net income grew at least {g['min_earnings_growth_pct']}% over {g['earnings_growth_years']}y.",
    ))

    # 7. Moderate P/E.
    pe = m.get("pe_ratio")
    results.append(CriterionResult(
        "moderate_pe", passed=(pe is not None and pe <= g["max_pe"]),
        actual=pe, threshold=g["max_pe"],
        detail="Price/earnings below the value ceiling.",
    ))

    # 8. Moderate P/B.
    pb = m.get("pb_ratio")
    results.append(CriterionResult(
        "moderate_pb", passed=(pb is not None and pb <= g["max_pb"]),
        actual=pb, threshold=g["max_pb"],
        detail="Price/book below the value ceiling.",
    ))

    # 9. Graham number: P/E * P/B <= 22.5 (price <= Graham number).
    if pe is not None and pb is not None:
        product = pe * pb
        passed = product <= g["max_pe_times_pb"]
    else:
        product = None
        passed = False
    results.append(CriterionResult(
        "graham_number", passed=passed, actual=product, threshold=g["max_pe_times_pb"],
        detail="P/E times P/B within Graham's 22.5 ceiling.",
    ))

    # 10. Positive book value.
    if g.get("require_positive_book_value", True):
        bv = latest.stockholders_equity
        results.append(CriterionResult(
            "positive_book_value", passed=(bv is not None and bv > 0),
            actual=bv, threshold=0.0, detail="Positive shareholder equity.",
        ))

    score = sum(r.weight for r in results if r.passed)
    max_score = sum(r.weight for r in results)
    pass_ratio = g.get("pass_ratio", 0.8)
    passed = max_score > 0 and (score / max_score) >= pass_ratio

    return ScreenResult(
        ticker=company.ticker, name=company.name, cik=company.cik, strategy="graham",
        passed=passed, score=score, max_score=max_score,
        metrics=m, criteria=results, errors=errors,
    )
