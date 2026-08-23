from stock_comber.config import load_config, validate_config
from stock_comber.seed_universe import seed_tickers
from stock_comber.universe import build_nightly, effective_config, _passes, _diversify


class FakeStore:
    enabled = True

    def __init__(self, universe=None, settings=None):
        self._u = universe or []
        self._s = settings or {}
        self.upserted = []

    def get_universe(self):
        return list(self._u)

    def upsert_universe(self, rows):
        self.upserted.extend(rows)
        self._u.extend(rows)

    def get_settings(self):
        return dict(self._s)


class FakeFinnhub:
    def __init__(self, profiles=None):
        self.profiles = profiles or {}
        self.calls = []

    def fetch_profile(self, ticker):
        self.calls.append(ticker)
        return self.profiles.get(ticker.upper(), {
            "name": ticker, "sector": "Technology", "country": "US",
            "market_cap": 5e9, "avg_volume": 500000,
        })


def _cfg(**nightly):
    c = load_config()
    c["universe"]["mode"] = "nightly"
    c["universe"]["nightly"].update(nightly)
    return c


def test_defaults_still_valid():
    assert validate_config(load_config()) == []


def test_build_nightly_caps_count():
    tickers = build_nightly(_cfg(cap=10), day_ordinal=1)
    assert len(tickers) == 10
    assert all(t.isupper() for t in tickers)


def test_build_nightly_without_store_uses_seed():
    tickers = build_nightly(_cfg(cap=200), day_ordinal=0)
    seed = set(seed_tickers())
    assert set(tickers).issubset(seed)
    assert len(tickers) == len(seed)  # cap exceeds pool → whole pool


def test_rotation_changes_window():
    cfg = _cfg(cap=10)
    day1 = build_nightly(cfg, day_ordinal=1)
    day2 = build_nightly(cfg, day_ordinal=2)
    assert day1 != day2  # different rotation offset


def test_market_cap_filter_excludes_out_of_band():
    store = FakeStore(universe=[
        {"ticker": "BIG", "sector": "Tech", "country": "US",
         "market_cap": 500e9, "avg_volume": 1e6},   # too big
        {"ticker": "GEM", "sector": "Tech", "country": "US",
         "market_cap": 2e9, "avg_volume": 1e6},      # in band
    ])
    cfg = _cfg(cap=100, include_unknown=False,
               market_cap_min=100e6, market_cap_max=20e9)
    tickers = build_nightly(cfg, store=store, day_ordinal=0)
    assert "GEM" in tickers and "BIG" not in tickers


def test_include_unknown_false_drops_unenriched():
    cfg = _cfg(cap=100, include_unknown=False, enrich_per_run=0)
    # No store/finnhub → seed names have no market_cap → all dropped.
    assert build_nightly(cfg, day_ordinal=0) == []


def test_enrich_calls_finnhub_and_upserts():
    fh = FakeFinnhub()
    store = FakeStore()
    build_nightly(_cfg(cap=5, enrich_per_run=5), store=store, finnhub=fh, day_ordinal=0)
    assert len(fh.calls) == 5
    assert len(store.upserted) == 5


def test_diversify_respects_max_per_sector():
    meta = {t: {"sector": "A"} for t in ["a", "b", "c", "d"]}
    meta["e"] = {"sector": "B"}
    out = _diversify(["a", "b", "c", "d", "e"], meta, cap=5, n={"max_per_sector": 2})
    # A capped at 2, then B, then backfill remaining A names.
    assert out[:3] == ["a", "b", "e"]
    assert set(out) == {"a", "b", "c", "d", "e"}


def test_passes_country_and_sector_filters():
    row = {"market_cap": 1e9, "avg_volume": 1e6, "country": "China", "sector": "Tech"}
    assert _passes(row, {"countries": ["China"], "market_cap_min": 0})
    assert not _passes(row, {"countries": ["US"], "market_cap_min": 0})
    assert not _passes(row, {"exclude_sectors": ["Tech"], "market_cap_min": 0})


def test_effective_config_merges_store_settings():
    store = FakeStore(settings={"graham": {"max_pe": 10.0}})
    merged = effective_config(load_config(), store)
    assert merged["graham"]["max_pe"] == 10.0
    assert merged["buffett"]["min_roe_pct"] == 15.0  # untouched


class FakeStoreCooldown(FakeStore):
    def __init__(self, universe=None, settings=None, recent=None):
        super().__init__(universe, settings)
        self._recent = set(recent or [])
        self.recent_days = None

    def recently_screened(self, days):
        self.recent_days = days
        return set(self._recent)


def test_nightly_skips_recently_scheduled_tickers():
    uni = [{"ticker": "AAA", "sector": "Tech", "country": "US", "market_cap": 2e9, "avg_volume": 1e6},
           {"ticker": "BBB", "sector": "Energy", "country": "US", "market_cap": 3e9, "avg_volume": 1e6}]
    cfg = _cfg(cap=50, reanalyze_cooldown_days=90, include_unknown=False,
               market_cap_min=1e8, market_cap_max=20e9)
    store = FakeStoreCooldown(universe=uni, recent={"AAA"})
    tickers = build_nightly(cfg, store=store, day_ordinal=0)
    assert "AAA" not in tickers and "BBB" in tickers
    assert store.recent_days == 90


def test_nightly_cooldown_disabled_when_zero():
    uni = [{"ticker": "AAA", "sector": "Tech", "country": "US", "market_cap": 2e9, "avg_volume": 1e6}]
    cfg = _cfg(cap=50, reanalyze_cooldown_days=0, include_unknown=False,
               market_cap_min=1e8, market_cap_max=20e9)
    store = FakeStoreCooldown(universe=uni, recent={"AAA"})
    tickers = build_nightly(cfg, store=store, day_ordinal=0)
    assert "AAA" in tickers                 # cooldown off -> not filtered
    assert store.recent_days is None        # never consulted


