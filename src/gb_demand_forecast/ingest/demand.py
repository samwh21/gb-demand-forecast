"""Download NESO historic half-hourly national demand data (raw, untouched)."""

from __future__ import annotations

import logging
import re
from datetime import date
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

CKAN_BASE = "https://api.neso.energy/api/3/action"
DATASET_ID = "historic-demand-data"
RAW_DIR = Path("data/raw/demand")
YEAR_PATTERN = re.compile(r"(\d{4})")


def parse_year(resource_name: str) -> int | None:
    """Extract the year from a resource name like 'Historic Demand Data 2025'."""
    match = YEAR_PATTERN.search(resource_name)
    return int(match.group(1)) if match else None


def list_resources(client: httpx.Client) -> list[dict]:
    """Ask the NESO CKAN API for every file in the historic demand dataset."""
    response = client.get(f"{CKAN_BASE}/package_show", params={"id": DATASET_ID})
    response.raise_for_status()
    payload = response.json()
    if not payload.get("success"):
        raise RuntimeError(f"NESO API returned an error: {payload}")
    return payload["result"]["resources"]


def select_years(resources: list[dict], start_year: int, end_year: int) -> dict[int, str]:
    """Return {year: download_url} for CSV resources within the year range."""
    selected: dict[int, str] = {}
    for resource in resources:
        year = parse_year(resource.get("name", ""))
        if year is None or not start_year <= year <= end_year:
            continue
        if resource.get("format", "").upper() != "CSV":
            continue
        selected[year] = resource["url"]
    return selected


def download(client: httpx.Client, url: str, dest: Path, overwrite: bool = False) -> bool:
    """Download url to dest. Skips existing files unless overwrite=True."""
    if dest.exists() and not overwrite:
        logger.info("Skipping %s (already downloaded)", dest.name)
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".tmp")
    with client.stream("GET", url) as response:
        response.raise_for_status()
        with tmp.open("wb") as f:
            for chunk in response.iter_bytes():
                f.write(chunk)
    tmp.replace(dest)  # only replace the real file once the download fully succeeded
    logger.info("Downloaded %s", dest.name)
    return True


def ingest_demand(start_year: int = 2018, raw_dir: Path = RAW_DIR) -> list[Path]:
    """Download one raw CSV per year. Always refreshes the current year."""
    current_year = date.today().year
    with httpx.Client(timeout=60, follow_redirects=True) as client:
        urls = select_years(list_resources(client), start_year, current_year)
        missing = sorted(set(range(start_year, current_year + 1)) - urls.keys())
        if missing:
            logger.warning("No CSV found for years: %s", missing)
        paths = []
        for year, url in sorted(urls.items()):
            dest = raw_dir / f"demand_{year}.csv"
            download(client, url, dest, overwrite=(year == current_year))
            paths.append(dest)
    return paths


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    for path in ingest_demand():
        print(path)
