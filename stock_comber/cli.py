"""Command-line interface for Stock-Comber."""

from __future__ import annotations

import argparse
import json
import logging
import random
import sys
from typing import Optional

from . import __version__
from .config import DEFAULT_CONFIG, load_config, validate_config
from .report import to_markdown, write_reports
from .screener import Screener


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="stock-comber",
        description="Find publicly traded companies that fit Graham/Buffett value criteria.",
    )
    p.add_argument("--version", action="version", version=f"stock-comber {__version__}")
    p.add_argument("-c", "--config", help="Path to a YAML config file.")
    p.add_argument("-v", "--verbose", action="store_true", help="Verbose logging.")
    sub = p.add_subparsers(dest="command", required=True)

    ps = sub.add_parser("screen", help="Run the screen over the universe.")
    # Accept --verbose after the subcommand too (argparse otherwise only allows
    # the global flag before it). SUPPRESS keeps it from resetting the global
    # value when omitted, so both orderings work.
    ps.add_argument("-v", "--verbose", action="store_true",
                    default=argparse.SUPPRESS, help="Verbose logging.")
    ps.add_argument("tickers", nargs="*", help="Explicit tickers (overrides config universe).")
    ps.add_argument("--limit", type=int, help="Cap the SEC ticker universe.")
    ps.add_argument("--nightly", action="store_true",
                    help="Use the capped, diversified 'hidden gems' universe.")
    ps.add_argument("--strategy", action="append",
                    choices=["graham", "buffett", "custom", "piotroski",
                             "greenblatt", "lynch", "netnet"],
                    help="Restrict to specific strategies (repeatable).")
    ps.add_argument("--only-passing", action="store_true", help="Report only passing rows.")
    ps.add_argument("--no-write", action="store_true", help="Print to stdout, don't write files.")

    sub.add_parser("config", help="Print the effective configuration and exit.")
    sub.add_parser("validate", help="Validate the configuration and exit.")

    pt = sub.add_parser("tickers", help="List available tickers from SEC EDGAR.")
    pt.add_argument("--limit", type=int, default=50)

    psch = sub.add_parser("schedule", help="Run the screen on a recurring local schedule.")
    psch.add_argument("--once", action="store_true", help="Run one cycle then exit.")

    sub.add_parser(
        "schedule-gate",
        help="Decide whether the stored schedule says the hosted run should fire "
             "now (for the hourly GitHub Actions heartbeat).")

    paq = sub.add_parser("analyze-queue",
                         help="Process queued tickers with a full analysis (news + sentiment).")
    paq.add_argument("--limit", type=int, default=5, help="Max tickers to process.")
    paq.add_argument("--seed", help="Comma-separated tickers to enqueue first (analyse on demand).")
    paq.add_argument("--reseed-strategy",
                     help="Enqueue every ticker currently on this strategy (e.g. 'custom') "
                          "for a fresh full analysis.")

    pct = sub.add_parser("check-theses",
                         help="Re-check stored investment theses against fresh metrics.")
    pct.add_argument("--limit", type=int, default=100, help="Max theses to check.")

    sub.add_parser("run-jobs",
                   help="Run every saved custom job (from the dashboard) and store each "
                        "as its own run. Used by the scheduled workflow.")

    pp = sub.add_parser("purge-strategy",
                        help="Permanently delete all stored results for a strategy.")
    pp.add_argument("--strategy", required=True,
                    help="Strategy whose results to delete (e.g. 'custom').")
    pp.add_argument("--yes", action="store_true",
                    help="Confirm the destructive purge (required).")
    return p


def _load(args) -> dict:
    cfg = load_config(args.config)
    # Merge any DB-stored settings (from the settings page) over the file config.
    from .storage import get_storage
    from .universe import effective_config
    cfg = effective_config(cfg, get_storage(cfg))
    if getattr(args, "limit", None) is not None:
        cfg["universe"]["limit"] = args.limit
    if getattr(args, "nightly", False):
        cfg["universe"]["mode"] = "nightly"
        # Rank the nightly "hidden gems" by composite health, unless the user
        # explicitly chose another sort.
        out = cfg.setdefault("output", {})
        if out.get("sort_by", "score_pct") == "score_pct":
            out["sort_by"] = "health"
    if getattr(args, "strategy", None):
        cfg["strategies"] = args.strategy
    if getattr(args, "only_passing", False):
        cfg["output"]["only_passing"] = True
    return cfg


def _progress(i: int, total: int, ticker: str) -> None:
    print(f"  [{i}/{total}] {ticker}", file=sys.stderr)


