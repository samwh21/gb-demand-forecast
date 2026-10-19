"""Clean NESO's published day-ahead demand forecasts into a UTC-indexed benchmark table."""

import logging
from pathlib import Path

import pandas as pd

from gb_demand_forecast.ingest.benchmark import RAW_PATH
from gb_demand_forecast.ingest.process_demand import parse_settlement_dates
from gb_demand_forecast.timeutils import expected_periods, settlement_period_to_utc

logger = logging.getLogger(__name__)

PROCESSED_PATH = Path("data/processed/neso_benchmark.parquet")

# normalised raw column -> clean column name
COLUMNS = {
    "date": "settlement_date",
    "settlement_period": "settlement_period",
    "demand_forecast": "neso_forecast",
    "demand_outturn": "neso_outturn",
    "triad_avoidance_estimate": "triad_avoidance",
    "publish_datetime": "published",
}


def normalise_columns(columns: pd.Index) -> pd.Index:
    """'Demand Forecast' and 'DEMAND_FORECAST' both become 'demand_forecast'."""
    return columns.str.strip().str.lower().str.replace(r"[^a-z0-9]+", "_", regex=True)


def load_benchmark(path: Path = RAW_PATH) -> pd.DataFrame:
    """Read the raw file, keep the useful columns and add our own UTC timestamps."""
    df = pd.read_csv(path)
    df.columns = normalise_columns(df.columns)
    missing = set(COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"{path.name} is missing columns: {sorted(missing)}")
    df = df[list(COLUMNS)].rename(columns=COLUMNS)
    # Dates may arrive as '2021-04-18' or '2021-04-18T00:00:00'; keep the date part only
    df["settlement_date"] = parse_settlement_dates(df["settlement_date"].astype(str).str[:10])
    # Build timestamps ourselves rather than trusting NESO's Datetime column
    df["timestamp_utc"] = settlement_period_to_utc(df["settlement_date"], df["settlement_period"])
    df["published"] = pd.to_datetime(df["published"], utc=True)
    return df


def build_benchmark(path: Path = RAW_PATH) -> pd.DataFrame:
    df = load_benchmark(path)
    n_dupes = df["timestamp_utc"].duplicated().sum()
    if n_dupes:
        logger.warning("Dropping %d duplicate timestamps (keeping the last)", n_dupes)
    df = df.drop_duplicates("timestamp_utc", keep="last").sort_values("timestamp_utc")
    max_periods = {day: expected_periods(day) for day in df["settlement_date"].unique()}
    impossible = df["settlement_period"] > df["settlement_date"].map(max_periods)
    if impossible.any():
        raise ValueError(f"Periods beyond the end of the day:\n{df[impossible].head()}")
    first = ["timestamp_utc", "settlement_date", "settlement_period"]
    return df[first + [c for c in df.columns if c not in first]].reset_index(drop=True)


def main() -> None:
    df = build_benchmark()
    PROCESSED_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(PROCESSED_PATH, index=False)
    logger.info(
        "Saved %d rows (%s to %s) to %s",
        len(df),
        df["timestamp_utc"].min(),
        df["timestamp_utc"].max(),
        PROCESSED_PATH,
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    main()
