from datetime import date

import numpy as np
import pandas as pd

from gb_demand_forecast.ingest.process_weather import (
    parse_payload,
    to_half_hourly,
    weighted_average,
)
from gb_demand_forecast.ingest.weather import build_params


def test_forecast_params_request_day2_variables_and_pinned_model():
    params = build_params("forecast", 51.5, -0.1, date(2024, 1, 1), date(2024, 12, 31))
    assert "temperature_2m_previous_day2" in params["hourly"]
    assert params["models"] == "ecmwf_ifs025"
    assert params["timezone"] == "UTC"


def test_parse_payload_strips_suffix_and_sets_utc():
    payload = {"hourly": {"time": ["2024-01-01T00:00"], "temperature_2m_previous_day2": [5.0]}}
    df = parse_payload(payload, "_previous_day2")
    assert list(df.columns) == ["temperature_2m"]
    assert str(df.index.tz) == "UTC"


def test_weighted_average_reweights_when_a_city_is_missing():
    t = pd.to_datetime(["2024-01-01 00:00"], utc=True)
    frames = {
        "a": pd.DataFrame({"temperature_2m": [10.0]}, index=t),
        "b": pd.DataFrame({"temperature_2m": [np.nan]}, index=t),
    }
    result = weighted_average(frames, {"a": 3.0, "b": 1.0})
    assert result["temperature_2m"].iloc[0] == 10.0  # not 7.5


def test_half_hourly_interpolates_and_recentres_radiation():
    t = pd.to_datetime(["2024-06-01 00:00", "2024-06-01 01:00", "2024-06-01 02:00"], utc=True)
    df = pd.DataFrame(
        {"temperature_2m": [10.0, 12.0, 14.0], "shortwave_radiation": [0.0, 100.0, 200.0]}, index=t
    )
    out = to_half_hourly(df)
    assert out.loc["2024-06-01 00:30", "temperature_2m"] == 11.0
    # the 01:00 value averages 00:00-01:00, so it should sit at 00:30
    assert out.loc["2024-06-01 00:30", "shortwave_radiation"] == 100.0


def test_leading_all_missing_hours_are_not_kept():
    t = pd.date_range("2024-01-01", periods=3, freq="h", tz="UTC")
    frames = {"a": pd.DataFrame({"temperature_2m": [np.nan, np.nan, 5.0]}, index=t)}
    hourly = weighted_average(frames, {"a": 1.0}).dropna(how="all")
    assert hourly.index.min() == t[2]
