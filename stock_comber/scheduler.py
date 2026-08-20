"""Optional local scheduler for recurring screens.

For hosted/cron-based scheduling prefer the GitHub Actions workflow in
``.github/workflows/screen.yml``. This module is a convenience for running a
recurring screen on a machine you control, using APScheduler when available and
falling back to a simple sleep loop otherwise.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from .report import write_reports
from .screener import Screener

log = logging.getLogger("stock_comber.scheduler")


def run_once(cfg: dict[str, Any]) -> int:
    screener = Screener(cfg)
    results = screener.run()
    paths = write_reports(results, cfg)
    passing = sum(1 for r in results if r.passed)
    log.info("screen complete: %d passing; wrote %d files", passing, len(paths))
    print(f"Screen complete: {passing} passing. Reports: {', '.join(paths)}")
    return 0


def run_schedule(cfg: dict[str, Any], once: bool = False) -> int:
    if once:
        return run_once(cfg)

    sched_cfg = cfg.get("schedule", {})
    cron = sched_cfg.get("cron", "0 6 * * 1-5")
    tz = sched_cfg.get("timezone", "UTC")
    try:
        from apscheduler.schedulers.blocking import BlockingScheduler
        from apscheduler.triggers.cron import CronTrigger

        scheduler = BlockingScheduler(timezone=tz)
        scheduler.add_job(lambda: run_once(cfg), CronTrigger.from_crontab(cron, timezone=tz))
        print(f"Scheduled screen with cron '{cron}' ({tz}). Ctrl-C to stop.")
        try:
            scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            print("Scheduler stopped.")
        return 0
    except ImportError:
        log.warning("APScheduler not installed; running once then exiting. "
                    "Install 'apscheduler' or use the GitHub Actions workflow.")
        return run_once(cfg)