def _attach_backtest_edge(results, screener, cfg) -> None:
    """Inject a per-name ``backtest_edge_pct`` into each result's metrics (nightly
    report). One year-end price-history fetch per distinct ticker; the fetches run
    on a small bounded thread pool (``data.backtest_fetch_workers``) so the nightly
    run isn't serialised on network latency. Failures are skipped so they never
    sink the run."""
    import threading
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from .backtest import overall_edge
    from .datasources import make_history_source
    data = cfg.get("data", {})
    cache = getattr(screener.sec, "cache", None)
    timeout = data.get("request_timeout", 25)
    delay = data.get("request_delay_seconds", 0.0)
    # The history source (Tiingo when a key is set, else Yahoo) owns a
    # requests.Session that is not guaranteed thread-safe, so each worker thread
    # gets its own — created lazily and reused within that thread. The file cache
    # is safe to share (distinct tickers → distinct keys).
    _local = threading.local()

    def _hist():
        h = getattr(_local, "hist", None)
        if h is None:
            h = make_history_source(cfg, cache=cache, timeout=timeout, delay=delay)
            _local.hist = h
        return h

    # Only names we actually have fundamentals for can be backtested.
    todo = [t for t in sorted({r.ticker for r in results})
            if getattr(screener.last_companies.get(t), "annuals", None)]
    if not todo:
        return
    try:
        workers = int(data.get("backtest_fetch_workers", 4))
    except (TypeError, ValueError):
        workers = 4
    workers = max(1, min(workers, 16, len(todo)))

    def _fetch(t):
        try:
            return t, _hist().fetch_history(t, years=10), None
        except Exception as exc:  # isolate a single ticker's failure
            return t, None, exc

    edges: dict[str, float] = {}

    def _record(t, hist, err, i):
        if err is not None:
            print(f"  backtest edge failed for {t}: {err}", file=sys.stderr)
        else:
            company = screener.last_companies.get(t)
            edge = overall_edge(company, hist, cfg) if hist else None
            if edge is not None:
                edges[t] = edge
        print(f"  backtest {i}/{len(todo)} {t}", file=sys.stderr)

    if workers == 1:
        for i, t in enumerate(todo, 1):
            tt, hist, err = _fetch(t)
            _record(tt, hist, err, i)
    else:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_fetch, t): t for t in todo}
            for i, fut in enumerate(as_completed(futures), 1):
                tt, hist, err = fut.result()
                _record(tt, hist, err, i)

    for r in results:
        e = edges.get(r.ticker)
        if e is not None and r.metrics is not None:
            r.metrics["backtest_edge_pct"] = e


