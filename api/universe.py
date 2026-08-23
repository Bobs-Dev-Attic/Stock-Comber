"""Vercel serverless function: index universe templates.

  GET /api/universe                         -> available templates
  GET /api/universe?index=sp500&sector=...  -> a filtered slice of an index

Returns constituents of a bundled index template (Dow 30 / Nasdaq-100 / S&P 500)
filtered by sector, industry, market-cap band and volume, ranked by market cap.
Market cap / volume come from the stored universe catalog (Finnhub-enriched)
when available; sector + industry come from the bundled snapshot. Read-only,
no secrets.
"""

from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from stock_comber.indices import INDEXES, index_rows, SNAPSHOT_DATE  # noqa: E402
from stock_comber.storage import get_storage  # noqa: E402

MAX_LIMIT = 30


def build_nightly_preview(params) -> dict:
    """Preview the capped, diversified, rotated ticker pool the nightly
    'hidden gems' run will screen for a given day (defaults to today).

    Rotation depends only on the day ordinal, so the dashboard passes the next
    scheduled run's date. No Finnhub calls (finnhub=None) — uses the stored
    universe catalog + bundled seed, exactly like the hosted run's inputs.
    """
    import datetime
    from stock_comber.config import load_config
    from stock_comber.universe import build_nightly, effective_config

    store = get_storage()
    cfg = effective_config(load_config(), store)
    try:
        ordinal = int(params.get("ordinal", [""])[0])
    except (ValueError, TypeError):
        ordinal = datetime.date.today().toordinal()
    try:
        hour = min(23, max(0, int(params.get("hour", [""])[0])))
    except (ValueError, TypeError):
        hour = 0
    # Optional "remix" offset: re-draw a *different* stratified-random pool without
    # changing the run's date/hour. remix=0 (default) reproduces the exact pool the
    # next scheduled run will screen; remix>0 shifts the seed by a large prime so
    # each click yields a fresh, well-spread alternative draw (used by the dashboard's
    # 🎲 Remix button, e.g. to hand-screen a different set now).
    try:
        remix = max(0, int(params.get("remix", ["0"])[0]))
    except (ValueError, TypeError):
        remix = 0

    # Rotation advances hourly (see schedule.rotation_tick), so the preview seeds
    # the pool by the next run's date *and* hour to match what will actually run.
    tick = ordinal * 24 + hour + remix * 100003
    tickers = build_nightly(cfg, store, finnhub=None, day_ordinal=tick)

    catalog = {}
    if getattr(store, "enabled", False):
        try:
            catalog = {r["ticker"]: r for r in store.get_universe()}
        except Exception:
            catalog = {}
    rows = [{"ticker": t, "sector": (catalog.get(t) or {}).get("sector"),
             "market_cap": (catalog.get(t) or {}).get("market_cap")} for t in tickers]

    n = cfg.get("universe", {}).get("nightly", {})
    # Cooldown status: how many recently-screened names the nightly is holding
    # back (already excluded from `rows` by build_nightly).
    cooldown_days = int(n.get("reanalyze_cooldown_days", 0) or 0)
    on_cooldown: list = []
    if cooldown_days > 0 and getattr(store, "enabled", False):
        try:
            on_cooldown = sorted(store.recently_screened(cooldown_days))
        except Exception:
            on_cooldown = []
    return {
        "nightly": True,
        "ordinal": ordinal,
        "remix": remix,
        "date": datetime.date.fromordinal(ordinal).isoformat(),
        "cap": int(n.get("cap", 75)),
        "index": (cfg.get("universe", {}).get("index") or ""),
        "count": len(rows),
        "results": rows,
        "enriched": bool(catalog),
        "cooldown_days": cooldown_days,
        "on_cooldown_count": len(on_cooldown),
        "on_cooldown": on_cooldown[:60],   # a capped sample for display
    }


def _num(params, key):
    try:
        v = params.get(key, [""])[0]
        return float(v) if v not in ("", None) else None
    except (ValueError, TypeError):
        return None


def build_slice(params) -> dict:
    index = (params.get("index", [""])[0] or "").lower()
    if not index or index not in INDEXES:
        return {"templates": [{"key": k, "name": v["name"], "count": len(v["tickers"])}
                              for k, v in INDEXES.items()],
                "snapshot_date": SNAPSHOT_DATE}

    sector = (params.get("sector", [""])[0] or "").strip()
    industry = (params.get("industry", [""])[0] or "").strip()
    mc_min, mc_max = _num(params, "market_cap_min"), _num(params, "market_cap_max")
    vol_min = _num(params, "min_avg_volume")
    try:
        limit = min(MAX_LIMIT, max(1, int(params.get("limit", ["10"])[0])))
    except (ValueError, TypeError):
        limit = 10

    # Enrichment (market cap / volume) from the stored catalog, if any.
    catalog = {}
    store = get_storage()
    if getattr(store, "enabled", False):
        try:
            catalog = {r["ticker"]: r for r in store.get_universe()}
        except Exception:
            catalog = {}

    rows = []
    for ticker, gics_sector, gics_industry in index_rows(index):
        cat = catalog.get(ticker, {})
        mc = cat.get("market_cap")
        vol = cat.get("avg_volume")
        sec = cat.get("sector") or gics_sector
        if sector and sec != sector:
            continue
        if industry and gics_industry != industry:
            continue
        if mc is not None and mc_min is not None and mc < mc_min:
            continue
        if mc is not None and mc_max is not None and mc > mc_max:
            continue
        if vol is not None and vol_min is not None and vol < vol_min:
            continue
        rows.append({"ticker": ticker, "sector": sec, "industry": gics_industry,
                     "market_cap": mc, "avg_volume": vol})

    # Rank by market cap desc; unknown caps sort last but stay included.
    rows.sort(key=lambda r: (r["market_cap"] is None, -(r["market_cap"] or 0), r["ticker"]))
    return {
        "index": index, "name": INDEXES[index]["name"],
        "snapshot_date": SNAPSHOT_DATE,
        "total": len(rows), "count": min(limit, len(rows)),
        "results": rows[:limit],
        "sectors": sorted({r["sector"] for r in rows if r["sector"]}),
    }


from stock_comber.apiguard import guard  # noqa: E402


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        ok, _rl = guard(self, "universe")
        if not ok:
            self._send(429, {"error": "rate limit exceeded — slow down", **_rl})
            return
        params = parse_qs(urlparse(self.path).query)
        try:
            if params.get("nightly", [""])[0] in ("1", "true", "yes"):
                self._send(200, build_nightly_preview(params))
            else:
                self._send(200, build_slice(params))
        except Exception as exc:
            self._send(502, {"error": f"universe failed: {exc}"})

    def _send(self, code, obj):
        body = json.dumps(obj, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "public, max-age=300")
        self.end_headers()
        self.wfile.write(body)
