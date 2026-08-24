"""Fund X-ray — deconstruct a bundled ETF / mutual-fund snapshot into its top
holdings and score the fund against the selected strategies (fund-weighted),
plus diversity & balance metrics (sector spread, concentration).

Pure functions over already-screened result dicts (the shape from
``storage.list_all_results`` / ``api/screen.run_screen``): each has ``ticker``,
``strategy``, ``passed``, ``score_pct``, ``metrics`` and (sometimes) ``sector``.
No network — the caller reads the stored universe and passes the results in, so a
fund analysis never hits an upstream rate limit; holdings not yet screened come
back as ``pending`` for the caller to enqueue.

Bundled holdings are curated *top-holding* snapshots (weights as of
``SNAPSHOT_DATE``, expressed as fractions of the whole fund) — an educational
convenience, not a live holdings feed. They drift; refresh when needed. For a
fund not in the set the caller may pass explicit ``[{ticker, weight}]`` holdings.
"""

from __future__ import annotations

from typing import Any, Optional

from .indices import SP500
from .portfolio import holding_passes, holding_score, targets

SNAPSHOT_DATE = "2026-08-20"

WEAK_SCORE = 40.0        # a holding scoring below this is "low quality"
CONCENTRATED_TOP10 = 0.60   # top-10 weight above this reads as concentrated
SECTOR_HEAVY = 0.40      # a single sector above this reads as sector-heavy
GICS_SECTORS = 11        # the 11 GICS sectors — the diversification yardstick


def _num(v: Any) -> Optional[float]:
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


# ---- bundled snapshots -------------------------------------------------------
# Top holdings as (ticker, percent-of-fund). Percentages, not fractions, so the
# literals stay readable; _build() converts to fractions. Curated & approximate.

_SP500_TOP = [
    ("AAPL", 7.0), ("MSFT", 6.6), ("NVDA", 6.2), ("AMZN", 3.8), ("META", 2.5),
    ("GOOGL", 2.0), ("GOOG", 1.7), ("BRK.B", 1.7), ("AVGO", 1.6), ("TSLA", 1.5),
    ("LLY", 1.4), ("JPM", 1.3), ("V", 1.2), ("UNH", 1.1), ("XOM", 1.1),
]
_QQQ_TOP = [
    ("AAPL", 8.8), ("MSFT", 8.2), ("NVDA", 7.8), ("AMZN", 5.5), ("AVGO", 5.0),
    ("META", 4.8), ("TSLA", 3.0), ("COST", 2.6), ("NFLX", 2.9), ("GOOGL", 2.5),
    ("GOOG", 2.4), ("TMUS", 1.6), ("PEP", 1.5), ("ADBE", 1.3), ("AMD", 1.3),
]
_SCHD_TOP = [
    ("ABBV", 4.3), ("AVGO", 4.3), ("HD", 4.2), ("KO", 4.1), ("PEP", 4.0),
    ("CVX", 4.0), ("VZ", 4.0), ("TXN", 3.9), ("CSCO", 3.9), ("AMGN", 3.9),
    ("MRK", 3.8), ("PFE", 3.5), ("LMT", 3.0), ("BLK", 3.0), ("UPS", 2.5),
]
_DIA_TOP = [
    ("GS", 8.5), ("UNH", 6.5), ("MSFT", 6.5), ("HD", 6.0), ("CAT", 6.0),
    ("V", 4.5), ("CRM", 4.5), ("MCD", 4.5), ("AXP", 4.0), ("AMGN", 4.0),
    ("IBM", 3.5), ("AAPL", 3.5), ("TRV", 3.5), ("HON", 3.0), ("JPM", 3.0),
]
_VUG_TOP = [
    ("AAPL", 12.0), ("MSFT", 11.0), ("NVDA", 10.0), ("AMZN", 7.0), ("AVGO", 4.0),
    ("META", 4.5), ("GOOGL", 3.8), ("GOOG", 3.3), ("TSLA", 2.8), ("LLY", 3.0),
    ("V", 2.0), ("COST", 2.0), ("MA", 1.8), ("HD", 1.8), ("NFLX", 1.5),
]
_VTV_TOP = [
    ("BRK.B", 3.2), ("JPM", 3.0), ("XOM", 2.6), ("UNH", 2.4), ("JNJ", 2.2),
    ("PG", 2.0), ("HD", 2.0), ("ABBV", 1.9), ("WMT", 1.8), ("BAC", 1.6),
    ("KO", 1.5), ("CVX", 1.5), ("MRK", 1.4), ("WFC", 1.3), ("CSCO", 1.3),
]
_VYM_TOP = [
    ("JPM", 3.5), ("XOM", 3.2), ("AVGO", 3.0), ("JNJ", 2.6), ("PG", 2.5),
    ("HD", 2.4), ("ABBV", 2.2), ("WMT", 2.0), ("BAC", 1.9), ("KO", 1.8),
    ("CVX", 1.8), ("MRK", 1.6), ("PEP", 1.6), ("WFC", 1.5), ("CSCO", 1.4),
]

