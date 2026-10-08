"""Combine raw Open-Meteo files into population-weighted, half-hourly GB weather."""

import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from gb_demand_forecast.ingest.weather import CITIES, RAW_DIR, SOURCES

logger = logging.getLogger(__name__)

PROCESSED_DIR = Path("data/processed")
HOUR_ENDING = ["shortwave_radiation"]  # values averaged over the preceding hour


def parse_payload(payload: dict, suffix: str) -> pd.DataFrame:
    """Turn one Open-Meteo response into an hourly UTC DataFrame with clean column names."""
    hourly = pd.DataFrame(payload["hourly"])
    hourly["time"] = pd.to_datetime(hourly["time"], utc=True)
    hourly.columns = [c.removesuffix(suffix) for c in hourly.columns]
    return hourly.set_index("time")


def load_city(source: str, city: str, raw_dir: Path = RAW_DIR) -> pd.DataFrame:
    suffix = SOURCES[source]["suffix"]
    files = sorted((raw_dir / source).glob(f"{city}_*.json"))
    frames = [parse_payload(json.loads(f.read_text()), suffix) for f in files]
    df = pd.concat(frames)
    return df[~df.index.duplicated(keep="last")].sort_index()


def weighted_average(frames: dict[str, pd.DataFrame], weights: dict[str, float]) -> pd.DataFrame:
    """Population-weighted mean across cities, re-weighting when a city has a missing value."""
    stacked = pd.concat(frames, names=["city", "time"])
    w = stacked.index.get_level_values("city").map(weights).to_numpy(dtype=float)[:, None]
    values = stacked.to_numpy(dtype=float)
    present = ~np.isnan(values)
    num = pd.DataFrame(
        np.where(present, values * w, 0.0), index=stacked.index, columns=stacked.columns
    )
    den = pd.DataFrame(np.where(present, w, 0.0), index=stacked.index, columns=stacked.columns)
    return num.groupby(level="time").sum() / den.groupby(level="time").sum().replace(0, np.nan)


def _interpolate_onto(data: pd.DataFrame, index: pd.DatetimeIndex) -> pd.DataFrame:
    """Time-interpolate onto a new index, filling only short gaps (about an hour)."""
    combined = data.reindex(data.index.union(index))
    return combined.interpolate(method="time", limit=2, limit_area="inside").reindex(index)


def to_half_hourly(df: pd.DataFrame) -> pd.DataFrame:
    """Hourly -> half-hourly. Hour-ending averages are re-centred on the middle of their hour."""
    index = pd.date_range(df.index.min(), df.index.max(), freq="30min")
    instant = df.drop(columns=[c for c in HOUR_ENDING if c in df.columns])
    out = _interpolate_onto(instant, index)
    for col in HOUR_ENDING:
        if col in df.columns:
            centred = df[[col]].copy()
            centred.index = centred.index - pd.Timedelta(minutes=30)
            out[col] = _interpolate_onto(centred, index)[col].clip(lower=0)
    out.index.name = "timestamp_utc"
    return out


def build_weather_table(source: str) -> pd.DataFrame:
    frames = {city: load_city(source, city) for city in CITIES}
    weights = {city: pop for city, (_, _, pop) in CITIES.items()}
    hourly = weighted_average(frames, weights).dropna(how="all")
    logger.info("%s: first hour with data %s", source, hourly.index.min())
    return to_half_hourly(hourly)


def main() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    for source in SOURCES:
        df = build_weather_table(source)
        path = PROCESSED_DIR / f"weather_{source}.parquet"
        df.reset_index().to_parquet(path, index=False)
        logger.info(
            "%s: %d rows (%s to %s) -> %s", source, len(df), df.index.min(), df.index.max(), path
        )
        logger.info("Missing values:\n%s", df.isna().sum())


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    main()
