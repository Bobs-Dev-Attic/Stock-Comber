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
