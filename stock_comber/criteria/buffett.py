"""Warren Buffett-style quality criteria.

Buffett favours understandable businesses with a durable moat, high and
consistent returns on equity, low debt, fat margins, steady earnings growth,
and real free cash flow ("owner earnings"). The quantitative proxies below are
adjustable through ``config["buffett"]``.
"""

from __future__ import annotations

from typing import Any

from .. import metrics
from ..models import Company, CriterionResult, ScreenResult


def evaluate_buffett(company: Company, cfg: dict[str, Any]) -> ScreenResult:
    b = cfg["buffett"]
    latest = company.latest
    results: list[CriterionResult] = []
    m = metrics.compute_metrics(company)

    if latest is None:
        return ScreenResult(
            ticker=company.ticker, name=company.name, strategy="buffett",
            passed=False, score=0.0, max_score=0.0, metrics=m,
            errors=["no annual fundamentals available"],
        )

    # 1. High return on equity, latest year.
    roe = m.get("roe_pct")
    results.append(CriterionResult(
        "high_roe", passed=(roe is not None and roe >= b["min_roe_pct"]),
        actual=roe, threshold=b["min_roe_pct"],
        detail=f"Return on equity above {b['min_roe_pct']}%.",
    ))

    # 2. Consistent ROE across the window.
    need = b["roe_consistency_years"]
    roes = [metrics.roe(a) for a in company.annuals if metrics.roe(a) is not None]
    recent = roes[-need:]
    consistent = len(roes) >= need and all(r >= b["min_roe_pct"] for r in recent)
    results.append(CriterionResult(
        "consistent_roe", passed=consistent,
        actual=float(sum(1 for r in recent if r >= b["min_roe_pct"])), threshold=float(need),
        detail=f"ROE above target in each of the last {need} years.",
    ))

    # 3. Low leverage.
    de = m.get("debt_to_equity")
    results.append(CriterionResult(
        "low_debt", passed=(de is not None and de <= b["max_debt_to_equity"]),
        actual=de, threshold=b["max_debt_to_equity"],
        detail=f"Total-liabilities/equity below {b['max_debt_to_equity']}.",
    ))

    # 4. Strong net margin.
    nm = m.get("net_margin_pct")
    results.append(CriterionResult(
        "strong_margin", passed=(nm is not None and nm >= b["min_net_margin_pct"]),
        actual=nm, threshold=b["min_net_margin_pct"],
        detail=f"Net profit margin above {b['min_net_margin_pct']}%.",
    ))

    # 5. Consistent earnings growth over the window.
    growth = metrics.cumulative_growth_pct(
        company.annuals, b["earnings_growth_years"], "net_income"
    )
    results.append(CriterionResult(
        "earnings_growth", passed=(growth is not None and growth >= b["min_earnings_growth_pct"]),
        actual=growth, threshold=b["min_earnings_growth_pct"],
        detail=f"Net income grew at least {b['min_earnings_growth_pct']}% over {b['earnings_growth_years']}y.",
    ))

    # 6. Positive free cash flow ("owner earnings") over recent years.
    if b.get("require_positive_fcf", True):
        need_fcf = b["min_fcf_years"]
        fcfs = [metrics.free_cash_flow(a) for a in company.annuals
                if metrics.free_cash_flow(a) is not None]
        recent_fcf = fcfs[-need_fcf:]
        positive = len(fcfs) >= need_fcf and all(f > 0 for f in recent_fcf)
        results.append(CriterionResult(
            "positive_fcf", passed=positive,
            actual=float(sum(1 for f in recent_fcf if f > 0)), threshold=float(need_fcf),
            detail=f"Positive free cash flow in each of the last {need_fcf} years.",
        ))

    score = sum(r.weight for r in results if r.passed)
    max_score = sum(r.weight for r in results)
    pass_ratio = b.get("pass_ratio", 0.8)
    passed = max_score > 0 and (score / max_score) >= pass_ratio

    return ScreenResult(
        ticker=company.ticker, name=company.name, strategy="buffett",
        passed=passed, score=score, max_score=max_score,
        metrics=m, criteria=results, errors=[],
    )
