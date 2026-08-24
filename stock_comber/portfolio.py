"""Portfolio Advisor — score a set of holdings against the selected strategies,
derive per-holding buy/sell targets from Graham fair value, and suggest a more
balanced set of weights.

All pure functions over already-screened result dicts (the shape returned by
``api/screen.run_screen`` / ``ScreenResult.to_dict``): each has ``ticker``,
``strategy``, ``passed``, ``score_pct``, ``sector`` and a ``metrics`` mapping.
No network — the caller runs the screen and passes the results in.
"""

from __future__ import annotations

from typing import Any, Optional

# Value-investing guardrails. The valuation *verdict* still compares the current
# price to Graham fair value (a deep-value test), but the actionable buy/sell
# targets are anchored to the *current price* so they sit close to it — a small
# pullback to add on, a modest run-up to trim into — tilted by the verdict.
BUY_MARGIN = 0.25       # undervalued when price is >=25% below fair value
SELL_PREMIUM = 0.10     # overvalued when price is >=10% above fair value
BUY_PULLBACK = 0.05     # "buy below" = a ~5% dip from the current price (default)
SELL_RUNUP = 0.10       # "sell/trim above" = a ~10% run-up from the current price (default)
MAX_WEIGHT = 0.25       # single-position concentration ceiling
SECTOR_MAX = 0.40       # per-sector concentration ceiling
WEAK_SCORE = 40.0       # a holding scoring below this is flagged for review


def _num(v: Any) -> Optional[float]:
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _for_ticker(ticker: str, results: list[dict], strategies: list[str]) -> list[dict]:
    return [r for r in results if r.get("ticker") == ticker
            and (not strategies or r.get("strategy") in strategies)]


def holding_score(ticker: str, results: list[dict],
                  strategies: Optional[list[str]] = None) -> Optional[float]:
    """Average ``score_pct`` across the chosen strategies for this ticker (0..100)."""
    picks = _for_ticker(ticker, results, strategies or [])
    vals = [s for s in (_num(r.get("score_pct")) for r in picks) if s is not None]
    return round(sum(vals) / len(vals), 1) if vals else None


def holding_passes(ticker: str, results: list[dict],
                   strategies: Optional[list[str]] = None) -> bool:
    """True when the ticker passes at least one of the chosen strategies."""
    return any(r.get("passed") for r in _for_ticker(ticker, results, strategies or []))


def targets(price: Any, fair_value: Any) -> dict:
    """Actionable buy-below / sell-above levels close to the current price, plus a
    valuation verdict comparing the price to Graham fair value.

    The bands are anchored to the current price (a small pullback to add on, a
    modest run-up to trim into) and tilted by the verdict — tighter on the buy
    side when a name looks cheap, tighter on the sell side when it looks rich.
    With no current price we fall back to fair-value bands; with neither, ``n/a``.
    """
    price_n, fv = _num(price), _num(fair_value)

    # Valuation verdict from the deep-value test against fair value.
    verdict = "n/a"
    if fv is not None and fv > 0 and price_n is not None:
        if price_n <= fv * (1 - BUY_MARGIN):
            verdict = "undervalued"
        elif price_n >= fv * (1 + SELL_PREMIUM):
            verdict = "overvalued"
        else:
            verdict = "fair"

    if price_n is None or price_n <= 0:
        # No price to anchor to — fall back to the fair-value bands (or n/a).
        if fv is None or fv <= 0:
            return {"fair_value": None, "buy_below": None, "sell_above": None, "verdict": "n/a"}
        return {"fair_value": round(fv, 2), "buy_below": round(fv * (1 - BUY_MARGIN), 2),
                "sell_above": round(fv * (1 + SELL_PREMIUM), 2), "verdict": "fair"}

    buy_pull, sell_run = BUY_PULLBACK, SELL_RUNUP
    if verdict == "undervalued":       # cheap: add closer to price, let winners run further
        buy_pull, sell_run = BUY_PULLBACK / 2, SELL_RUNUP * 1.5
    elif verdict == "overvalued":      # rich: wait for a deeper dip, trim closer to price
        buy_pull, sell_run = BUY_PULLBACK * 1.5, SELL_RUNUP / 2
    return {
        "fair_value": round(fv, 2) if fv else None,
        "buy_below": round(price_n * (1 - buy_pull), 2),
        "sell_above": round(price_n * (1 + sell_run), 2),
        "verdict": verdict,
    }


def _metrics_for(ticker: str, results: list[dict]) -> dict:
    for r in results:
        if r.get("ticker") == ticker and r.get("metrics"):
            return r["metrics"] or {}
    return {}


def _sector_for(ticker: str, results: list[dict]) -> Optional[str]:
    for r in results:
        if r.get("ticker") == ticker and r.get("sector"):
            return r["sector"]
    return None