def test_nightly_cooldown_falls_back_when_all_on_cooldown():
    uni = [{"ticker": "AAA", "sector": "Tech", "country": "US", "market_cap": 2e9, "avg_volume": 1e6}]
    cfg = _cfg(cap=50, reanalyze_cooldown_days=90, include_unknown=False,
               market_cap_min=1e8, market_cap_max=20e9)
    # Everything eligible is on cooldown -> don't return an empty report.
    store = FakeStoreCooldown(universe=uni, recent={"AAA"})
    # Restrict the seed out by using an index-less cfg with only the catalog name.
    cfg["universe"]["extra_tickers"] = []
    tickers = build_nightly(cfg, store=store, day_ordinal=0)
    assert "AAA" in tickers                 # fallback keeps the pool non-empty


# -- stratified-random selection (v0.53.0) ---------------------------------
def _mk(sector, mc, vol):
    return {"sector": sector, "market_cap": mc, "avg_volume": vol}


def test_stratified_pick_spans_sectors_caps_and_volumes():
    from stock_comber.universe import _stratified_pick
    # 3 sectors × 3 cap tiers × 2 vol tiers, several names each.
    meta, elig = {}, []
    caps = {"small": 1e9, "mid": 5e9, "large": 15e9}
    vols = {"lo": 200_000, "hi": 3_000_000}
    for s in ("Tech", "Health", "Energy"):
        for cn, cv in caps.items():
            for vn, vv in vols.items():
                for i in range(3):
                    t = f"{s}{cn}{vn}{i}"
                    meta[t] = _mk(s, cv, vv); elig.append(t)
    pick = _stratified_pick(sorted(elig), meta, cap=18, n={}, seed=1)
    assert len(pick) == 18
    sectors = {meta[t]["sector"] for t in pick}
    cap_tiers = {("s" if meta[t]["market_cap"] < 2e9 else "l") for t in pick}
    vol_tiers = {("lo" if meta[t]["avg_volume"] < 5e5 else "hi") for t in pick}
    assert len(sectors) == 3          # spans all sectors
    assert len(cap_tiers) == 2        # spans small and large
    assert len(vol_tiers) == 2        # spans low and high volume


def test_stratified_pick_is_seed_reproducible_and_varies():
    from stock_comber.universe import _stratified_pick
    meta = {t: _mk("Tech", 5e9, 1e6) for t in (f"T{i}" for i in range(40))}
    elig = sorted(meta)
    a1 = _stratified_pick(elig, meta, cap=10, n={}, seed=7)
    a2 = _stratified_pick(elig, meta, cap=10, n={}, seed=7)
    b = _stratified_pick(elig, meta, cap=10, n={}, seed=8)
    assert a1 == a2                   # same seed → identical (preview reproduces run)
    assert a1 != b                    # different seed (next 6h) → different pick


def test_stratified_pick_prefers_classified_over_unknown():
    from stock_comber.universe import _stratified_pick
    meta = {"AAA": _mk("Tech", 5e9, 1e6), "BBB": _mk("Health", 3e9, 2e6)}
    meta.update({t: {"ticker": t} for t in ("U1", "U2", "U3")})  # unclassified
    pick = _stratified_pick(sorted(meta), meta, cap=2, n={}, seed=1)
    assert set(pick) == {"AAA", "BBB"}   # classified names fill the cap first


def test_build_nightly_spans_cap_tiers_when_enriched():
    store = FakeStore(universe=[
        {"ticker": "SM", "sector": "Tech", "country": "US", "market_cap": 1e9, "avg_volume": 1e6},
        {"ticker": "MD", "sector": "Tech", "country": "US", "market_cap": 5e9, "avg_volume": 1e6},
        {"ticker": "LG", "sector": "Tech", "country": "US", "market_cap": 15e9, "avg_volume": 1e6},
    ])
    cfg = _cfg(cap=3, include_unknown=False, market_cap_min=1e8, market_cap_max=20e9)
    tickers = build_nightly(cfg, store=store, day_ordinal=3)
    assert set(tickers) == {"SM", "MD", "LG"}   # one from each cap tier


def test_attach_sectors_sets_from_catalog():
    from stock_comber.universe import attach_sectors
    from stock_comber.models import ScreenResult
    store = FakeStore(universe=[
        {"ticker": "AAA", "sector": "Technology"},
        {"ticker": "BBB", "sector": "Health Care"},
    ])
    results = [
        ScreenResult(ticker="AAA", name="A", strategy="graham", passed=True, score=1, max_score=1),
        ScreenResult(ticker="BBB", name="B", strategy="graham", passed=False, score=0, max_score=1),
        ScreenResult(ticker="CCC", name="C", strategy="graham", passed=False, score=0, max_score=1),
    ]
    attach_sectors(results, store)
    assert results[0].sector == "Technology"
    assert results[1].sector == "Health Care"
    assert results[2].sector is None            # not in catalog → left unset
    assert results[0].to_dict()["sector"] == "Technology"   # flows into the report JSON


def test_attach_sectors_noop_without_store():
    from stock_comber.universe import attach_sectors
    from stock_comber.models import ScreenResult
    r = ScreenResult(ticker="AAA", name="A", strategy="graham", passed=True, score=1, max_score=1)
    attach_sectors([r], None)                   # no store → no error, no change
    assert r.sector is None
