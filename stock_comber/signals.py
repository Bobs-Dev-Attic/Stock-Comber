"""Turn the analyst checklists into a single, plain signal per company.

This is a transparent, rules-based summary of *how many of the value lenses a
company clears and how strongly* — NOT a price forecast and NOT advice. It maps
the per-strategy pass/fail + scores into one of:

    BUY    — broad agreement across the lenses, with solid average scores
    WATCH  — some lenses like it; worth keeping an eye on
    AVOID  — few or no lenses clear it
    N/A    — nothing could be evaluated (e.g. no fundamentals)

Everything is derived from data already computed by the strategies, so the
signal is reproducible and explainable.
"""

from __future__ import annotations

from typing import Any

# Only the value lenses count toward a signal; a user's ad-hoc "custom"
# strategy is excluded so it can't skew the consensus.
SIGNAL_STRATEGIES = {"graham", "buffett", "piotroski", "greenblatt", "lynch", "netnet"}


def _rows_from(results: Any) -> list[dict]:
    """Accept ScreenResult objects or already-serialised dicts."""
    out = []
    for r in results:
        if isinstance(r, dict):
            out.append(r)
        else:
            out.append({
                "strategy": r.strategy, "passed": r.passed,
                "max_score": r.max_score, "score_pct": getattr(r, "score_pct", 0.0),
            })
    return out


def compute_signal(results: Any) -> dict:
    """Summarise one ticker's per-strategy results into a single signal.

    ``results`` is the list of that ticker's strategy outcomes (ScreenResult or
    dicts). Returns {action, label, score, passed, evaluated, avg_score_pct,
    passing_strategies, reason}.
    """
    rows = [r for r in _rows_from(results)
            if r.get("strategy") in SIGNAL_STRATEGIES and (r.get("max_score") or 0) > 0]
    evaluated = len(rows)
    if not evaluated:
        return {
            "action": "N/A", "label": "Not analyzed", "score": 0.0,
            "passed": 0, "evaluated": 0, "avg_score_pct": 0.0,
            "passing_strategies": [],
            "reason": "No value lens could be scored (no fundamentals available).",
        }

    passing = [r["strategy"] for r in rows if r.get("passed")]
    passed = len(passing)
    ratio = passed / evaluated
    avg = sum(float(r.get("score_pct") or 0.0) for r in rows) / evaluated
    # Composite 0–100: blends how many lenses agree with how strong the scores are.
    score = round(0.6 * avg + 0.4 * ratio * 100.0, 1)

    if ratio >= 0.5 and avg >= 55.0:
        action, label = "BUY", "Broad value agreement"
    elif ratio >= 0.25 or avg >= 50.0:
        action, label = "WATCH", "Partial value support"
    else:
        action, label = "AVOID", "Weak value case"

    if passing:
        reason = (f"{passed} of {evaluated} lenses pass ({', '.join(passing)}); "
                  f"average score {avg:.0f}%.")
    else:
        reason = f"No lens passes; average score {avg:.0f}% across {evaluated} lenses."

    return {
        "action": action, "label": label, "score": score,
        "passed": passed, "evaluated": evaluated, "avg_score_pct": round(avg, 1),
        "passing_strategies": passing, "reason": reason,
    }
