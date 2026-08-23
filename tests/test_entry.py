"""Value entry zone: anchor, signal nudges, band, vs-price, confidence."""

from stock_comber.entry import suggest_entry_zone
from stock_comber.models import AnnualFacts, Company, Quote

CFG = {"entry": {"enabled": True, "base_margin_of_safety": 0.25,
                 "min_margin_of_safety": 0.05, "max_margin_of_safety": 0.40}}


def _company(eps=5.0, bvps_equity=40.0, shares=1.0, price=100.0, volume=None):
    # graham = sqrt(22.5 * eps * (equity/shares)); with eps=5, bvps=40 → ~67.08
    a = AnnualFacts(fiscal_year=2025, eps=eps, stockholders_equity=bvps_equity,
                    shares_outstanding=shares)
    q = Quote(ticker="AAPL", price=price, volume=volume)
    return Company(ticker="AAPL", name="Apple", annuals=[a], quote=q)


def _bt(*edges):
    return {"strategies": {f"s{i}": {"summary": {"edge_pct": e}}
                           for i, e in enumerate(edges)}}


def test_unavailable_without_fair_value():
    # Negative EPS → no Graham number → no anchor.
    z = suggest_entry_zone(_company(eps=-2.0), None, None, CFG)
    assert z["available"] is False
    assert "Graham" in z["reason"]
    assert "not investment advice" in z["disclaimer"]


def test_basic_zone_orders_low_mid_high():
    z = suggest_entry_zone(_company(), None, None, CFG)
    assert z["available"] is True
    assert z["low"] < z["mid"] < z["high"]
    # No signals → base 25% MoS off ~67.08 fair value → mid ~50.3
    assert z["margin_of_safety_pct"] == 25.0
    assert round(z["fair_value"], 0) == 67.0
    assert z["confidence"] == "low"          # no signals used


def test_positive_edge_tightens_discount():
    base = suggest_entry_zone(_company(), None, None, CFG)["margin_of_safety_pct"]
    withedge = suggest_entry_zone(_company(), _bt(12.0), None, CFG)
    assert withedge["margin_of_safety_pct"] < base   # more confidence → less discount
    assert withedge["signals_used"] >= 1


def test_negative_edge_widens_discount():
    z = suggest_entry_zone(_company(), _bt(-10.0), None, CFG)
    assert z["margin_of_safety_pct"] > 25.0


def test_positive_sentiment_tightens_discount():
    s = {"score": 0.6, "grade": "A", "article_count": 8}
    z = suggest_entry_zone(_company(), None, s, CFG)
    assert z["margin_of_safety_pct"] < 25.0


def test_sentiment_ignored_without_articles():
    s = {"score": 0.6, "grade": "A", "article_count": 0}
    z = suggest_entry_zone(_company(), None, s, CFG)
    assert z["margin_of_safety_pct"] == 25.0   # no articles → no nudge


def test_volume_velocity_widens_band_and_discount():
    # avg volume from latest quote fallback == latest, so pass an enriched extra.
    c = _company(volume=3_000_000)
    c.extra = {"10DayAverageTradingVolume": 1.0}  # 1.0M avg → velocity 3.0
    z = suggest_entry_zone(c, None, None, CFG)
    # velocity = 3.0 → wider band than the 5% default and a wider discount.
    assert z["band_pct"] > 5.0
    assert z["margin_of_safety_pct"] > 25.0


def test_vs_price_classification():
    # Fair value ~67; base zone mid ~50, band 5% → ~[47.8, 52.8].
    assert suggest_entry_zone(_company(price=40.0), None, None, CFG)["vs_price"] == "below"
    assert suggest_entry_zone(_company(price=50.0), None, None, CFG)["vs_price"] == "within"
    assert suggest_entry_zone(_company(price=90.0), None, None, CFG)["vs_price"] == "above"


def test_margin_clamped_to_max():
    z = suggest_entry_zone(_company(), _bt(-100.0), None, CFG)  # huge negative edge
    assert z["margin_of_safety_pct"] <= 40.0


def test_confidence_scales_with_signals():
    s = {"score": 0.3, "grade": "B", "article_count": 5}
    c = _company(volume=2_000_000)
    c.extra = {"10DayAverageTradingVolume": 1.0}  # 1.0M avg → velocity 2.0
    z = suggest_entry_zone(c, _bt(5.0), s, CFG)
    assert z["signals_used"] == 3
    assert z["confidence"] == "high"


def test_disabled_returns_unavailable():
    z = suggest_entry_zone(_company(), None, None, {"entry": {"enabled": False}})
    assert z["available"] is False


def test_factors_are_transparent():
    z = suggest_entry_zone(_company(), _bt(8.0), None, CFG)
    names = [f["name"] for f in z["factors"]]
    assert "Fair value (Graham number)" in names
    assert "Base margin of safety" in names
    assert "Backtest edge" in names
