import pandas as pd
import pytest

from gb_demand_forecast.ingest.process_benchmark import load_benchmark, normalise_columns

RAW_HEADERS = [
    "Month",
    "Date",
    "Datetime",
    "Settlement Period",
    "Demand Forecast",
    "Demand Outturn",
    "TRIAD Avoidance Estimate",
    "TRIAD Avoidance Corrected Demand Outturn",
    "APE (Absolute Percentage Error)",
    "Absolute Error",
    "Publish Datetime",
]


def write_raw(path, headers):
    rows = [
        ["Oct", "2025-10-26", "x", 1, 20000, 20100, 0, 20100, 0.5, 100, "2025-10-25T08:45:00Z"],
        ["Oct", "2025-10-26", "x", 5, 21000, 20900, 0, 20900, 0.5, 100, "2025-10-25T08:45:00Z"],
    ]
    pd.DataFrame(rows, columns=headers).to_csv(path, index=False)
    return path


def test_normalise_columns_handles_spaces_case_and_brackets():
    cols = normalise_columns(pd.Index(["Demand Forecast", "DEMAND_FORECAST", "APE (Absolute %)"]))
    assert list(cols) == ["demand_forecast", "demand_forecast", "ape_absolute_"]


@pytest.mark.parametrize(
    "headers", [RAW_HEADERS, [h.upper().replace(" ", "_") for h in RAW_HEADERS]]
)
def test_load_benchmark_builds_utc_timestamps_on_clocks_back_day(tmp_path, headers):
    df = load_benchmark(write_raw(tmp_path / "raw.csv", headers))
    # 26 Oct 2025: UK midnight = 23:00 UTC; period 5 starts 2 hours later
    assert list(df["timestamp_utc"].dt.strftime("%Y-%m-%d %H:%M")) == [
        "2025-10-25 23:00",
        "2025-10-26 01:00",
    ]
    assert list(df["neso_forecast"]) == [20000, 21000]
