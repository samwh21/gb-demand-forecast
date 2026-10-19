"""Download NESO's day-ahead half-hourly demand forecast performance file (raw, untouched)."""

import logging
from pathlib import Path

import httpx

from gb_demand_forecast.ingest.demand import download, list_resources

logger = logging.getLogger(__name__)

DATASET_ID = "day-ahead-half-hourly-demand-forecast-performance"
RAW_PATH = Path("data/raw/benchmark/neso_day_ahead_performance.csv")


def ingest_benchmark(dest: Path = RAW_PATH) -> Path:
    """Download the dataset's single CSV. Always refreshed: NESO appends to it monthly."""
    with httpx.Client(timeout=120, follow_redirects=True) as client:
        resources = list_resources(client, DATASET_ID)
        csvs = [r for r in resources if r.get("format", "").upper() == "CSV"]
        if len(csvs) != 1:
            raise RuntimeError(f"Expected 1 CSV in {DATASET_ID}, found {len(csvs)}")
        download(client, csvs[0]["url"], dest, overwrite=True)
    return dest


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    print(ingest_benchmark())
