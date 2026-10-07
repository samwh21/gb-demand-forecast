"""Combine raw NESO demand CSVs into one clean, timestamped Parquet table."""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from gb_demand_forecast.timeutils import expected_periods, settlement_period_to_utc

logger = logging.getLogger(__name__)

RAW_DIR = Path("data/raw/demand")
PROCESSED_PATH = Path("data/processed/demand.parquet")

# raw column -> clean column name
COLUMNS = {
    "SETTLEMENT_DATE": "settlement_date",
    "SETTLEMENT_PERIOD": "settlement_period",
    "ND": "nd",
    "TSD": "tsd",
    "EMBEDDED_WIND_GENERATION": "embedded_wind",
    "EMBEDDED_SOLAR_GENERATION": "embedded_solar",
}

DATE_FORMATS = ("%Y-%m-%d", "%d-%b-%Y", "%d-%b-%y")  # 2026-01-01, 01-JAN-2018, 01-Jan-23


def parse_settlement_dates(values: pd.Series) -> pd.Series:
    """Parse dates with the first known format that fits every value.

    Explicit formats instead of guessing: a guessing parser read 2026-02-05 as 2 May.
    """
    text = values.astype(str).str.strip()
    for fmt in DATE_FORMATS:
        parsed = pd.to_datetime(text, format=fmt, errors="coerce")
        if parsed.notna().all():
            return parsed
    raise ValueError(f"Unrecognised settlement date format, e.g. {text.iloc[0]!r}")


def load_raw_year(path: Path) -> pd.DataFrame:
    """Read one raw yearly CSV and standardise columns and dates."""
    df = pd.read_csv(path)
    df.columns = df.columns.str.strip().str.upper()
    if "FORECAST_ACTUAL_INDICATOR" in df.columns:  # older files mix in forecasts
        df = df[df["FORECAST_ACTUAL_INDICATOR"].astype(str).str.strip().str.upper() == "A"]
    missing = set(COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"{path.name} is missing columns: {sorted(missing)}")
    df = df[list(COLUMNS)].rename(columns=COLUMNS)
    # NESO has used different date formats across years, so parse each value flexibly
    df["settlement_date"] = parse_settlement_dates(df["settlement_date"])
    return df


def check_period_counts(df: pd.DataFrame) -> None:
    """Fail on impossible periods; warn about incomplete days."""
    counts = df.groupby("settlement_date")["settlement_period"].agg(["max", "count"])
    counts["expected"] = [expected_periods(day) for day in counts.index]
    impossible = counts[counts["max"] > counts["expected"]]
    if not impossible.empty:
        raise ValueError(f"Periods beyond the end of the day on:\n{impossible}")
    incomplete = counts[counts["count"] < counts["expected"]]
    if not incomplete.empty:
        logger.warning("%d incomplete days, e.g.\n%s", len(incomplete), incomplete.head())
    latest = df["timestamp_utc"].max()
    if latest > pd.Timestamp.now(tz="UTC") + pd.Timedelta(days=1):
        raise ValueError(f"Data extends into the future ({latest}) - check date parsing")


def build_demand_table(paths: list[Path]) -> pd.DataFrame:
    """Combine yearly files into one table indexed by UTC period start time."""
    df = pd.concat([load_raw_year(p) for p in paths], ignore_index=True)
    df["timestamp_utc"] = settlement_period_to_utc(df["settlement_date"], df["settlement_period"])
    n_dupes = df["timestamp_utc"].duplicated().sum()
    if n_dupes:
        logger.warning(
            "Dropping %d duplicate timestamps (keeping the latest file's value)", n_dupes
        )
    df = df.drop_duplicates("timestamp_utc", keep="last").sort_values("timestamp_utc")
    check_period_counts(df)
    first_cols = ["timestamp_utc", "settlement_date", "settlement_period"]
    return df[first_cols + [c for c in df.columns if c not in first_cols]].reset_index(drop=True)


def main() -> None:
    paths = sorted(RAW_DIR.glob("demand_*.csv"))
    if not paths:
        raise FileNotFoundError(f"No raw files in {RAW_DIR} - run the ingest step first")
    df = build_demand_table(paths)
    PROCESSED_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(PROCESSED_PATH, index=False)
    logger.info(
        "Saved %d rows (%s to %s) to %s",
        len(df),
        df["timestamp_utc"].min(),
        df["timestamp_utc"].max(),
        PROCESSED_PATH,
    )
    logger.info("Missing values per column:\n%s", df.isna().sum())


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    main()
