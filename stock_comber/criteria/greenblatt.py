"""Joel Greenblatt's "Magic Formula" (adapted to a threshold screen).

The Magic Formula ranks a universe by combining a **cheapness** measure
(earnings yield) with a **quality** measure (return on capital) and buys the
top names. Since this app scores each company independently, we express both as
adjustable thresholds: a company passes when it is both cheap enough and
productive enough. Return on capital and earnings yield use free-data
stand-ins (see ``metrics.return_on_capital`` / ``earnings_yield``).
"""

from __future__ import annotations

from typing import Any

from .. import metrics
from ..models import Company, CriterionResult, ScreenResult


def evaluate_greenblatt(company: Company, cfg: dict[str, Any]) -> ScreenResult:
    g = cfg.get("greenblatt", {})
    latest = company.latest
    m = metrics.compute_metrics(company)
    if latest is None:
        return ScreenResult(
            ticker=company.ticker, name=company.name, cik=company.cik,
            strategy="greenblatt", passed=False, score=0.0, max_score=0.0,
            metrics=m, errors=["no annual fundamentals available"],
        )

    results: list[CriterionResult] = []
    ey = m.get("earnings_yield_pct")
    roc = m.get("return_on_capital_pct")

    results.append(CriterionResult(
        "high_earnings_yield", passed=(ey is not None and ey >= g.get("min_earnings_yield_pct", 8.0)),
        actual=ey, threshold=g.get("min_earnings_yield_pct", 8.0),
        detail="Earnings yield (net income / market cap) is high enough — the stock is cheap.",
    ))
    results.append(CriterionResult(
        "high_return_on_capital", passed=(roc is not None and roc >= g.get("min_return_on_capital_pct", 20.0)),
        actual=roc, threshold=g.get("min_return_on_capital_pct", 20.0),
        detail="Return on capital is high — the business is productive with its capital.",
    ))
    # A light quality guard so a one-off cheap year alone doesn't pass.
    results.append(CriterionResult(
        "profitable", passed=(latest.net_income is not None and latest.net_income > 0),
        actual=latest.net_income, threshold=0.0,
        detail="Company is currently profitable.",
    ))

    score = sum(r.weight for r in results if r.passed)
    max_score = sum(r.weight for r in results)
    passed = max_score > 0 and (score / max_score) >= g.get("pass_ratio", 1.0)
    return ScreenResult(
        ticker=company.ticker, name=company.name, cik=company.cik, strategy="greenblatt",
        passed=passed, score=score, max_score=max_score, metrics=m, criteria=results,
    )
