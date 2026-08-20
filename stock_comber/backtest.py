"""A simple, transparent backtest: did a lens's verdict precede better returns?

For each fiscal year in a company's history we know two things: what the value
lens would have said using *only the fundamentals reported through that year*
(plus that year's year-end price), and what the stock actually did over the
*following* year. Lining those up tells you whether the lens's PASS verdicts
tended to precede stronger forward returns than its FAILs — a per-name,
point-in-time "did this signal have an edge?" check.

Caveats (it's educational, not a research backtest): free data gives us annual
fundamentals and year-end prices only, one name at a time, with no dividends,
survivorship control, or transaction costs. Treat the edge as directional
colour, not a track record.
"""

from __future__ import annotations

from typing import Any, Optional

from .criteria import STRATEGIES
from .models import Company, Quote

VALUE_STRATEGIES = ["graham", "buffett", "piotroski", "greenblatt", "lynch", "netnet"]


def _avg(xs: list) -> Optional[float]:
    return round(sum(xs) / len(xs), 2) if xs else None


def backtest_strategy(company: Company, price_by_year: dict, strategy: str,
                      cfg: dict) -> dict:
    """Replay one strategy across the company's fiscal-year history."""
    evaluate = STRATEGIES.get(strategy)
    if evaluate is None:
        return {"strategy": strategy, "years": [], "summary": {},
                "error": f"unknown strategy '{strategy}'"}

    annuals = sorted(company.annuals, key=lambda a: a.fiscal_year)
    years = []
    for a in annuals:
        y = a.fiscal_year
        price = price_by_year.get(y)
        nxt = price_by_year.get(y + 1)
        if not price or not nxt or price <= 0:
            continue
        as_of = Company(
            ticker=company.ticker, cik=company.cik, name=company.name,
            annuals=[x for x in annuals if x.fiscal_year <= y],
            quote=Quote(ticker=company.ticker, price=price, source="backtest"),
        )
        res = evaluate(as_of, cfg)
        passed = bool(res.passed) if res.max_score else None
        fwd = round((nxt / price - 1.0) * 100.0, 2)
        years.append({
            "year": y, "price": round(price, 2), "next_price": round(nxt, 2),
            "forward_return_pct": fwd, "passed": passed,
            "score_pct": round(res.score_pct, 1),
        })

    pass_rets = [r["forward_return_pct"] for r in years if r["passed"] is True]
    fail_rets = [r["forward_return_pct"] for r in years if r["passed"] is False]
    all_rets = [r["forward_return_pct"] for r in years]
    ap, af = _avg(pass_rets), _avg(fail_rets)
    summary = {
        "evaluated_years": len(years),
        "pass_years": len(pass_rets),
        "avg_forward_return_all": _avg(all_rets),
        "avg_forward_return_pass": ap,
        "avg_forward_return_fail": af,
        "pass_hit_rate_pct": (round(100.0 * sum(1 for r in pass_rets if r > 0) / len(pass_rets), 1)
                              if pass_rets else None),
        "edge_pct": (round(ap - af, 2) if ap is not None and af is not None else None),
    }
    return {"strategy": strategy, "years": years, "summary": summary}


def backtest_all(company: Company, price_by_year: dict, cfg: dict,
                 strategies: Optional[list] = None) -> dict:
    """Run every value lens and return per-strategy results."""
    strategies = strategies or VALUE_STRATEGIES
    out = {s: backtest_strategy(company, price_by_year, s, cfg) for s in strategies}
    price_years = sorted(price_by_year)
    return {
        "ticker": company.ticker, "name": company.name,
        "price_years": [{"year": y, "close": round(price_by_year[y], 2)} for y in price_years],
        "strategies": out,
    }
