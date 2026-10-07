import pandas as pd
import pytest

from gb_demand_forecast.timeutils import expected_periods, settlement_period_to_utc


def to_utc(date: str, periods: list[int]) -> list[str]:
    result = settlement_period_to_utc(pd.Series([date] * len(periods)), pd.Series(periods))
    return [t.strftime("%Y-%m-%d %H:%M") for t in result]


@pytest.mark.parametrize(
    ("day", "expected"),
    [("2025-06-15", 48), ("2025-03-30", 46), ("2025-10-26", 50)],
)
def test_expected_periods(day, expected):
    assert expected_periods(day) == expected


def test_summer_day_starts_at_2300_utc_previous_day():
    assert to_utc("2025-06-15", [1, 48]) == ["2025-06-14 23:00", "2025-06-15 22:30"]


def test_clocks_forward_day_has_no_gap():
    # 01:00 GMT becomes 02:00 BST; period 3 is 01:00 UTC
    assert to_utc("2025-03-30", [1, 3, 46]) == [
        "2025-03-30 00:00",
        "2025-03-30 01:00",
        "2025-03-30 22:30",
    ]


def test_clocks_back_day_has_50_periods_ending_2330_utc():
    assert to_utc("2025-10-26", [1, 50]) == ["2025-10-25 23:00", "2025-10-26 23:30"]


def test_consecutive_days_are_continuous_across_clock_changes():
    days = ["2025-03-29", "2025-03-30", "2025-03-31", "2025-10-25", "2025-10-26", "2025-10-27"]
    dates, periods = [], []
    for day in days:
        n = expected_periods(day)
        dates += [day] * n
        periods += list(range(1, n + 1))
    ts = settlement_period_to_utc(pd.Series(dates), pd.Series(periods))
    for block in (ts.iloc[:142], ts.iloc[142:]):  # first 3 days, last 3 days
        assert block.is_unique
        assert (block.diff().dropna() == pd.Timedelta(minutes=30)).all()
