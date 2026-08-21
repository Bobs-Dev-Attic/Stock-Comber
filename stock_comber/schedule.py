"""Decide whether the hosted nightly run should fire *now*.

GitHub Actions cron lives in static YAML and can't read the database at trigger
time. So the workflow instead runs on a frequent (hourly) heartbeat and calls
:func:`should_run_now`, which consults the schedule the user saved from the
dashboard (``settings.schedule`` in the database) and answers yes/no for the
current hour. This makes the *stored* schedule drive the hosted run.

Because the heartbeat is hourly, the cron ``minute`` field is ignored — a run
fires at the top of its configured hour. The other fields (hour, day-of-month,
month, day-of-week) are matched against the current UTC time.

When no schedule is stored (or no database is configured), the built-in default
preserves the original hosted behaviour: 06:xx UTC on weekdays.
"""

from __future__ import annotations

from typing import Optional, Tuple

# Preserves the pre-scheduling hosted behaviour when nothing is stored.
DEFAULT_SCHEDULE = {"enabled": True, "cron": "30 6 * * 1-5"}


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


def should_run_now(stored_settings: Optional[dict], now) -> Tuple[bool, str]:
    """Return ``(run, reason)`` for the given UTC ``now`` (a timezone-aware or
    naive datetime treated as UTC), based on the stored schedule.

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
    _minute, hour, dom, month, dow = fields[:5]  # minute ignored (hourly heartbeat)

    # cron day-of-week: 0 or 7 = Sunday, 1 = Monday … 6 = Saturday.
    cron_dow = now.isoweekday() % 7  # Mon..Sat = 1..6, Sun = 0
    ok = (_match_field(now.hour, hour, 0, 23)
          and _match_field(now.day, dom, 1, 31)
          and _match_field(now.month, month, 1, 12)
          and (_match_field(cron_dow, dow, 0, 6)
               or _match_field(7, dow, 0, 7) and cron_dow == 0))
    when = now.strftime("%Y-%m-%d %H:00 UTC")
    return (ok, f"cron {sched['cron']!r} {'matches' if ok else 'does not match'} {when} (dow {cron_dow})")
