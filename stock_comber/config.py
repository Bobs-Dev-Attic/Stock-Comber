"""Configuration loading and validation.

Every screening parameter is adjustable through a YAML config file so that
scheduled jobs can be tuned without touching code. ``DEFAULT_CONFIG`` documents
the full set of knobs and their defaults.
"""

from __future__ import annotations

import copy
import os
from typing import Any, Optional

try:  # PyYAML is an optional-at-import-time dependency
    import yaml
except Exception:  # pragma: no cover
    yaml = None  # type: ignore


DEFAULT_CONFIG: dict[str, Any] = {
    # Which strategies to run. Any subset of {"graham", "buffett"}.
    "strategies": ["graham", "buffett"],
    # Universe of tickers to comb through. If empty, the SEC ticker list is
    # used (optionally capped by universe.limit).
    "universe": {
        # "list": screen `tickers` (or the first `limit` SEC tickers).
        # "nightly": the capped, diversified "hidden gems" engine below.
        "mode": "list",
        "tickers": [],
        "limit": 500,  # cap when pulling the full SEC ticker list
        "exchanges": [],  # reserved for future filtering
        "extra_tickers": [],  # add your own names to the nightly candidate pool
        # Nightly "hidden gems" selection — capped, sector-diversified, rotating.
        "nightly": {
            "cap": 75,                       # stocks screened per night
            "market_cap_min": 100_000_000,   # $100M floor (skip tiny/illiquid)
            "market_cap_max": 20_000_000_000,  # $20B ceiling (skip mega-caps)
            "min_avg_volume": 100_000,       # shares/day liquidity floor
            "sectors": [],                   # empty = all industries
            "exclude_sectors": [],
            "countries": [],                 # empty = all (incl. international)
            "max_per_sector": 12,            # diversify: cap names per sector
            "enrich_per_run": 40,            # Finnhub profiles to fetch per night
            "include_unknown": True,         # screen not-yet-enriched names too
        },
    },
    # Data-source knobs.
    "data": {
        # SEC requires a descriptive User-Agent with a contact email.
        "user_agent": "Stock-Comber (bobchang711@gmail.com)",
        "cache_dir": ".cache/stock_comber",
        "cache_ttl_hours": 24,
        "request_timeout": 30,
        "request_delay_seconds": 0.2,  # be polite to free endpoints
        "min_annual_years": 3,  # need at least this many years of data
        # Optional Finnhub API key (or set FINNHUB_API_KEY). When present,
        # Finnhub enriches the universe (market cap / sector / country).
        "finnhub_api_key": None,
        # Seconds between Finnhub calls (free tier is ~60/min → ~1.1s).
        "finnhub_min_interval": 1.1,
        # Fetch Finnhub's metric bundle for every screened company (1 extra call
        # per ticker). Off by default to conserve the free-tier rate limit.
        "finnhub_enrich_results": False,
    },
    # Persistence. Leave dsn null to read DATABASE_URL/POSTGRES_URL from the
    # environment (e.g. a free Neon Postgres). Without any DSN, runs are not
    # stored and the app works exactly as before.
    "storage": {
        "dsn": None,
        "persist_runs": True,   # store each completed screen run
    },
    # Graham "defensive investor" thresholds. All adjustable.
    "graham": {
        "min_revenue": 700_000_000,       # adequate size
        "min_current_ratio": 2.0,         # strong financial condition
        "max_debt_to_equity": 1.0,        # debt not overwhelming equity
        "long_term_debt_under_working_capital": True,
        "positive_earnings_years": 5,     # earnings stability
        "require_dividend": False,         # dividend record (optional)
        "min_earnings_growth_pct": 33.0,  # cumulative over the window
        "earnings_growth_years": 5,
        "max_pe": 15.0,                   # moderate price/earnings
        "max_pb": 1.5,                    # moderate price/book
        "max_pe_times_pb": 22.5,          # Graham number ceiling
        "require_positive_book_value": True,
        # A company must pass at least this fraction of criteria to "pass".
        "pass_ratio": 0.8,
    },
    # Buffett quality/moat thresholds. All adjustable.
    "buffett": {
        "min_roe_pct": 15.0,
        "roe_consistency_years": 5,       # ROE above target for N years
        "max_debt_to_equity": 0.5,
        "min_net_margin_pct": 10.0,
        "min_earnings_growth_pct": 50.0,  # cumulative over the window
        "earnings_growth_years": 5,
        "require_positive_fcf": True,
        "min_fcf_years": 3,
        "pass_ratio": 0.8,
    },
    # User-defined custom criteria. Add rules of the form {metric} {op} {value};
    # include "custom" in `strategies` to run them. Metrics are the keys of the
    # computed metric bundle (see stock_comber/metrics.py METRIC_KEYS).
    "custom": {
        "pass_ratio": 1.0,   # by default every custom rule must pass
        "criteria": [
            # {"name": "Cheap", "metric": "pe_ratio", "op": "<=", "value": 12},
            # {"metric": "roe_pct", "op": ">=", "value": 20},
        ],
    },
    # Output/reporting knobs.
    "output": {
        "dir": "reports",
        "formats": ["json", "csv", "markdown"],  # any of json/csv/markdown/html
        "only_passing": False,   # include near-misses in reports
        "top_n": 50,             # cap rows in human-readable reports
        "sort_by": "score_pct",
    },
    # Scheduling knobs for local (APScheduler) runs. GitHub Actions uses its
    # own cron in .github/workflows/screen.yml.
    "schedule": {
        "enabled": False,
        "cron": "0 6 * * 1-5",   # 06:00 on weekdays
        "timezone": "UTC",
    },
}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge ``override`` into a copy of ``base``."""
    result = copy.deepcopy(base)
    for key, value in override.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def load_config(path: Optional[str] = None) -> dict[str, Any]:
    """Load config from ``path`` merged over :data:`DEFAULT_CONFIG`.

    Passing ``None`` returns the defaults. Missing files raise
    ``FileNotFoundError``; unreadable YAML raises the underlying parser error.
    """
    if path is None:
        return copy.deepcopy(DEFAULT_CONFIG)
    if not os.path.exists(path):
        raise FileNotFoundError(f"Config file not found: {path}")
    if yaml is None:  # pragma: no cover
        raise RuntimeError("PyYAML is required to load YAML config files")
    with open(path, "r", encoding="utf-8") as fh:
        user_cfg = yaml.safe_load(fh) or {}
    if not isinstance(user_cfg, dict):
        raise ValueError("Top-level config must be a mapping")
    return _deep_merge(DEFAULT_CONFIG, user_cfg)


def validate_config(cfg: dict[str, Any]) -> list[str]:
    """Return a list of human-readable problems (empty means valid)."""
    problems: list[str] = []
    valid_strategies = {"graham", "buffett", "custom"}
    strategies = cfg.get("strategies", [])
    if not strategies:
        problems.append("strategies must list at least one strategy")
    for s in strategies:
        if s not in valid_strategies:
            problems.append(f"unknown strategy: {s!r}")

    for strat in ("graham", "buffett", "custom"):
        pr = cfg.get(strat, {}).get("pass_ratio")
        if pr is not None and not (0.0 < pr <= 1.0):
            problems.append(f"{strat}.pass_ratio must be in (0, 1]")

    # Validate any custom criteria (lazy import avoids a cycle at module load).
    custom_criteria = cfg.get("custom", {}).get("criteria", [])
    if custom_criteria:
        from .criteria.custom import validate_criteria
        problems.extend(validate_criteria(custom_criteria))

    valid_formats = {"json", "csv", "markdown", "html"}
    for fmt in cfg.get("output", {}).get("formats", []):
        if fmt not in valid_formats:
            problems.append(f"unknown output format: {fmt!r}")

    limit = cfg.get("universe", {}).get("limit")
    if limit is not None and limit < 0:
        problems.append("universe.limit must be >= 0")
    return problems
