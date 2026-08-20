"""Benjamin Graham's "net-net" (NCAV) deep-value screen.

Graham's most conservative bargain test: buy below **net current asset value**
— current assets minus *all* liabilities — ideally at a discount (his classic
rule was paying no more than two-thirds of NCAV). Such opportunities are rare,
especially among large caps, so most names fail by design. Thresholds live in
``config["netnet"]``.
"""

from __future__ import annotations

from typing import Any

from .. import metrics
from ..models import Company, CriterionResult, ScreenResult


def evaluate_netnet(company: Company, cfg: dict[str, Any]) -> ScreenResult:
    nn = cfg.get("netnet", {})
    latest = company.latest
    m = metrics.compute_metrics(company)
    if latest is None:
        return ScreenResult(
            ticker=company.ticker, name=company.name, cik=company.cik,
            strategy="netnet", passed=False, score=0.0, max_score=0.0,
            metrics=m, errors=["no annual fundamentals available"],
        )

    results: list[CriterionResult] = []
    price = m.get("price")
    ncav_ps = m.get("ncav_per_share")
    discount = nn.get("discount", 0.667)  # Graham's two-thirds rule

    results.append(CriterionResult(
        "positive_ncav", passed=(ncav_ps is not None and ncav_ps > 0),
        actual=ncav_ps, threshold=0.0,
        detail="Net current asset value per share is positive (current assets exceed all liabilities).",
    ))
    below_ncav = (price is not None and ncav_ps is not None and ncav_ps > 0 and price <= ncav_ps)
    results.append(CriterionResult(
        "price_below_ncav", passed=below_ncav, actual=price, threshold=ncav_ps,
        detail="Price trades below net current asset value.",
    ))
    bargain = (price is not None and ncav_ps is not None and ncav_ps > 0
               and price <= discount * ncav_ps)
    results.append(CriterionResult(
        "graham_bargain", passed=bargain, actual=price,
        threshold=(discount * ncav_ps if ncav_ps else None),
        detail=f"Price at or below {int(discount*100)}% of NCAV (Graham's margin of safety).",
    ))
    # Not a burning match: still profitable / solvent.
    results.append(CriterionResult(
        "not_losing_money", passed=(latest.net_income is not None and latest.net_income > 0),
        actual=latest.net_income, threshold=0.0,
        detail="Company is not currently loss-making.",
    ))

    score = sum(r.weight for r in results if r.passed)
    max_score = sum(r.weight for r in results)
    # Net-nets are strict: require the core discount plus the guard by default.
    passed = bargain and (latest.net_income is not None and latest.net_income > 0)
    return ScreenResult(
        ticker=company.ticker, name=company.name, cik=company.cik, strategy="netnet",
        passed=passed, score=score, max_score=max_score, metrics=m, criteria=results,
    )