# symbol -> (name, category, top-holdings). SPY/VOO/IVV/VTI track the S&P 500 (or
# near enough at the top) so they share the S&P snapshot.
_RAW_FUNDS: dict[str, tuple[str, str, list[tuple[str, float]]]] = {
    "SPY": ("SPDR S&P 500 ETF", "US large-cap blend", _SP500_TOP),
    "VOO": ("Vanguard S&P 500 ETF", "US large-cap blend", _SP500_TOP),
    "IVV": ("iShares Core S&P 500 ETF", "US large-cap blend", _SP500_TOP),
    "VTI": ("Vanguard Total Stock Market ETF", "US total market", _SP500_TOP),
    "QQQ": ("Invesco QQQ Trust (Nasdaq-100)", "US large-cap growth", _QQQ_TOP),
    "SCHD": ("Schwab US Dividend Equity ETF", "US large-cap value / dividend", _SCHD_TOP),
    "DIA": ("SPDR Dow Jones Industrial Average ETF", "US large-cap blend (price-weighted)", _DIA_TOP),
    "VUG": ("Vanguard Growth ETF", "US large-cap growth", _VUG_TOP),
    "VTV": ("Vanguard Value ETF", "US large-cap value", _VTV_TOP),
    "VYM": ("Vanguard High Dividend Yield ETF", "US large-cap value / dividend", _VYM_TOP),
}


def _build(top: list[tuple[str, float]]) -> list[dict]:
    return [{"ticker": t, "weight": round(pct / 100.0, 4)} for t, pct in top]


def list_funds() -> list[dict]:
    """The bundled fund catalog: symbol, name, category, holding count and the
    total weight the top-holdings snapshot covers."""
    out = []
    for sym, (name, cat, top) in _RAW_FUNDS.items():
        cov = round(sum(pct for _, pct in top) / 100.0, 4)
        out.append({"symbol": sym, "name": name, "category": cat,
                    "holdings_count": len(top), "coverage": cov})
    out.sort(key=lambda f: str(f["symbol"]))
    return out


def get_fund(symbol: str) -> Optional[dict]:
    """Bundled snapshot for a fund symbol, or ``None`` if not in the set."""
    rec = _RAW_FUNDS.get((symbol or "").strip().upper())
    if not rec:
        return None
    name, cat, top = rec
    return {"symbol": symbol.strip().upper(), "name": name, "category": cat,
            "snapshot": SNAPSHOT_DATE, "holdings": _build(top)}


# ---- analysis ----------------------------------------------------------------

def _sector_for(ticker: str, results: list[dict]) -> Optional[str]:
    """Sector from the screened result if present, else the bundled GICS map."""
    for r in results:
        if r.get("ticker") == ticker:
            sec = r.get("sector") or (r.get("metrics") or {}).get("sector")
            if sec:
                return sec
    sp = SP500.get(ticker)
    return sp[0] if sp else None


def _hhi(weights: list[float]) -> float:
    """Herfindahl-Hirschman index over weights normalized to sum 1 (0..1)."""
    tot = sum(weights)
    if tot <= 0:
        return 0.0
    return sum((w / tot) ** 2 for w in weights)


def _effective_n(weights: list[float]) -> float:
    h = _hhi(weights)
    return (1.0 / h) if h > 0 else 0.0


def _grade(score: Optional[float]) -> str:
    if score is None:
        return "n/a"
    if score >= 85:
        return "A"
    if score >= 70:
        return "B"
    if score >= 55:
        return "C"
    if score >= 40:
        return "D"
    return "F"


