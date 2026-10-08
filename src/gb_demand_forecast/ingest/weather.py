"""Download hourly weather for GB population centres from Open-Meteo (raw JSON)."""

import json
import logging
import time
from datetime import date, timedelta
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

RAW_DIR = Path("data/raw/weather")
VARIABLES = ["temperature_2m", "wind_speed_10m", "shortwave_radiation", "cloud_cover"]

# name: (latitude, longitude, approx. built-up-area population in millions - verify vs ONS)
CITIES = {
    "london": (51.507, -0.128, 9.8),
    "birmingham": (52.486, -1.890, 2.6),
    "manchester": (53.480, -2.242, 2.8),
    "leeds": (53.801, -1.549, 1.9),
    "glasgow": (55.864, -4.252, 1.0),
    "newcastle": (54.978, -1.618, 0.8),
    "bristol": (51.455, -2.588, 0.7),
    "cardiff": (51.481, -3.179, 0.5),
}

SOURCES = {
    # What the weather actually was. Useful for EDA, but leaks if used as a model feature.
    "observed": {
        "url": "https://archive-api.open-meteo.com/v1/archive",
        "suffix": "",
        "model": "era5",
        "start_year": 2018,
        "lag_days": 7,  # ERA5 is published with a few days' delay
    },
    # The forecast for each hour as issued 48 hours earlier - available at 09:00 the day before.
    "forecast": {
        "url": "https://previous-runs-api.open-meteo.com/v1/forecast",
        "suffix": "_previous_day2",
        "model": "ecmwf_ifs025",
        "start_year": 2024,
        "lag_days": 0,
    },
}


def build_params(source: str, lat: float, lon: float, start: date, end: date) -> dict:
    """Query parameters for one location and date range."""
    cfg = SOURCES[source]
    return {
        "latitude": lat,
        "longitude": lon,
        "hourly": ",".join(v + cfg["suffix"] for v in VARIABLES),
        "models": cfg["model"],
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "timezone": "UTC",
    }


def fetch_json(client: httpx.Client, url: str, params: dict, retries: int = 3) -> dict:
    """GET with a polite retry when rate-limited (HTTP 429)."""
    for attempt in range(1, retries + 1):
        response = client.get(url, params=params)
        if response.status_code == 429 and attempt < retries:
            logger.warning("Rate limited; waiting 60s (attempt %d/%d)", attempt, retries)
            time.sleep(60)
            continue
        response.raise_for_status()
        return response.json()
    raise RuntimeError("Unreachable")


def download_city_year(
    client: httpx.Client, source: str, city: str, year: int, raw_dir: Path = RAW_DIR
) -> Path | None:
    """Save one city-year of raw JSON. Skips past years already downloaded."""
    cfg = SOURCES[source]
    today = date.today()
    end = min(date(year, 12, 31), today - timedelta(days=cfg["lag_days"]))
    start = date(year, 1, 1)
    if end < start:
        return None
    dest = raw_dir / source / f"{city}_{year}.json"
    if dest.exists() and year < today.year:
        logger.info("Skipping %s (already downloaded)", dest)
        return dest
    lat, lon, _ = CITIES[city]
    payload = fetch_json(client, cfg["url"], build_params(source, lat, lon, start, end))
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload))
    tmp.replace(dest)
    logger.info("Downloaded %s", dest)
    time.sleep(1)  # be gentle with a free API
    return dest


def ingest_weather(sources: tuple[str, ...] = ("observed", "forecast")) -> list[Path]:
    paths = []
    with httpx.Client(timeout=120) as client:
        for source in sources:
            for year in range(SOURCES[source]["start_year"], date.today().year + 1):
                for city in CITIES:
                    path = download_city_year(client, source, city, year)
                    if path:
                        paths.append(path)
    return paths


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    print(f"{len(ingest_weather())} files ready")
