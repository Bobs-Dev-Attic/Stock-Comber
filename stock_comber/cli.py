"""Command-line interface for Stock-Comber."""

from __future__ import annotations

import argparse
import json
import logging
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
    ps.add_argument("--strategy", action="append", choices=["graham", "buffett", "custom"],
                    help="Restrict to specific strategies (repeatable).")
    ps.add_argument("--only-passing", action="store_true", help="Report only passing rows.")
    ps.add_argument("--no-write", action="store_true", help="Print to stdout, don't write files.")

    sub.add_parser("config", help="Print the effective configuration and exit.")
    sub.add_parser("validate", help="Validate the configuration and exit.")

    pt = sub.add_parser("tickers", help="List available tickers from SEC EDGAR.")
    pt.add_argument("--limit", type=int, default=50)

    psch = sub.add_parser("schedule", help="Run the screen on a recurring local schedule.")
    psch.add_argument("--once", action="store_true", help="Run one cycle then exit.")

    paq = sub.add_parser("analyze-queue",
                         help="Process queued tickers with a full analysis (news + sentiment).")
    paq.add_argument("--limit", type=int, default=5, help="Max tickers to process.")
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
    if getattr(args, "strategy", None):
        cfg["strategies"] = args.strategy
    if getattr(args, "only_passing", False):
        cfg["output"]["only_passing"] = True
    return cfg


def _progress(i: int, total: int, ticker: str) -> None:
    print(f"  [{i}/{total}] {ticker}", file=sys.stderr)


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

    # Persist the run when a database is configured.
    if cfg.get("storage", {}).get("persist_runs", True):
        if getattr(store, "enabled", False):
            try:
                run_id = store.save_run(
                    results, screener.last_companies,
                    meta={"universe": len({r.ticker for r in results})},
                )
                print(f"Stored run #{run_id} in the database.")
            except Exception as exc:  # persistence must never fail the screen
                print(f"Warning: could not store run: {exc}", file=sys.stderr)

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


def cmd_analyze_queue(args) -> int:
    from .analysis import process_queue
    from .storage import get_storage
    cfg = _load(args)
    store = get_storage(cfg)
    if not getattr(store, "enabled", False):
        print("No database configured (set DATABASE_URL); nothing to process.",
              file=sys.stderr)
        return 0
    summary = process_queue(cfg, store, limit=args.limit)
    print(f"Processed {summary.get('processed', 0)} queued ticker(s).")
    for item in summary.get("tickers", []):
        if "error" in item:
            print(f"  {item['ticker']}: error — {item['error']}")
        else:
            print(f"  {item['ticker']}: analysed → run #{item['run_id']}")
    return 0


COMMANDS = {
    "screen": cmd_screen,
    "config": cmd_config,
    "validate": cmd_validate,
    "tickers": cmd_tickers,
    "schedule": cmd_schedule,
    "analyze-queue": cmd_analyze_queue,
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