def _suggestions(rows: list[dict], sectors: dict[str, float], top10: float,
                 coverage: float, pending: list[str]) -> list[dict]:
    out: list[dict] = []
    if top10 >= CONCENTRATED_TOP10:
        out.append({"type": "concentration",
                    "message": f"The top 10 holdings are {top10 * 100:.0f}% of the snapshot — "
                               "concentrated; a stumble in the megacaps moves the whole fund."})
    heavy = sorted(((s, w) for s, w in sectors.items() if s != "Unknown" and w >= SECTOR_HEAVY),
                   key=lambda x: -x[1])
    for sec, w in heavy:
        out.append({"type": "sector",
                    "message": f"{sec} is {w * 100:.0f}% of the snapshot — sector-heavy; "
                               "returns will track that sector closely."})
    covered = [r for r in rows if r["score"] is not None]
    weak = [r["ticker"] for r in covered if (r["score"] or 0) < WEAK_SCORE]
    if covered and len(weak) >= max(1, len(covered) // 3):
        out.append({"type": "quality",
                    "message": f"{len(weak)} of {len(covered)} scored holdings look weak on the "
                               "selected strategies — the fund tilts away from classic value/quality."})
    if pending:
        shown = ", ".join(pending[:8]) + ("…" if len(pending) > 8 else "")
        out.append({"type": "coverage",
                    "message": f"{len(pending)} holding(s) aren't screened yet ({shown}); queue them "
                               f"to raise coverage above the current {coverage * 100:.0f}%."})
    if not out:
        out.append({"type": "ok",
                    "message": "No major concentration, sector or quality flags in the snapshot — "
                               "reasonably balanced for its category."})
    return out


def analyze_fund(holdings: list[dict], results: list[dict],
                 strategies: Optional[list[str]] = None,
                 meta: Optional[dict] = None) -> dict:
    """Deconstruct a fund's holdings and score it fund-weighted against the
    strategies, with diversity/balance metrics and an overall 0–100 score.

    ``holdings``: ``[{ticker, weight}]`` (weight a fraction of the whole fund;
    top-holdings snapshots need not sum to 1). ``results``: the stored screened
    universe. Returns per-holding rows, sector breakdown, concentration stats,
    coverage, an overall score/grade and suggestions.
    """
    strategies = [s for s in (strategies or []) if s]
    rows: list[dict] = []
    seen: set[str] = set()
    for h in holdings:
        ticker = str((h or {}).get("ticker", "")).strip().upper()
        weight = _num((h or {}).get("weight")) or 0.0
        if not ticker or ticker in seen:
            continue
        seen.add(ticker)
        score = holding_score(ticker, results, strategies)
        metrics: dict = {}
        for r in results:
            if r.get("ticker") == ticker and r.get("metrics"):
                metrics = r["metrics"] or {}
                break
        tgt = targets(metrics.get("price"), metrics.get("graham_number"))
        rows.append({
            "ticker": ticker, "weight": round(weight, 4), "score": score,
            "passing": holding_passes(ticker, results, strategies),
            "sector": _sector_for(ticker, results), "verdict": tgt["verdict"],
            "covered": score is not None,
        })

    total_w = sum(r["weight"] for r in rows)
    pending = [r["ticker"] for r in rows if not r["covered"]]

    # Fund-weighted quality score over the covered holdings.
    cov_rows = [r for r in rows if r["score"] is not None]
    cov_w = sum(r["weight"] for r in cov_rows)
    if cov_w > 0:
        quality: Optional[float] = round(sum(r["weight"] * r["score"] for r in cov_rows) / cov_w, 1)
    elif cov_rows:
        quality = round(sum(r["score"] for r in cov_rows) / len(cov_rows), 1)
    else:
        quality = None
    coverage = round(cov_w / total_w, 4) if total_w else 0.0

    # Sector breakdown (fraction of the snapshot's weight per sector).
    sectors: dict[str, float] = {}
    for r in rows:
        sec = r["sector"] or "Unknown"
        sectors[sec] = sectors.get(sec, 0.0) + r["weight"]
    if total_w > 0:
        sectors = {s: round(w / total_w, 4) for s, w in sectors.items()}
    sectors_sorted = dict(sorted(sectors.items(), key=lambda x: -x[1]))
    known = {s: w for s, w in sectors_sorted.items() if s != "Unknown"}
    top_sector, top_sector_w = (next(iter(known.items())) if known else ("Unknown", 0.0))

    # Concentration / evenness.
    weights = [r["weight"] for r in rows]
    by_w = sorted(weights, reverse=True)
    tw = sum(weights) or 1.0
    top10 = round(sum(by_w[:10]) / tw, 4)
    eff_n = _effective_n(weights)
    name_even = min(1.0, eff_n / len(rows)) if rows else 0.0
    eff_sectors = _effective_n(list(known.values())) if known else 0.0
    sector_even = min(1.0, eff_sectors / GICS_SECTORS)
    diversification = round(100 * (0.5 * name_even + 0.5 * sector_even), 1)

    # Overall: blend fund-weighted quality with diversification; when nothing is
    # screened yet, fall back to diversification alone (and flag low coverage).
    if quality is not None:
        overall: Optional[float] = round(0.65 * quality + 0.35 * diversification, 1)
    elif rows:
        overall = diversification
    else:
        overall = None

    return {
        "symbol": (meta or {}).get("symbol", ""),
        "name": (meta or {}).get("name", ""),
        "category": (meta or {}).get("category", ""),
        "snapshot": (meta or {}).get("snapshot", SNAPSHOT_DATE),
        "holdings": rows,
        "count": len(rows),
        "snapshot_weight": round(total_w, 4),
        "coverage": coverage,
        "covered_count": len(cov_rows),
        "pending": pending,
        "quality_score": quality,
        "diversification_score": diversification,
        "score": overall,
        "grade": _grade(overall),
        "passing": sum(1 for r in rows if r["passing"]),
        "sectors": sectors_sorted,
        "sector_count": len(known),
        "top_sector": top_sector,
        "top_sector_weight": top_sector_w,
        "top10_weight": top10,
        "effective_holdings": round(eff_n, 1),
        "effective_sectors": round(eff_sectors, 1),
        "suggestions": _suggestions(rows, known, top10, coverage, pending),
        "strategies": strategies,
    }
