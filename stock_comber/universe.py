"""Nightly "hidden gems" universe: a capped, **seeded stratified-random** pick.

The candidate pool is the whole market — the full SEC ticker list (thousands of
names) plus the curated seed (``seed_universe.py``), any Finnhub-enriched catalog
rows, and ``extra_tickers`` from settings. Each run we (optionally) enrich a
rotating batch of names via Finnhub (market cap, sector, country, volume), filter
by the configured gem profile, then take a **stratified random sample** that spans
sectors × market-cap tiers × volume tiers. The sample is seeded by the run's
rotation ordinal, so it's different every run (e.g. every 6 hours) yet
reproducible for the dashboard's "next run" preview. Names not yet classified
(no sector/cap/volume) are used only as backfill and are steadily classified by
the rotating enrichment over time — so coverage grows toward the whole market
without re-screening every listed company each run.
"""

from __future__ import annotations

import logging
import math
import random
from typing import Any, Optional

from .config import _deep_merge
from .seed_universe import SEED_UNIVERSE, seed_tickers

log = logging.getLogger("stock_comber.universe")


def attach_sectors(results, store) -> None:
    """Set ``result.sector`` from the stored universe catalog (enrichment) for
    every result whose ticker is classified. One catalog read; a no-op without a
    database. Leaves ``sector`` as ``None`` for names the catalog doesn't know."""
    if not results or store is None or not getattr(store, "enabled", False):
        return
    try:
        catalog = {r["ticker"]: r for r in store.get_universe()}
    except Exception as exc:
        log.warning("could not load universe catalog for sectors: %s", exc)
        return
    for r in results:
        sec = (catalog.get(getattr(r, "ticker", None)) or {}).get("sector")
        if sec:
            r.sector = sec


def effective_config(base_cfg: dict, store=None) -> dict:
    """Deep-merge DB-stored settings over the file/default config."""
    if store is None:
        return base_cfg
    try:
        stored = store.get_settings() if getattr(store, "enabled", False) else {}
    except Exception as exc:  # settings must never break a run
        log.warning("could not load stored settings: %s", exc)
        stored = {}
    return _deep_merge(base_cfg, stored) if stored else base_cfg


def _passes(row: dict, n: dict) -> bool:
    mc = row.get("market_cap")
    if mc is not None:
        if mc < n.get("market_cap_min", 0):
            return False
        mx = n.get("market_cap_max")
        if mx and mc > mx:
            return False
    elif not n.get("include_unknown", True):
        return False

    vol = row.get("avg_volume")
    if vol is not None and vol < n.get("min_avg_volume", 0):
        return False

    countries = n.get("countries") or []
    if countries and row.get("country") and row["country"] not in countries:
        return False

    sectors = n.get("sectors") or []
    if sectors and row.get("sector") not in sectors:
        return False

    if row.get("sector") in (n.get("exclude_sectors") or []):
        return False

    industries = n.get("industries") or []
    if industries and row.get("industry") not in industries:
        return False
    return True


def _diversify(order: list[str], meta: dict, cap: int, n: dict) -> list[str]:
    """Pick up to `cap` tickers, spreading across sectors."""
    max_per = n.get("max_per_sector")
    if not max_per:
        max_per = max(1, math.ceil(cap / 6))
    selected: list = []
    leftovers: list = []
    counts: dict = {}
    for t in order:
        sector = (meta.get(t) or {}).get("sector") or "Unknown"
        if counts.get(sector, 0) < max_per:
            selected.append(t)
            counts[sector] = counts.get(sector, 0) + 1
        else:
            leftovers.append(t)
        if len(selected) >= cap:
            return selected[:cap]
    # Backfill if the per-sector cap left us short of the target count.
    for t in leftovers:
        if len(selected) >= cap:
            break
        selected.append(t)
    return selected[:cap]


def _tier(value: Optional[float], edges: list) -> Optional[int]:
    """Bucket a value into a tier index by the ascending ``edges`` (e.g. market-cap
    or volume bands). ``None`` (unknown) stays None so it doesn't fake a tier."""
    if value is None:
        return None
    for i, edge in enumerate(edges):
        if value < edge:
            return i
    return len(edges)


def _stratified_pick(eligible: list[str], meta: dict, cap: int, n: dict,
                     seed: int) -> list[str]:
    """Pick up to ``cap`` names as a **seeded stratified random** sample that spans
    sectors × market-cap tiers × volume tiers.

    Names are bucketed by (sector, mcap-tier, vol-tier); we round-robin across the
    buckets — so the pick spreads across every dimension we know — taking a
    seeded-random name from each. Names with no sector/cap/volume signal are used
    only as backfill. ``seed`` (the run's rotation ordinal) makes it deterministic
    so the dashboard preview reproduces the run, yet different every run.
    """
    mcap_edges = n.get("mcap_tier_edges") or [2_000_000_000, 10_000_000_000]
    vol_edges = n.get("volume_tier_edges") or [500_000, 2_000_000]
    rng = random.Random(seed)
    classified: dict = {}
    unclassified: list = []
    for t in eligible:                       # ``eligible`` is pre-sorted → stable
        m = meta.get(t) or {}
        sector = m.get("sector")
        mc_t = _tier(m.get("market_cap"), mcap_edges)
        vol_t = _tier(m.get("avg_volume"), vol_edges)
        if sector is None and mc_t is None and vol_t is None:
            unclassified.append(t)
        else:
            classified.setdefault((sector or "Unknown", mc_t, vol_t), []).append(t)
    keys = sorted(classified, key=lambda k: (str(k[0]), str(k[1]), str(k[2])))
    rng.shuffle(keys)
    for k in keys:
        rng.shuffle(classified[k])
    rng.shuffle(unclassified)
    picked: list = []
    active = [k for k in keys if classified[k]]
    while active and len(picked) < cap:       # round-robin one per bucket per pass
        for k in list(active):
            if not classified[k]:
                active.remove(k)
                continue
            picked.append(classified[k].pop())
            if len(picked) >= cap:
                break
    for t in unclassified:                    # backfill only if the cap isn't met
        if len(picked) >= cap:
            break
        picked.append(t)
    return picked[:cap]


