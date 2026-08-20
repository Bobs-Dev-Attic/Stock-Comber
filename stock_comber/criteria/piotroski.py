"""Piotroski F-Score — a 9-point test of financial strength.

Joseph Piotroski's score (2000) rewards firms whose fundamentals are improving
across profitability, leverage/liquidity, and operating efficiency. Each of the
nine binary signals is worth one point; a company "passes" when its score meets
``config["piotroski"]["min_score"]`` (default 7 of 9).

Two signals use free-data stand-ins: the profitability-trend and margin signals
use net margin (we don't extract COGS/gross profit). Documented in each rule.
"""

from __future__ import annotations

from typing import Any, Optional

from .. import metrics
from ..models import Company, CriterionResult, ScreenResult


def _prior(company: Company):
    return company.annuals[-2] if len(company.annuals) >= 2 else None


def _sig(name: str, passed: bool, detail: str,
         actual: Optional[float] = None) -> CriterionResult:
    return CriterionResult(name, passed=passed, actual=actual, threshold=1.0, detail=detail)


def evaluate_piotroski(company: Company, cfg: dict[str, Any]) -> ScreenResult:
    p = cfg.get("piotroski", {})
    latest = company.latest
    m = metrics.compute_metrics(company)
    if latest is None:
        return ScreenResult(
            ticker=company.ticker, name=company.name, cik=company.cik,
            strategy="piotroski", passed=False, score=0.0, max_score=0.0,
            metrics=m, errors=["no annual fundamentals available"],
        )
    prev = _prior(company)
    sig: list[CriterionResult] = []

    roa = metrics.return_on_assets(latest)
    cfo = latest.operating_cash_flow
    ni = latest.net_income

    # Profitability (4)
    sig.append(_sig("positive_roa", roa is not None and roa > 0,
                    "Return on assets is positive.", roa))
    sig.append(_sig("positive_cfo", cfo is not None and cfo > 0,
                    "Operating cash flow is positive.", cfo))
    roa_prev = metrics.return_on_assets(prev) if prev else None
    sig.append(_sig("rising_roa", roa is not None and roa_prev is not None and roa > roa_prev,
                    "Return on assets improved year over year.", roa))
    sig.append(_sig("accruals", cfo is not None and ni is not None and cfo > ni,
                    "Operating cash flow exceeds net income (earnings quality).", cfo))

    # Leverage, liquidity, dilution (3)
    ltd_ratio = metrics._safe_div(latest.long_term_debt or 0.0, latest.total_assets)
    ltd_prev = (metrics._safe_div(prev.long_term_debt or 0.0, prev.total_assets)
                if prev else None)
    sig.append(_sig("lower_leverage",
                    ltd_ratio is not None and ltd_prev is not None and ltd_ratio <= ltd_prev,
                    "Long-term debt ratio did not rise.", ltd_ratio))
    cr, cr_prev = metrics.current_ratio(latest), (metrics.current_ratio(prev) if prev else None)
    sig.append(_sig("rising_liquidity",
                    cr is not None and cr_prev is not None and cr > cr_prev,
                    "Current ratio improved year over year.", cr))
    sh, sh_prev = latest.shares_outstanding, (prev.shares_outstanding if prev else None)
    sig.append(_sig("no_dilution",
                    sh is not None and sh_prev is not None and sh <= sh_prev * 1.01,
                    "No meaningful new share issuance.", sh))

    # Operating efficiency (2) — margin uses net margin as a gross-margin proxy.
    nm, nm_prev = metrics.net_margin(latest), (metrics.net_margin(prev) if prev else None)
    sig.append(_sig("rising_margin",
                    nm is not None and nm_prev is not None and nm > nm_prev,
                    "Net margin improved (gross-margin stand-in).", nm))
    at, at_prev = metrics.asset_turnover(latest), (metrics.asset_turnover(prev) if prev else None)
    sig.append(_sig("rising_turnover",
                    at is not None and at_prev is not None and at > at_prev,
                    "Asset turnover improved year over year.", at))

    score = sum(1.0 for s in sig if s.passed)
    max_score = float(len(sig))
    min_score = p.get("min_score", 7)
    passed = score >= min_score

    m = {**m, "piotroski_f_score": score}
    return ScreenResult(
        ticker=company.ticker, name=company.name, cik=company.cik, strategy="piotroski",
        passed=passed, score=score, max_score=max_score, metrics=m, criteria=sig,
    )
