"""Decide whether the hosted nightly run should fire *now*.

GitHub Actions cron lives in static YAML and can't read the database at trigger
time. So the workflow instead runs on a frequent (hourly) heartbeat and calls
:func:`should_run_now`, which consults the schedule the user saved from the
dashboard (``settings.schedule`` in the database) and answers yes/no for the
current hour. This makes the *stored* schedule drive the hosted run.

GitHub throttles frequent scheduled crons hard — a ``*/5`` heartbeat often only
fires every 20–40 minutes — so a gate that required a heartbeat to land inside the
exact minute of a scheduled slot routinely *missed* the slot and skipped the run.
Instead the gate is **catch-up**: :func:`should_run_now` fires on the first
heartbeat at or after a scheduled slot, and de-duplicates on ``last_run`` (the
timestamp of the most recent scheduled run) so it runs a slot once even when the
heartbeat that triggers it is minutes late. All cron fields (minute, hour,
day-of-month, month, day-of-week) are matched against UTC.

When no schedule is stored (or no database is configured), the built-in default
preserves the original hosted behaviour: 06:30 UTC on weekdays.
"""

from __future__ import annotations

import datetime
from typing import Optional, Tuple

# Must match the workflow heartbeat (screen.yml: cron "*/5 * * * *").
HEARTBEAT_MINUTES = 5

# How far back to search for the most recent scheduled slot. Eight days covers
# weekly (day-of-week-restricted) schedules with room to spare.
_LOOKBACK_MINUTES = 8 * 24 * 60

# Preserves the pre-scheduling hosted behaviour when nothing is stored.
DEFAULT_SCHEDULE = {"enabled": True, "cron": "30 6 * * 1-5"}


def rotation_tick(now) -> int:
    """Seed for the nightly universe rotation that advances every hour, so a
    shorter-than-daily schedule (e.g. every 4 hours) screens fresh names on each
    run rather than repeating the same day's pool. Deterministic from the run's
    UTC time, so the dashboard preview can reproduce it for the next run."""
    return now.toordinal() * 24 + now.hour


def _match_field(value: int, spec: str, lo: int, hi: int) -> bool:
    """Match a single cron field. Supports ``*``, ``a``, ``a,b``, ``a-b`` and
    ``*/n`` / ``a-b/n`` steps, bounded to ``[lo, hi]``."""
    spec = (spec or "*").strip()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        step = 1
        body = part
        if "/" in part:
            body, step_s = part.split("/", 1)
            try:
                step = max(1, int(step_s))
            except ValueError:
                step = 1
        if body == "*":
            a, b = lo, hi
        elif "-" in body:
            aa, bb = body.split("-", 1)
            try:
                a, b = int(aa), int(bb)
            except ValueError:
                continue
        else:
            try:
                a = b = int(body)
            except ValueError:
                continue
        if a <= value <= b and (value - a) % step == 0:
            return True
    return False


def _matches(dt: datetime.datetime, minute: str, hour: str, dom: str,
             month: str, dow: str) -> bool:
    """Whether ``dt`` (UTC) exactly matches every cron field."""
    cron_dow = dt.isoweekday() % 7   # Mon..Sat = 1..6, Sun = 0
    return (_match_field(dt.minute, minute, 0, 59)
            and _match_field(dt.hour, hour, 0, 23)
            and _match_field(dt.day, dom, 1, 31)
            and _match_field(dt.month, month, 1, 12)
            and (_match_field(cron_dow, dow, 0, 6)
                 or (_match_field(7, dow, 0, 7) and cron_dow == 0)))


def _last_slot(now: datetime.datetime, fields) -> Optional[datetime.datetime]:
    """The most recent minute ``<= now`` matching the cron, or None if none falls
    within the lookback window."""
    minute, hour, dom, month, dow = fields
    cur = now.replace(second=0, microsecond=0)
    for _ in range(_LOOKBACK_MINUTES + 1):
        if _matches(cur, minute, hour, dom, month, dow):
            return cur
        cur -= datetime.timedelta(minutes=1)
    return None


def should_run_now(stored_settings: Optional[dict], now,
                   last_run: "Optional[datetime.datetime]" = None) -> Tuple[bool, str]:
    """Return ``(run, reason)`` for the given UTC ``now`` (timezone-aware or naive,
    treated as UTC), based on the stored schedule — **catch-up** semantics.

    Fires when there is a scheduled slot at or before ``now`` that hasn't been run
    yet: i.e. the most recent matching slot is newer than ``last_run`` (the
    timestamp of the last scheduled run, or None if there hasn't been one). This
    tolerates GitHub's throttled/late heartbeats — the first tick after a slot
    runs it — while ``last_run`` de-duplicates so a slot fires only once.

    ``stored_settings`` is the raw settings blob from the database (so an absent
    ``schedule`` key means "never configured" → default), not the effective
    config (whose default ``schedule.enabled`` is False).
    """
    sched = (stored_settings or {}).get("schedule")
    if not isinstance(sched, dict) or not sched.get("cron"):
        sched = DEFAULT_SCHEDULE
    if not sched.get("enabled", False):
        return False, "schedule disabled"

    fields = str(sched.get("cron") or "").split()
    if len(fields) < 5:
        return False, f"invalid cron: {sched.get('cron')!r}"

    slot = _last_slot(now, fields[:5])
    cron = sched["cron"]
    when = now.strftime("%Y-%m-%d %H:%M UTC")
    if slot is None:
        return False, f"cron {cron!r}: no scheduled slot in the 8 days before {when}"

    # Normalise last_run to an aware UTC datetime for comparison.
    lr = last_run
    if lr is not None and lr.tzinfo is None:
        lr = lr.replace(tzinfo=datetime.timezone.utc)
    slot_str = slot.strftime("%Y-%m-%d %H:%M UTC")
    if lr is not None and lr >= slot:
        return False, (f"cron {cron!r}: already ran for slot {slot_str} "
                       f"(last scheduled run {lr.strftime('%Y-%m-%d %H:%M UTC')})")
    last_txt = lr.strftime("%Y-%m-%d %H:%M UTC") if lr is not None else "never"
    return True, (f"cron {cron!r}: due for slot {slot_str} at {when} "
                  f"(last scheduled run {last_txt})")