def _candidates(config: dict, store, sec=None) -> tuple[list[str], dict]:
    u = config.get("universe", {})
    meta: dict[str, dict] = {}
    cands: list[str] = []
    # An index template (Dow / Nasdaq-100 / S&P 500), when chosen, is the seed
    # universe — its constituents carry sector + industry hints. Otherwise use
    # the curated diversified seed list.
    index = (u.get("index") or "").lower()
    if index:
        from .indices import index_rows
        for t, sector, industry in index_rows(index):
            meta[t] = {"ticker": t, "sector": sector or None,
                       "industry": industry or None, "country": "US"}
            cands.append(t)
    else:
        for t, sector, region in SEED_UNIVERSE:
            meta[t] = {"ticker": t, "sector": sector, "country": region}
        cands = list(seed_tickers())
    for t in u.get("extra_tickers", []) or []:
        cands.append(str(t).upper())
    if store is not None and getattr(store, "enabled", False):
        try:
            for row in store.get_universe():
                meta[row["ticker"]] = {**meta.get(row["ticker"], {}), **row}
                cands.append(row["ticker"])
        except Exception as exc:
            log.warning("could not load universe catalog: %s", exc)
    # Grow the pool to the whole market: add the full SEC ticker list (thousands
    # of names, unclassified until enrichment fills in sector/cap/volume). They
    # give the rotating enrichment a real backlog to work through and let the
    # nightly reach names beyond the curated seed. Only when a SEC source is
    # supplied (the real run) — the lightweight preview skips this fetch.
    n = u.get("nightly", {})
    if sec is not None and n.get("include_sec_universe", True):
        try:
            for t in sec.ticker_map().keys():
                up = str(t).upper()
                cands.append(up)
                meta.setdefault(up, {"ticker": up})
        except Exception as exc:
            log.warning("could not load SEC universe: %s", exc)
    # De-dup, preserve order, uppercase.
    seen, ordered = set(), []
    for t in (c.upper() for c in cands):
        if t not in seen:
            seen.add(t)
            ordered.append(t)
    return ordered, meta


def _enrich(cands: list[str], meta: dict, n: dict, finnhub, store,
            day_ordinal: int) -> None:
    budget = int(n.get("enrich_per_run", 40))
    if budget <= 0 or finnhub is None:
        return
    need = [t for t in cands if not (meta.get(t) or {}).get("market_cap")]
    if not need:
        return
    start = (day_ordinal * budget) % len(need)
    picks = (need[start:] + need[:start])[:budget]
    rows = []
    for t in picks:
        try:
            prof = finnhub.fetch_profile(t)
        except Exception as exc:
            log.warning("finnhub profile failed for %s: %s", t, exc)
            prof = None
        if prof:
            row = {"ticker": t, **{k: v for k, v in prof.items() if v is not None},
                   "source": "finnhub"}
            rows.append(row)
            meta[t] = {**meta.get(t, {}), **row}
    if store is not None and getattr(store, "enabled", False) and rows:
        try:
            store.upsert_universe(rows)
        except Exception as exc:
            log.warning("could not upsert universe rows: %s", exc)


def build_nightly(config: dict, store=None, finnhub=None,
                  day_ordinal: int = 0, sec=None) -> list[str]:
    """Return the capped ticker list for this run: a seeded **stratified random**
    sample spanning sectors × market-cap tiers × volume tiers, different every run.
    Pass ``sec`` (a SEC source) to widen the candidate pool to the whole market."""
    n = config.get("universe", {}).get("nightly", {})
    cap = int(n.get("cap", 75))
    cands, meta = _candidates(config, store, sec)
    _enrich(cands, meta, n, finnhub, store, day_ordinal)

    eligible = sorted(t for t in cands if _passes(meta.get(t, {"ticker": t}), n))

    # Don't let the scheduled report re-screen a name it already covered within
    # the cooldown window (manual analyses are exempt — see recently_screened).
    cooldown = int(n.get("reanalyze_cooldown_days", 0) or 0)
    if cooldown > 0 and store is not None and getattr(store, "enabled", False):
        recent = getattr(store, "recently_screened", None)
        if callable(recent):
            try:
                skip = recent(cooldown) or set()
                if skip:
                    filtered = [t for t in eligible if t not in skip]
                    # Never return an empty pool solely because everything is on
                    # cooldown — fall back to the unfiltered set in that edge case.
                    if filtered:
                        eligible = filtered
            except Exception as exc:
                log.warning("cooldown lookup failed: %s", exc)

    if not eligible:
        return []
    return _stratified_pick(eligible, meta, cap, n, day_ordinal)
