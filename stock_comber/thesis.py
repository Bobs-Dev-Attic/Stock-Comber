"""Investment thesis tracker.

A *thesis* is the reasons you bought (or would buy) a stock, expressed as
measurable conditions on the fundamentals — e.g. "revenue growth ≥ 20%",
"net margin ≥ 15%", "debt/equity ≤ 0.5". Stock-Comber snapshots the metrics at
creation time (the *baseline*), then re-checks the live metrics on a schedule
and tells you whether the thesis still holds — and, when it doesn't, exactly
which conditions broke and how far each metric has drifted from the baseline.

Conditions reuse the custom-criteria vocabulary (``metric op value``), so the
same metrics and operators work here. This module has no I/O; persistence lives
in ``storage`` and the periodic re-check in ``check_theses``.
"""

from __future__ import annotations

from typing import Any, Optional

from . import metrics as _metrics
from .criteria.custom import OPS, _compare, validate_criteria

# Status vocabulary, worst-first for display.
INTACT = "intact"
WEAKENING = "weakening"
BROKEN = "broken"


def validate_thesis(ticker: str, conditions: list) -> list[str]:
    """Return a list of problems with a thesis (empty = valid)."""
    problems: list[str] = []
    if not ticker or not str(ticker).strip():
        problems.append("thesis.ticker is required")
    if not isinstance(conditions, list) or not conditions:
        problems.append("thesis needs at least one condition")
        return problems
    problems.extend(validate_criteria(conditions))
    return problems


def evaluate_thesis(conditions: list, current: dict,
                    baseline: Optional[dict] = None) -> dict:
    """Evaluate ``conditions`` against ``current`` metrics.

    Returns ``{status, met, total, checks}`` where each check carries the
    condition, the actual value, whether it passes, and the baseline value +
    drift (when a baseline is supplied). Status is:
      - ``intact``    — every condition still holds
      - ``weakening`` — all hold, but a metric has slipped ≥15% toward its limit
      - ``broken``    — one or more conditions no longer hold
    """
    current = current or {}
    baseline = baseline or {}
    checks: list[dict] = []
    failed = 0
    slipping = False
    for c in conditions:
        metric = c.get("metric")
        op = c.get("op")
        value = c.get("value")
        actual = current.get(metric)
        passed = _compare(actual, op, value)
        base = baseline.get(metric)
        drift = None
        if isinstance(actual, (int, float)) and isinstance(base, (int, float)):
            drift = round(actual - base, 4)
            # "weakening": still passing, but moved the wrong way vs. baseline by
            # ≥15% of the baseline magnitude (direction depends on the operator).
            if passed and base not in (0, None):
                worse = ((op in (">=", ">") and actual < base)
                         or (op in ("<=", "<") and actual > base))
                if worse and abs(actual - base) >= 0.15 * abs(base):
                    slipping = True
        if not passed:
            failed += 1
        checks.append({
            "metric": metric, "op": op, "value": value,
            "actual": actual, "passed": passed,
            "baseline": base, "drift": drift,
        })
    total = len(conditions)
    if failed:
        status = BROKEN
    elif slipping:
        status = WEAKENING
    else:
        status = INTACT
    return {"status": status, "met": total - failed, "total": total, "checks": checks}


def snapshot_metrics(company_metrics: dict) -> dict:
    """Keep only the numeric, thesis-relevant metric keys for a baseline/current
    snapshot (drops price-less/None noise, stays small in the DB)."""
    out = {}
    for k in _metrics.METRIC_KEYS:
        v = (company_metrics or {}).get(k)
        if isinstance(v, (int, float)):
            out[k] = v
    return out


def check_theses(store, screener, limit: int = 100) -> dict:
    """Re-evaluate every stored thesis against fresh metrics; persist results.

    Screens each distinct ticker once, evaluates all of its theses, and writes
    back status + current snapshot. Returns a summary; never raises for one bad
    ticker. ``screener`` is a configured :class:`Screener`.
    """
    if not getattr(store, "enabled", False):
        return {"checked": 0, "note": "no database configured"}
    theses = store.list_theses(limit=limit)
    if not theses:
        return {"checked": 0, "theses": []}

    by_ticker: dict[str, list] = {}
    for t in theses:
        by_ticker.setdefault(t["ticker"].upper(), []).append(t)

    done = []
    for ticker, group in by_ticker.items():
        try:
            results = screener.run([ticker])
            current = snapshot_metrics(results[0].metrics if results else {})
        except Exception as exc:  # a bad ticker must not sink the batch
            for th in group:
                done.append({"id": th["id"], "ticker": ticker, "error": str(exc)[:200]})
            continue
        for th in group:
            ev = evaluate_thesis(th["conditions"], current, th.get("baseline"))
            prev = th.get("status")
            try:
                store.update_thesis_check(th["id"], ev["status"], current, ev["checks"])
            except Exception as exc:
                done.append({"id": th["id"], "ticker": ticker, "error": str(exc)[:200]})
                continue
            done.append({"id": th["id"], "ticker": ticker, "status": ev["status"],
                         "changed": prev != ev["status"], "was": prev})
    return {"checked": len(done), "theses": done}
