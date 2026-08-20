"""Composite 0–100 scores (Value / Quality / Growth) and a blended health score.

Transparent, deterministic math on the metrics we already compute — no ML, no
paid data. Each component metric is mapped to 0–100 by a documented piecewise
band, then combined by fixed weights. Missing metrics are skipped and the
remaining weights renormalised, so a score is only ``None`` when nothing in that
category could be measured. Every score carries its component breakdown, so the
number is always explainable.
"""

from __future__ import annotations

from typing import Optional


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def _high(v: Optional[float], lo: float, hi: float) -> Optional[float]:
    """Higher is better: ``lo`` → 0, ``hi`` → 100 (clamped)."""
    if v is None or hi == lo:
        return None
    return round(100.0 * _clamp((v - lo) / (hi - lo)), 1)


def _low(v: Optional[float], lo: float, hi: float) -> Optional[float]:
    """Lower is better: ``lo`` → 100, ``hi`` → 0 (clamped)."""
    if v is None or hi == lo:
        return None
    return round(100.0 * _clamp((hi - v) / (hi - lo)), 1)


# (label, metric key, scorer, low, high, weight)
_VALUE = [
    ("Earnings yield", "earnings_yield_pct", _high, 0.0, 12.0, 0.40),
    ("P/E", "pe_ratio", _low, 5.0, 40.0, 0.35),
    ("P/B", "pb_ratio", _low, 0.5, 8.0, 0.25),
]
_QUALITY = [
    ("Return on equity", "roe_pct", _high, 0.0, 25.0, 0.25),
    ("Return on capital", "return_on_capital_pct", _high, 0.0, 20.0, 0.20),
    ("Net margin", "net_margin_pct", _high, 0.0, 25.0, 0.20),
    ("Return on assets", "roa_pct", _high, 0.0, 12.0, 0.15),
    ("Debt / equity", "debt_to_equity", _low, 0.0, 2.0, 0.10),
    ("Current ratio", "current_ratio", _high, 1.0, 3.0, 0.10),
]
_GROWTH = [
    ("Earnings CAGR 5y", "earnings_cagr_5y_pct", _high, 0.0, 25.0, 0.40),
    ("Earnings growth 5y", "earnings_growth_5y_pct", _high, 0.0, 100.0, 0.30),
    ("Revenue growth 5y", "revenue_growth_5y_pct", _high, 0.0, 60.0, 0.30),
]


def _component_score(metrics: dict, spec: list) -> Optional[dict]:
    comps, wsum, acc = [], 0.0, 0.0
    for label, key, scorer, lo, hi, weight in spec:
        pts = scorer(metrics.get(key), lo, hi)
        if pts is None:
            continue
        comps.append({"name": label, "metric": key,
                      "value": metrics.get(key), "points": pts, "weight": weight})
        wsum += weight
        acc += weight * pts
    if wsum == 0:
        return None
    return {"score": round(acc / wsum, 1), "components": comps}


def _grade(score: Optional[float]) -> Optional[str]:
    if score is None:
        return None
    if score >= 80:
        return "A"
    if score >= 65:
        return "B"
    if score >= 50:
        return "C"
    if score >= 35:
        return "D"
    return "F"


# Health blend leans on quality (Buffett-style durability) over raw cheapness.
_HEALTH_WEIGHTS = {"value": 0.30, "quality": 0.45, "growth": 0.25}


def overall_health(metrics: Optional[dict]) -> Optional[float]:
    """The blended 0–100 health score for a metric bundle, or ``None`` when
    nothing is measurable. Convenience wrapper over :func:`compute_scores`."""
    o = compute_scores(metrics).get("overall")
    return o["score"] if o else None


def compute_scores(metrics: Optional[dict]) -> dict:
    """Return {value, quality, growth, overall} composite scores (0–100).

    Each is ``{"score", "grade", "components"}`` or ``None`` when unmeasurable.
    ``overall`` blends the three present categories by ``_HEALTH_WEIGHTS``.
    """
    metrics = metrics or {}
    cats = {
        "value": _component_score(metrics, _VALUE),
        "quality": _component_score(metrics, _QUALITY),
        "growth": _component_score(metrics, _GROWTH),
    }
    wsum = acc = 0.0
    for name, cat in cats.items():
        if cat is None:
            continue
        w = _HEALTH_WEIGHTS[name]
        wsum += w
        acc += w * cat["score"]
    overall = round(acc / wsum, 1) if wsum else None

    out = {}
    for name, cat in cats.items():
        out[name] = None if cat is None else {**cat, "grade": _grade(cat["score"])}
    out["overall"] = (None if overall is None
                      else {"score": overall, "grade": _grade(overall)})
    return out
