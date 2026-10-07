import pandas as pd
import pytest

from gb_demand_forecast.ingest.process_demand import parse_settlement_dates


def test_iso_dates_are_not_day_month_swapped():
    parsed = parse_settlement_dates(pd.Series(["2026-02-05", "2026-01-10"]))
    assert list(parsed.dt.strftime("%d %b")) == ["05 Feb", "10 Jan"]


def test_month_name_format_parses():
    parsed = parse_settlement_dates(pd.Series(["01-JAN-2018", "28-OCT-2018"]))
    assert list(parsed.dt.strftime("%Y-%m-%d")) == ["2018-01-01", "2018-10-28"]


def test_unknown_format_raises():
    with pytest.raises(ValueError):
        parse_settlement_dates(pd.Series(["05/02/2026"]))


def test_two_digit_year_format_parses():
    parsed = parse_settlement_dates(pd.Series(["01-Jan-23", "29-Oct-23"]))
    assert list(parsed.dt.strftime("%Y-%m-%d")) == ["2023-01-01", "2023-10-29"]