def _suggestions(rows: list[dict]) -> list[dict]:
    out: list[dict] = []
    for r in rows:
        if r["weight"] > MAX_WEIGHT:
            out.append({"type": "concentration",
                        "message": f"{r['ticker']} is {r['weight'] * 100:.0f}% of the portfolio — "
                                   f"above the {MAX_WEIGHT * 100:.0f}% single-position guide; consider trimming."})
    sectors: dict[str, float] = {}
    for r in rows:
        sectors[r.get("sector") or "Unknown"] = sectors.get(r.get("sector") or "Unknown", 0.0) + r["weight"]
    for sec, w in sectors.items():
        if sec != "Unknown" and w > SECTOR_MAX:
            out.append({"type": "sector",
                        "message": f"{sec} is {w * 100:.0f}% of the portfolio — above the "
                                   f"{SECTOR_MAX * 100:.0f}% sector guide; diversify into other sectors."})
    over = [r["ticker"] for r in rows if r["verdict"] == "overvalued"]
    under = [r["ticker"] for r in rows if r["verdict"] == "undervalued"]
    if over:
        out.append({"type": "valuation", "message": "Trading above fair value (consider trimming): " + ", ".join(over) + "."})
    if under:
        out.append({"type": "valuation", "message": "Trading below fair value (potential adds): " + ", ".join(under) + "."})
    weak = [r["ticker"] for r in rows if r["score"] is not None and r["score"] < WEAK_SCORE]
    if weak:
        out.append({"type": "quality", "message": "Low strategy score — review the thesis: " + ", ".join(weak) + "."})
    if 0 < len(rows) < 5:
        out.append({"type": "diversification",
                    "message": f"Only {len(rows)} holding(s) — a more balanced portfolio usually spreads "
                               "across 8–15 names and several sectors."})
    if not out:
        out.append({"type": "ok", "message": "No major concentration or valuation flags — the portfolio looks reasonably balanced."})
    return out


def _target_weights(rows: list[dict]) -> dict[str, float]:
    """Suggested weights tilted toward higher-scoring holdings: drop weak scorers,
    weight the rest in proportion to their score, and normalize to 1.0. (The 25%
    single-position guide is surfaced as a suggestion rather than hard-capped here,
    since a cap is infeasible for a handful of names.)"""
    cand = {r["ticker"]: (r["score"] or 0.0) for r in rows if (r["score"] or 0.0) >= WEAK_SCORE}
    total = sum(cand.values())
    if total <= 0:
        return {}
    return {t: round(s / total, 4) for t, s in cand.items()}


def analyze(holdings: list[dict], results: list[dict],
            strategies: Optional[list[str]] = None) -> dict:
    """Score a portfolio and return per-holding rows, a value-weighted score,
    buy/sell targets, balance suggestions and suggested target weights."""
    strategies = [s for s in (strategies or []) if s]
    priced: list[tuple] = []
    total_value = 0.0
    for h in holdings:
        ticker = str((h or {}).get("ticker", "")).strip().upper()
        if not ticker:
            continue
        shares = _num((h or {}).get("shares")) or 0.0
        metrics = _metrics_for(ticker, results)
        price = _num(metrics.get("price"))
        value = (price or 0.0) * shares
        total_value += value
        priced.append((ticker, shares, price, value, metrics))

    rows: list[dict] = []
    for ticker, shares, price, value, metrics in priced:
        weight = (value / total_value) if total_value else 0.0
        score = holding_score(ticker, results, strategies)
        tgt = targets(price, metrics.get("graham_number"))
        if tgt["verdict"] == "undervalued" and (score or 0) >= 50:
            action = "buy"
        elif tgt["verdict"] == "overvalued":
            action = "trim"
        elif score is not None and score < WEAK_SCORE:
            action = "review"
        else:
            action = "hold"
        rows.append({
            "ticker": ticker, "shares": shares, "price": price,
            "value": round(value, 2), "weight": round(weight, 4),
            "score": score, "passing": holding_passes(ticker, results, strategies),
            "sector": _sector_for(ticker, results), "action": action, **tgt,
        })

    scored = [(r["value"], r["score"]) for r in rows if r["score"] is not None]
    wsum = sum(v for v, _ in scored)
    if wsum > 0:
        pscore: Optional[float] = round(sum(v * s for v, s in scored) / wsum, 1)
    elif scored:
        pscore = round(sum(s for _, s in scored) / len(scored), 1)
    else:
        pscore = None

    return {
        "holdings": rows,
        "total_value": round(total_value, 2),
        "score": pscore,
        "passing": sum(1 for r in rows if r["passing"]),
        "count": len(rows),
        "suggestions": _suggestions(rows),
        "target_weights": _target_weights(rows),
        "strategies": strategies,
    }
