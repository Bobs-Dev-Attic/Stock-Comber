"""Nightly "hidden gems" universe: a capped, sector-diversified, rotating pick.

The candidate pool is the curated seed (``seed_universe.py``) plus any tickers a
Finnhub-backed catalog has accumulated and any ``extra_tickers`` from settings.
Each night we (optionally) enrich a rotating batch of names via Finnhub (market
cap, sector, country, volume), filter by the configured gem profile, spread the
pick across sectors, cap the count, and rotate the window so coverage spreads
over days — so we hunt long-term value across industries and geographies without
re-screening every listed company nightly.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Optional

from .config import _deep_merge
from .seed_universe import SEED_UNIVERSE, seed_tickers

log = logging.getLogger("stock_comber.universe")


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
    return True


def _diversify(order: list[str], meta: dict, cap: int, n: dict) -> list[str]:
    """Pick up to `cap` tickers, spreading across sectors."""
    max_per = n.get("max_per_sector")
    if not max_per:
        max_per = max(1, math.ceil(cap / 6))
    selected, leftovers, counts = [], [], {}
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


def _candidates(config: dict, store) -> tuple[list[str], dict]:
    u = config.get("universe", {})
    meta: dict[str, dict] = {}
    # Seed hints first.
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
                  day_ordinal: int = 0) -> list[str]:
    """Return the capped, sector-diversified, rotated ticker list for tonight."""
    n = config.get("universe", {}).get("nightly", {})
    cap = int(n.get("cap", 75))
    cands, meta = _candidates(config, store)
    _enrich(cands, meta, n, finnhub, store, day_ordinal)

    eligible = sorted(t for t in cands if _passes(meta.get(t, {"ticker": t}), n))
    if not eligible:
        return []
    off = (day_ordinal * cap) % len(eligible)
    rotated = eligible[off:] + eligible[:off]
    return _diversify(rotated, meta, cap, n)
