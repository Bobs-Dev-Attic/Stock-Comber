import datetime

from stock_comber.schedule import should_run_now

UTC = datetime.timezone.utc


def at(y, mo, d, h, mi):
    return datetime.datetime(y, mo, d, h, mi, tzinfo=UTC)


def run(stored, now, last_run=None):
    return should_run_now(stored, now, last_run)[0]


# 2026-08-21 is a Friday; 08-22 Sat, 08-23 Sun, 08-24 Mon.
FRI_0630 = at(2026, 8, 21, 6, 30)
THU_0630 = at(2026, 8, 20, 6, 30)


# -- default (unconfigured) → weekdays 06:30 -------------------------------
def test_default_due_at_slot_when_not_yet_run():
    assert run({}, FRI_0630, last_run=THU_0630) is True     # Fri slot, last ran Thu
    assert run(None, at(2026, 8, 24, 6, 30), last_run=FRI_0630) is True  # Mon slot


def test_default_not_due_once_slot_has_run():
    assert run({}, FRI_0630, last_run=FRI_0630) is False    # already ran this slot
    # Later the same day, still not due (last run is at/after the slot).
    assert run({}, at(2026, 8, 21, 12, 0), last_run=FRI_0630) is False


def test_weekend_holds_last_weekday_slot():
    # Saturday: the most recent slot is Friday 06:30; if it ran, don't re-run.
    assert run({}, at(2026, 8, 22, 8, 0), last_run=FRI_0630) is False
    # …but if Friday's slot was somehow missed, catch it up once.
    assert run({}, at(2026, 8, 22, 8, 0), last_run=THU_0630) is True


# -- catch-up: a LATE heartbeat still fires the slot ------------------------
def test_late_heartbeat_still_fires_the_slot():
    stored = {"schedule": {"enabled": True, "cron": "30 */4 * * *"}}
    # GitHub fires at 08:49 instead of 08:30 — the 08:30 slot must still run.
    assert run(stored, at(2026, 8, 21, 8, 49), last_run=at(2026, 8, 21, 4, 30)) is True


def test_dedup_after_a_late_catch_up_run():
    stored = {"schedule": {"enabled": True, "cron": "30 */4 * * *"}}
    # Once the 08:30 slot has run (at 08:49), the next heartbeat won't re-run it.
    assert run(stored, at(2026, 8, 21, 8, 55), last_run=at(2026, 8, 21, 8, 49)) is False


# -- every-4-hours -----------------------------------------------------------
def test_every_4h_due_for_prior_slot():
    stored = {"schedule": {"enabled": True, "cron": "30 */4 * * *"}}
    # 10:30 isn't a step hour; the last slot is 08:30. Due if not run since.
    assert run(stored, at(2026, 8, 21, 10, 30), last_run=at(2026, 8, 21, 4, 30)) is True
    assert run(stored, at(2026, 8, 21, 10, 30), last_run=at(2026, 8, 21, 8, 30)) is False


def test_every_4h_weekday_restricted():
    stored = {"schedule": {"enabled": True, "cron": "30 */4 * * 1-5"}}
    # Saturday has no slot of its own; holds Friday's last (20:30).
    assert run(stored, at(2026, 8, 22, 9, 0), last_run=at(2026, 8, 21, 20, 30)) is False
    assert run(stored, at(2026, 8, 22, 9, 0), last_run=at(2026, 8, 21, 12, 30)) is True


# -- disabled / invalid ------------------------------------------------------
def test_disabled_never_runs():
    stored = {"schedule": {"enabled": False, "cron": "0 6 * * 1-5"}}
    assert run(stored, FRI_0630, last_run=None) is False


def test_invalid_cron_does_not_run():
    stored = {"schedule": {"enabled": True, "cron": "nonsense"}}
    assert run(stored, FRI_0630) is False


def test_no_reachable_slot_does_not_run():
    # Feb 31 never occurs → no slot in the lookback window.
    stored = {"schedule": {"enabled": True, "cron": "0 0 31 2 *"}}
    assert run(stored, FRI_0630, last_run=None) is False


def test_never_run_fires_once():
    stored = {"schedule": {"enabled": True, "cron": "0 9 * * *"}}
    assert run(stored, at(2026, 8, 21, 9, 0), last_run=None) is True


# -- day-of-week forms -------------------------------------------------------
def test_weekend_cron():
    stored = {"schedule": {"enabled": True, "cron": "0 8 * * 0,6"}}
    assert run(stored, at(2026, 8, 22, 8, 0), last_run=at(2026, 8, 16, 8, 0)) is True   # Sat
    assert run(stored, at(2026, 8, 23, 8, 0), last_run=at(2026, 8, 22, 8, 0)) is True   # Sun


def test_sunday_as_seven():
    stored = {"schedule": {"enabled": True, "cron": "0 8 * * 7"}}
    assert run(stored, at(2026, 8, 23, 8, 0), last_run=at(2026, 8, 16, 8, 0)) is True


def test_step_hour_field():
    stored = {"schedule": {"enabled": True, "cron": "0 */2 * * *"}}
    assert run(stored, at(2026, 8, 21, 6, 0), last_run=at(2026, 8, 21, 4, 0)) is True   # 6 even
    # 09:00 → last even-hour slot is 08:00; not due if it already ran.
    assert run(stored, at(2026, 8, 21, 9, 0), last_run=at(2026, 8, 21, 8, 0)) is False


def test_naive_last_run_is_treated_as_utc():
    stored = {"schedule": {"enabled": True, "cron": "30 */4 * * *"}}
    naive = datetime.datetime(2026, 8, 21, 8, 30)   # no tzinfo
    assert run(stored, at(2026, 8, 21, 8, 49), last_run=naive) is False


def test_rotation_tick_advances_each_hour_and_day():
    from stock_comber.schedule import rotation_tick
    base = at(2026, 8, 21, 6, 30)
    assert rotation_tick(at(2026, 8, 21, 10, 30)) == rotation_tick(base) + 4
    assert rotation_tick(at(2026, 8, 22, 6, 30)) == rotation_tick(base) + 24
