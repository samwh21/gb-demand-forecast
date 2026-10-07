"""Time helpers for GB electricity settlement periods."""

from __future__ import annotations

import pandas as pd

UK_TZ = "Europe/London"
PERIOD = pd.Timedelta(minutes=30)


def settlement_period_to_utc(settlement_date: pd.Series, settlement_period: pd.Series) -> pd.Series:
    """Return the UTC start time of each half-hourly settlement period.

    Period 1 starts at local UK midnight; each period is 30 minutes of elapsed time,
    so clock-change days naturally have 46 or 50 periods.
    """
    local_midnight = pd.to_datetime(settlement_date).dt.normalize().dt.tz_localize(UK_TZ)
    return local_midnight.dt.tz_convert("UTC") + (settlement_period - 1) * PERIOD


def expected_periods(day: str | pd.Timestamp) -> int:
    """Number of settlement periods in a UK settlement day (48, or 46/50 on clock changes)."""
    start = pd.Timestamp(day).normalize()
    elapsed = (start + pd.Timedelta(days=1)).tz_localize(UK_TZ) - start.tz_localize(UK_TZ)
    return int(elapsed / PERIOD)
