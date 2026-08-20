"""Peter Lynch's growth-at-a-reasonable-price (GARP) lens.

From *One Up on Wall Street*. The signature test is the **PEG ratio** —
P/E divided by the earnings growth rate — where PEG ≤ 1 marks a fairly priced
grower. We pair it with a healthy (but not implausibly high) growth rate, a
sane balance sheet, and current profitability. Thresholds live in
``config["lynch"]``.
"""

from __future__ import annotations

from typing import Any, Optional

from .. import metrics
from ..models import Company, CriterionResult, ScreenResult


def evaluate_lynch(company: Company, cfg: dict[str, Any]) -> ScreenResult:
    ly = cfg.get("lynch", {})
    latest = company.latest
    m = metrics.compute_metrics(company)
    if latest is None:
        return ScreenResult(
            ticker=company.ticker, name=company.name, cik=company.cik,
            strategy="lynch", passed=False, score=0.0, max_score=0.0,
            metrics=m, errors=["no annual fundamentals available"],
        )

    results: list[CriterionResult] = []
    pe = m.get("pe_ratio")
    cagr = m.get("earnings_cagr_5y_pct")
    peg: Optional[float] = None
    if pe is not None and cagr is not None and cagr > 0:
        peg = pe / cagr
    m = {**m, "peg_ratio": peg}

    results.append(CriterionResult(
        "reasonable_peg", passed=(peg is not None and peg <= ly.get("max_peg", 1.0)),
        actual=peg, threshold=ly.get("max_peg", 1.0),
        detail="PEG (P/E ÷ earnings growth) at or below the fair-price line.",
    ))
    results.append(CriterionResult(
        "solid_growth",
        passed=(cagr is not None and ly.get("min_growth_pct", 15.0) <= cagr <= ly.get("max_growth_pct", 50.0)),
        actual=cagr, threshold=ly.get("min_growth_pct", 15.0),
        detail=f"Earnings growth in Lynch's sweet spot "
               f"({ly.get('min_growth_pct',15.0)}–{ly.get('max_growth_pct',50.0)}%/yr).",
    ))
    de = m.get("debt_to_equity")
    results.append(CriterionResult(
        "manageable_debt", passed=(de is not None and de <= ly.get("max_debt_to_equity", 0.8)),
        actual=de, threshold=ly.get("max_debt_to_equity", 0.8),
        detail="Debt is not overwhelming equity.",
    ))
    results.append(CriterionResult(
        "profitable", passed=(latest.net_income is not None and latest.net_income > 0),
        actual=latest.net_income, threshold=0.0,
        detail="Company is currently profitable.",
    ))

    score = sum(r.weight for r in results if r.passed)
    max_score = sum(r.weight for r in results)
    passed = max_score > 0 and (score / max_score) >= ly.get("pass_ratio", 0.75)
    return ScreenResult(
        ticker=company.ticker, name=company.name, cik=company.cik, strategy="lynch",
        passed=passed, score=score, max_score=max_score, metrics=m, criteria=results,
    )
