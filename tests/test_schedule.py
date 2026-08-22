import datetime

from stock_comber.schedule import should_run_now

UTC = datetime.timezone.utc


def at(y, mo, d, h, mi):
    return datetime.datetime(y, mo, d, h, mi, tzinfo=UTC)


FRI_0630 = at(2026, 8, 21, 6, 30)   # Friday 06:30
FRI_0600 = at(2026, 8, 21, 6, 0)    # Friday 06:00
FRI_0900 = at(2026, 8, 21, 9, 0)    # Friday 09:00
SAT_0800 = at(2026, 8, 22, 8, 0)    # Saturday 08:00
SUN_0800 = at(2026, 8, 23, 8, 0)    # Sunday 08:00
MON_0630 = at(2026, 8, 24, 6, 30)   # Monday 06:30


def run(stored, now):
    return should_run_now(stored, now)[0]


def test_default_when_unconfigured_runs_weekday_0630():
    # No stored schedule -> default "30 6 * * 1-5" (preserves prior behaviour).
    assert run({}, FRI_0630) is True
    assert run(None, MON_0630) is True


def test_default_skips_wrong_minute_hour_and_weekend():
    assert run({}, FRI_0600) is False          # right hour, wrong minute (0 vs 30)
    assert run({}, FRI_0900) is False          # wrong hour
    assert run({}, SAT_0800) is False          # weekend


def test_disabled_never_runs():
    stored = {"schedule": {"enabled": False, "cron": "0 6 * * 1-5"}}
    assert run(stored, FRI_0600) is False


def test_stored_hour_and_minute_drive_run():
    stored = {"schedule": {"enabled": True, "cron": "0 9 * * *"}}
    assert run(stored, FRI_0900) is True       # matches 09:00, any day
    assert run(stored, FRI_0600) is False      # not hour 6


def test_minute_matched_to_five_minute_slot():
    stored = {"schedule": {"enabled": True, "cron": "32 6 * * 1-5"}}
    # Heartbeat window 30–34 contains minute 32 -> fires at the :30 tick.
    assert run(stored, at(2026, 8, 21, 6, 30)) is True
    assert run(stored, at(2026, 8, 21, 6, 34)) is True
    # The :35 and :25 ticks are outside the 30–34 window.
    assert run(stored, at(2026, 8, 21, 6, 35)) is False
    assert run(stored, at(2026, 8, 21, 6, 25)) is False


def test_exact_five_minute_minute():
    stored = {"schedule": {"enabled": True, "cron": "15 6 * * 1-5"}}
    assert run(stored, at(2026, 8, 21, 6, 15)) is True
    assert run(stored, at(2026, 8, 21, 6, 20)) is False
    assert run(stored, at(2026, 8, 21, 6, 10)) is False


def test_weekend_cron():
    stored = {"schedule": {"enabled": True, "cron": "0 8 * * 0,6"}}
    assert run(stored, SAT_0800) is True       # Saturday (dow 6)
    assert run(stored, SUN_0800) is True       # Sunday (dow 0)
    assert run(stored, FRI_0600) is False


def test_sunday_as_seven():
    stored = {"schedule": {"enabled": True, "cron": "0 8 * * 7"}}
    assert run(stored, SUN_0800) is True       # 7 also means Sunday


def test_invalid_cron_does_not_run():
    stored = {"schedule": {"enabled": True, "cron": "nonsense"}}
    assert run(stored, FRI_0600) is False


def test_step_field():
    stored = {"schedule": {"enabled": True, "cron": "0 */2 * * *"}}
    assert run(stored, at(2026, 8, 21, 6, 0)) is True    # 6 is even
    assert run(stored, at(2026, 8, 21, 9, 0)) is False   # 9 is odd


def test_rotation_tick_advances_each_hour_and_day():
    from stock_comber.schedule import rotation_tick
    base = at(2026, 8, 21, 6, 30)
    t6 = rotation_tick(base)
    t10 = rotation_tick(at(2026, 8, 21, 10, 30))
    t_next = rotation_tick(at(2026, 8, 22, 6, 30))
    assert t10 == t6 + 4            # +4 hours -> +4 ticks (fresh names each run)
    assert t_next == t6 + 24        # next day at same hour -> +24


def test_every_n_hours_cron_fires_on_matching_hours():
    # 00/04/08/12/16/20:30 on weekdays.
    stored = {"schedule": {"enabled": True, "cron": "30 */4 * * 1-5"}}
    assert should_run_now(stored, at(2026, 8, 21, 8, 30))[0] is True    # Fri 08:30 ✓
    assert should_run_now(stored, at(2026, 8, 21, 12, 30))[0] is True   # Fri 12:30 ✓
    assert should_run_now(stored, at(2026, 8, 21, 10, 30))[0] is False  # 10 not a step
    assert should_run_now(stored, at(2026, 8, 22, 8, 30))[0] is False   # Saturday
