import datetime

from stock_comber.schedule import should_run_now

UTC = datetime.timezone.utc
FRI_06 = datetime.datetime(2026, 8, 21, 6, 0, tzinfo=UTC)   # Friday 06:00
FRI_09 = datetime.datetime(2026, 8, 21, 9, 0, tzinfo=UTC)   # Friday 09:00
SAT_08 = datetime.datetime(2026, 8, 22, 8, 0, tzinfo=UTC)   # Saturday 08:00
SUN_08 = datetime.datetime(2026, 8, 23, 8, 0, tzinfo=UTC)   # Sunday 08:00
MON_06 = datetime.datetime(2026, 8, 24, 6, 0, tzinfo=UTC)   # Monday 06:00


def run(stored, now):
    return should_run_now(stored, now)[0]


def test_default_when_unconfigured_runs_weekday_06():
    # No stored schedule -> default 06:xx weekdays (preserves prior behaviour).
    assert run({}, FRI_06) is True
    assert run(None, MON_06) is True


def test_default_skips_wrong_hour_and_weekend():
    assert run({}, FRI_09) is False           # wrong hour
    assert run({}, SAT_08) is False           # weekend
    assert run({}, SUN_08) is False


def test_disabled_never_runs():
    stored = {"schedule": {"enabled": False, "cron": "0 6 * * 1-5"}}
    assert run(stored, FRI_06) is False


def test_stored_hour_drives_run():
    stored = {"schedule": {"enabled": True, "cron": "0 9 * * *"}}
    assert run(stored, FRI_09) is True        # matches hour 9, any day
    assert run(stored, FRI_06) is False        # not hour 6


def test_minute_is_ignored_hourly_heartbeat():
    # Stored minute 30, but the heartbeat fires at :00 — still runs on the hour.
    stored = {"schedule": {"enabled": True, "cron": "30 6 * * 1-5"}}
    assert run(stored, FRI_06) is True


def test_weekend_cron():
    stored = {"schedule": {"enabled": True, "cron": "0 8 * * 0,6"}}
    assert run(stored, SAT_08) is True         # Saturday (dow 6)
    assert run(stored, SUN_08) is True         # Sunday (dow 0)
    assert run(stored, FRI_06) is False


def test_sunday_as_seven():
    stored = {"schedule": {"enabled": True, "cron": "0 8 * * 7"}}
    assert run(stored, SUN_08) is True         # 7 also means Sunday


def test_invalid_cron_does_not_run():
    stored = {"schedule": {"enabled": True, "cron": "nonsense"}}
    assert run(stored, FRI_06) is False


def test_step_field():
    stored = {"schedule": {"enabled": True, "cron": "0 */2 * * *"}}
    assert run(stored, FRI_06) is True         # 6 is even
    assert run(stored, FRI_09) is False        # 9 is odd
