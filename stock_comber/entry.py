"""An illustrative *value entry zone* for a deep-dive analysis.

This is **not a price target and not investment advice.** It is a transparent,
deterministic reference range that shows where a classic value investor's
margin-of-safety discount would put an entry, and how a few observable signals
(the backtest edge, headline sentiment, and volume velocity) nudge that discount.
Every input and its effect is returned alongside the numbers so the range is
fully auditable — the app never emits an opaque "buy at $X".

Method (all knobs live under ``config.entry``):

1. **Anchor** on a value estimate — Graham's fair-value number
   ``sqrt(22.5 * EPS * BVPS)``. No Graham number (needs positive EPS *and* book
   value) → no zone; we say so rather than inventing one.
2. Start from a **base margin of safety** (default 25%) and nudge it, in
   percentage points, by:
   - **Backtest edge** — a stronger historical edge earns *less* required
     discount (more confidence); a weak/negative edge widens it.
   - **Sentiment** — positive headline tone trims the discount a little,
     negative widens it.
   - **Volume velocity** — unusually heavy recent volume (vs. the average) reads
     as elevated volatility/uncertainty, so it widens the discount and the band.
3. **Zone** = fair_value * (1 - margin), with a ± band whose width also grows
   with volume velocity. The result is clamped to a sane min/max discount.
"""

from __future__ import annotations

from typing import Any, Optional

from . import metrics
from .models import Company


def _clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x


def _mean_edge(backtest: Optional[dict]) -> Optional[float]:
    """Mean per-strategy ``edge_pct`` from a ``backtest_all`` payload, or None."""
    strat = (backtest or {}).get("strategies") or {}
    edges = [v.get("summary", {}).get("edge_pct")
             for v in strat.values() if isinstance(v, dict)]
    edges = [e for e in edges if e is not None]
    return sum(edges) / len(edges) if edges else None


def _volume_velocity(company: Company) -> Optional[float]:
    """Latest-day share volume ÷ average daily volume, or None.

    ~1.0 means today traded near normal; >1 is heavier-than-usual activity.
    Only meaningful when an average is known (Finnhub-enriched); otherwise the
    average falls back to the latest day and the ratio is a no-op 1.0.
    """
    avg = metrics.average_volume(company)
    latest = company.quote.volume if company.quote else None
    if avg and latest and avg > 0:
        return latest / avg
    return None


def suggest_entry_zone(
    company: Optional[Company],
    backtest: Optional[dict] = None,
    sentiment: Optional[dict] = None,
    cfg: Optional[dict] = None,
) -> dict:
    """Return the illustrative value entry zone (see module docstring).

    The result always includes ``available`` and ``disclaimer``. When
    ``available`` is False, ``reason`` explains why (and no numbers are given).
    """
    ecfg = (cfg or {}).get("entry", {})
    disclaimer = ("Illustrative value reference computed from public fundamentals "
                  "— not a price target and not investment advice.")
    out: dict[str, Any] = {"available": False, "disclaimer": disclaimer}
    if not ecfg.get("enabled", True):
        out["reason"] = "Entry zone is disabled in configuration."
        return out
    if company is None or company.latest is None:
        out["reason"] = "No fundamentals available for this ticker."
        return out

    fair_value = metrics.graham_number(company.latest)
    if fair_value is None or fair_value <= 0:
        out["reason"] = ("No Graham fair value (needs positive EPS and book "
                         "value per share), so no value anchor to discount.")
        return out

    price = company.quote.price if company.quote else None

    base = float(ecfg.get("base_margin_of_safety", 0.25))
    lo_mos = float(ecfg.get("min_margin_of_safety", 0.05))
    hi_mos = float(ecfg.get("max_margin_of_safety", 0.40))

    factors: list[dict[str, Any]] = [{
        "name": "Fair value (Graham number)",
        "detail": f"√(22.5 × EPS × BVPS) = {fair_value:,.2f}",
        "effect_pp": None,
    }, {
        "name": "Base margin of safety",
        "detail": f"{base * 100:.0f}% discount to fair value",
        "effect_pp": round(base * 100, 1),
    }]

    signals = 0

    # Backtest edge → confidence: more edge, less required discount.
    edge = _mean_edge(backtest)
    adj_edge = 0.0
    if edge is not None:
        signals += 1
        adj_edge = _clamp(-0.005 * edge, -0.10, 0.10)  # +12% edge → −6pp
        factors.append({
            "name": "Backtest edge",
            "detail": f"mean historical edge {edge:+.1f}% → "
                      f"{'tightens' if adj_edge < 0 else 'widens'} the discount",
            "effect_pp": round(adj_edge * 100, 1),
        })

    # Sentiment → positive tone trims the discount a little.
    adj_sent = 0.0
    score = (sentiment or {}).get("score")
    if score is not None and (sentiment or {}).get("article_count"):
        signals += 1
        adj_sent = _clamp(-0.10 * float(score), -0.08, 0.08)
        factors.append({
            "name": "News sentiment",
            "detail": f"score {float(score):+.2f} (grade "
                      f"{(sentiment or {}).get('grade', '—')}) → "
                      f"{'tightens' if adj_sent < 0 else 'widens'} the discount",
            "effect_pp": round(adj_sent * 100, 1),
        })

    # Volume velocity → heavy volume widens discount and band (more uncertainty).
    vel = _volume_velocity(company)
    adj_vol = 0.0
    band = 0.05
    if vel is not None and abs(vel - 1.0) > 1e-9:
        signals += 1
        adj_vol = _clamp(0.04 * (vel - 1.0), -0.03, 0.06)
        band = _clamp(0.03 + 0.02 * (vel - 1.0), 0.03, 0.10)
        factors.append({
            "name": "Volume velocity",
            "detail": f"latest volume {vel:.2f}× the average → "
                      f"{'widens' if adj_vol >= 0 else 'tightens'} the discount",
            "effect_pp": round(adj_vol * 100, 1),
        })

    mos = _clamp(base + adj_edge + adj_sent + adj_vol, lo_mos, hi_mos)
    mid = fair_value * (1.0 - mos)
    low = mid * (1.0 - band)
    high = mid * (1.0 + band)

    vs_price = None
    if price is not None:
        if price < low:
            vs_price = "below"      # already cheaper than the zone
        elif price > high:
            vs_price = "above"      # trading above the zone
        else:
            vs_price = "within"

    # Confidence from how many independent signals informed the nudge.
    confidence = "high" if signals >= 3 else "medium" if signals == 2 else "low"

    out.update({
        "available": True,
        "price": round(price, 2) if price is not None else None,
        "fair_value": round(fair_value, 2),
        "margin_of_safety_pct": round(mos * 100, 1),
        "band_pct": round(band * 100, 1),
        "low": round(low, 2),
        "mid": round(mid, 2),
        "high": round(high, 2),
        "vs_price": vs_price,
        "confidence": confidence,
        "signals_used": signals,
        "factors": factors,
    })
    return out