def cmd_screen(args) -> int:
    cfg = _load(args)
    problems = validate_config(cfg)
    if problems:
        print("Invalid configuration:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 2
    from .storage import get_storage
    store = get_storage(cfg)
    screener = Screener(cfg)
    screener.store = store  # share store for the nightly universe/rotation
    tickers = [t.upper() for t in args.tickers] or None
    results = screener.run(tickers, progress=_progress)

    # Tag each result with its sector from the universe catalog so the report
    # (and the Full list) can show a Sector column.
    from .universe import attach_sectors
    attach_sectors(results, store)

    # For the nightly "hidden gems" report, attach a per-name backtest edge so it
    # shows alongside the fundamentals (one extra price-history fetch per name).
    if (cfg.get("universe", {}).get("mode") == "nightly"
            and cfg.get("data", {}).get("backtest_in_nightly", True)):
        _attach_backtest_edge(results, screener, cfg)

    # Persist the run when a database is configured.
    if cfg.get("storage", {}).get("persist_runs", True):
        if getattr(store, "enabled", False):
            try:
                # Tag nightly runs as the scheduled report so the catch-up gate
                # can tell them from manual analyses (see schedule.should_run_now).
                is_scheduled = cfg.get("universe", {}).get("mode") == "nightly"
                run_meta: dict = {"universe": len({r.ticker for r in results})}
                if is_scheduled:
                    run_meta["source"] = "schedule"
                run_id = store.save_run(
                    results, screener.last_companies, meta=run_meta,
                )
                print(f"Stored run #{run_id} in the database.")
            except Exception as exc:  # persistence must never fail the screen
                print(f"Warning: could not store run: {exc}", file=sys.stderr)

    # The heavy Company objects (annuals, quotes, raw payloads) are no longer
    # needed once the run is persisted and the edge attached — release them so
    # report rendering doesn't hold them alongside the results.
    screener.last_companies = {}

    if args.no_write:
        print(to_markdown(results, cfg))
    else:
        paths = write_reports(results, cfg)
        passing = sum(1 for r in results if r.passed)
        print(f"Screened {len({r.ticker for r in results})} companies · "
              f"{passing} strategy matches passed.")
        print("Wrote:")
        for path in paths:
            print(f"  {path}")
    return 0


def cmd_config(args) -> int:
    print(json.dumps(load_config(args.config), indent=2))
    return 0


def cmd_validate(args) -> int:
    cfg = load_config(args.config)
    problems = validate_config(cfg)
    if problems:
        for p in problems:
            print(f"  - {p}")
        return 1
    print("Configuration OK.")
    return 0


def cmd_tickers(args) -> int:
    cfg = load_config(args.config)
    screener = Screener(cfg)
    for t in screener.sec.list_tickers(limit=args.limit):
        print(t)
    return 0


def cmd_schedule(args) -> int:
    from .scheduler import run_schedule
    cfg = _load(args)
    return run_schedule(cfg, once=args.once)


def cmd_schedule_gate(args) -> int:
    """Print (and export to $GITHUB_OUTPUT) whether the hosted run should fire
    now, per the schedule stored in the database. Exit code is always 0 so the
    workflow can branch on the ``run`` output rather than on failure."""
    import datetime
    import os
    from .schedule import should_run_now
    from .storage import get_storage
    cfg = load_config(args.config)
    store = get_storage(cfg)
    try:
        stored = store.get_settings() or {}
    except Exception as exc:  # never fail the gate on a DB hiccup
        print(f"schedule-gate: could not read settings ({exc}); using default",
              file=sys.stderr)
        stored = {}
    # The last scheduled run de-duplicates catch-up: a slot fires only once even
    # when the heartbeat that triggers it is (as GitHub often is) minutes late.
    try:
        last_run = store.last_scheduled_run_at()
    except Exception as exc:
        print(f"schedule-gate: could not read last run ({exc}); assuming none",
              file=sys.stderr)
        last_run = None
    now = datetime.datetime.now(datetime.timezone.utc)
    run, reason = should_run_now(stored, now, last_run)
    print(f"schedule-gate: run={str(run).lower()} — {reason}")
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as fh:
            fh.write(f"run={'true' if run else 'false'}\n")
    return 0


def cmd_analyze_queue(args) -> int:
    from .analysis import process_queue
    from .storage import get_storage
    cfg = _load(args)
    store = get_storage(cfg)
    if not getattr(store, "enabled", False):
        print("No database configured (set DATABASE_URL); nothing to process.",
              file=sys.stderr)
        return 0
    limit = args.limit
    if getattr(args, "seed", None):
        seed = [t.strip().upper() for t in args.seed.split(",") if t.strip()]
        if seed:
            store.enqueue(seed)
            print(f"Seeded {len(seed)} ticker(s) into the queue.")
            limit = max(limit, len(seed))
    reseed = getattr(args, "reseed_strategy", None)
    if reseed:
        stale = store.tickers_with_strategy(reseed.strip())
        if stale:
            store.enqueue(stale)
            print(f"Re-seeded {len(stale)} ticker(s) currently on the "
                  f"{reseed!r} strategy into the queue.")
            limit = max(limit, len(stale))
        else:
            print(f"No tickers found on the {reseed!r} strategy.")
    summary = process_queue(cfg, store, limit=limit)
    print(f"Processed {summary.get('processed', 0)} queued ticker(s).")
    for item in summary.get("tickers", []):
        if "error" in item:
            print(f"  {item['ticker']}: error — {item['error']}")
        else:
            print(f"  {item['ticker']}: analysed → run #{item['run_id']}")
    return 0


def cmd_purge_strategy(args) -> int:
    from .storage import get_storage
    cfg = _load(args)
    store = get_storage(cfg)
    if not getattr(store, "enabled", False):
        print("No database configured (set DATABASE_URL); nothing to purge.",
              file=sys.stderr)
        return 0
    strat = (args.strategy or "").strip()
    if not strat:
        print("Provide --strategy NAME.", file=sys.stderr)
        return 2
    if not getattr(args, "yes", False):
        print(f"Refusing to purge {strat!r} results without --yes.", file=sys.stderr)
        return 2
    out = store.delete_results_by_strategy(strat)
    print(f"Purged {out['results_deleted']} {strat!r} result(s); "
          f"removed {out['empty_runs_deleted']} now-empty run(s).")
    return 0


def cmd_check_theses(args) -> int:
    from .thesis import check_theses
    from .storage import get_storage
    cfg = _load(args)
    store = get_storage(cfg)
    if not getattr(store, "enabled", False):
        print("No database configured (set DATABASE_URL); no theses to check.",
              file=sys.stderr)
        return 0
    screener = Screener(cfg)
    screener.store = store
    summary = check_theses(store, screener, limit=args.limit)
    print(f"Checked {summary.get('checked', 0)} thesis(es).")
    for item in summary.get("theses", []):
        if "error" in item:
            print(f"  #{item['id']} {item['ticker']}: error — {item['error']}")
        else:
            flag = " ← changed" if item.get("changed") else ""
            print(f"  #{item['id']} {item['ticker']}: {item['status']}{flag}")
    return 0


def _job_config(job: dict, base_cfg: dict) -> "tuple[dict, list]":
    """Build the (cfg, tickers) for a saved custom job. Pure: mirrors the on-demand
    screen path (api/screen.run_screen) — the job's strategies + custom criteria
    over its ticker list — without touching the network."""
    import copy
    from .criteria import STRATEGIES
    tickers = [t.strip().upper() for t in (job.get("tickers") or "").split(",") if t.strip()]
    cfg = copy.deepcopy(base_cfg)
    # Custom jobs screen their pool with the selected built-in strategies (or the
    # defaults). They no longer emit a "custom" strategy row — any saved criteria
    # are not scored into a persisted result.
    chosen = [s for s in (job.get("strategies") or []) if s in STRATEGIES and s != "custom"]
    cfg["strategies"] = chosen or ["graham", "buffett"]
    cfg["universe"] = {"mode": "list", "tickers": tickers}
    return cfg, tickers


def _name_seed(name: str) -> int:
    """A stable (PYTHONHASHSEED-independent) integer seed from a job name."""
    s = 0
    for ch in (name or ""):
        s = (s * 131 + ord(ch)) & 0xFFFFFFFF
    return s


def _sample_pool(pool: list, job: dict) -> list:
    """Randomly draw ``job['pick']`` tickers from the pool — a different subset each
    scheduled run, yet reproducible within a run window (seeded by the rotation tick
    plus the job name) so a workflow retry screens the same set. Blank/0/≥size keeps
    the whole pool."""
    try:
        pick = int(job.get("pick") or 0)
    except (TypeError, ValueError):
        pick = 0
    if pick <= 0 or pick >= len(pool):
        return pool
    from datetime import datetime, timezone
    from .schedule import rotation_tick
    seed = rotation_tick(datetime.now(timezone.utc)) * 1_000_003 + _name_seed(job.get("name") or "")
    return random.Random(seed).sample(pool, pick)


def _run_one_job(job: dict, base_cfg: dict, store) -> "Optional[int]":
    """Run a single saved custom job and persist it as its own run. Returns the
    run id (or None)."""
    name = (job.get("name") or "unnamed").strip()
    cfg, pool = _job_config(job, base_cfg)
    if not pool:
        print(f"  job {name!r}: no tickers — skipped", file=sys.stderr)
        return None
    tickers = _sample_pool(pool, job)   # random draw from the pool when `pick` is set
    screener = Screener(cfg)
    screener.store = store
    results = screener.run(tickers, progress=_progress)
    passing = sum(1 for r in results if r.passed)
    run_id = None
    if cfg.get("storage", {}).get("persist_runs", True) and getattr(store, "enabled", False):
        try:
            run_id = store.save_run(
                results, screener.last_companies,
                # Tagged scheduled (so the catch-up gate/History see it) plus the
                # job name so the run is attributable to this job.
                meta={"source": "schedule", "job": name,
                      "universe": len({r.ticker for r in results})})
            picked = (f"{len(tickers)} of {len(pool)}" if len(tickers) < len(pool)
                      else f"{len(tickers)}")
            print(f"  job {name!r}: stored run #{run_id} — "
                  f"{picked} tickers, {passing} passing")
        except Exception as exc:  # persistence must never sink the batch
            print(f"  job {name!r}: could not store run: {exc}", file=sys.stderr)
    screener.last_companies = {}
    return run_id


def cmd_run_jobs(args) -> int:
    """Run every saved custom job (stored in the settings blob) and persist each
    as its own run. Invoked by the scheduled workflow alongside the nightly screen."""
    cfg = _load(args)
    jobs = cfg.get("jobs") or []
    if not jobs:
        print("No saved custom jobs to run.")
        return 0
    from .storage import get_storage
    store = get_storage(cfg)
    ran = 0
    for job in jobs:
        try:
            _run_one_job(job, cfg, store)
            ran += 1
        except Exception as exc:  # never let one job sink the rest
            print(f"  job {job.get('name')!r} failed: {exc}", file=sys.stderr)
    print(f"Ran {ran} of {len(jobs)} saved custom job(s).")
    return 0


COMMANDS = {
    "screen": cmd_screen,
    "config": cmd_config,
    "validate": cmd_validate,
    "tickers": cmd_tickers,
    "schedule": cmd_schedule,
    "schedule-gate": cmd_schedule_gate,
    "analyze-queue": cmd_analyze_queue,
    "check-theses": cmd_check_theses,
    "run-jobs": cmd_run_jobs,
    "purge-strategy": cmd_purge_strategy,
}


def main(argv: Optional[list[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(message)s",
    )
    return COMMANDS[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
