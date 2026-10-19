# Data dictionary

What every column in the processed data means, where it comes from, and whether it can be
used by the model.

**The availability rule.** The forecast is issued at **09:00 UK time on day D** for every
half-hour of **day D+1**. A column can only be a model input if its value for the target
time would be known at 09:00 on day D. Anything else is either the target or leakage.

## Conventions

- **Time:** every table is indexed by `timestamp_utc`, the **start** of a half-hour period,
  in UTC. UTC never jumps, so clock-change days need no special handling downstream.
  Convert to `Europe/London` only for display.
- **Settlement periods:** period 1 starts at UK local midnight; each period is 30 minutes
  of elapsed time. Days have 48 periods, 46 when clocks go forward (last Sunday in March)
  and 50 when they go back (last Sunday in October).
- **Power:** MW, averaged over the half-hour.

## Demand: `data/processed/demand.parquet`

Source: NESO Data Portal, *Historic Demand Data* (one CSV per year), 2018 onwards.
Licence: NESO Open Data Licence.

| Column | Meaning | Units | Use in the model |
|---|---|---|---|
| `timestamp_utc` | Start of the half-hour period | UTC datetime | Index / join key |
| `settlement_date` | UK settlement day the period belongs to | date | Calendar features |
| `settlement_period` | Period number within the day (1-46/48/50) | integer | Calendar features |
| `nd` | **National Demand.** Metered generation from transmission-connected power stations, excluding station load, pumped-storage pumping and interconnector exports. Approximately the demand GB homes and businesses draw from the national grid. | MW | **Target.** Lagged values (e.g. same period 2 and 7 days earlier) are allowed as features |
| `tsd` | **Transmission System Demand.** ND plus station load, pumped-storage pumping and interconnector exports: the total the transmission system supplies. | MW | **Not used.** Same-time value is leakage; lagged values duplicate lagged ND |
| `embedded_wind` | NESO's estimate of output from wind farms connected to local distribution networks (invisible to the transmission network, so it reduces ND) | MW | Same-time value is leakage. Weather (wind speed) is used as a proxy; NESO's embedded wind *forecasts* are a possible future feature |
| `embedded_solar` | NESO's estimate of output from distribution-connected solar, including rooftop panels. Causes the midday summer dip in ND. | MW | As `embedded_wind`; radiation is the proxy |

Neither ND nor TSD includes embedded generation: when rooftop solar supplies a home
directly, that demand never reaches the national grid.

## Weather: `data/processed/weather_observed.parquet` and `weather_forecast.parquet`

Source: Open-Meteo (CC BY 4.0). Population-weighted average of 8 GB cities (London,
Birmingham, Manchester, Leeds, Glasgow, Newcastle, Bristol, Cardiff), converted from hourly
to half-hourly. Both tables have the same columns.

| Column | Meaning | Units | Notes |
|---|---|---|---|
| `temperature_2m` | Air temperature **2 m above ground**, the standard thermometer height, roughly where people and buildings experience it | °C | Instantaneous value; interpolated to half-hours |
| `wind_speed_10m` | Wind speed **10 m above ground**, the standard anemometer height, clear of hedges and buildings | km/h | Instantaneous; interpolated |
| `shortwave_radiation` | Sunlight energy reaching a horizontal surface (global horizontal irradiance) | W/m² | **Average over the preceding hour**, labelled at the hour's end. Re-centred 30 min earlier before interpolating |
| `cloud_cover` | Share of the sky covered by cloud, all levels | % | Instantaneous; interpolated |

### The two weather tables

| Table | What it is | API / model | Coverage | Use |
|---|---|---|---|---|
| `weather_observed` | What the weather actually was | Historical Weather API, ERA5 reanalysis | 2018 to ~7 days ago | EDA and an upper-bound comparison only. **Leakage if used as a model feature** |
| `weather_forecast` | The forecast for each hour as issued about **48 hours earlier** (`_previous_day2`) | Previous Runs API, ECMWF IFS 0.25° | Temperature, wind, cloud from 5 Feb 2024; radiation from 7 Mar 2024 | **Model features** |

Why 48 hours: the latest target time (23:30 on D+1) is 38.5 hours after the 09:00 issue time,
so a 24-hour-old forecast for it would not yet exist. A 48-hour-old forecast always does.

## Known data issues

| Issue | Handling |
|---|---|
| NESO yearly files use three date formats (`01-JAN-2018`, `01-Jan-23`, `2025-01-01`) | Parsed with explicit per-file formats. A guessing parser silently swapped day and month in ISO dates |
| Yearly demand files lag about 4 weeks | Recent data to come from NESO's *Demand Data Update* dataset (daily pipeline) |
| NESO changed its data source in 2026 | Check for a discontinuity in ND during EDA |
| Forecast weather starts Feb 2024; radiation Mar 2024 | Modelling period starts 8 March 2024 |
| Forecast cloud cover missing 17-22 Apr 2026 | Left as missing; not filled from observations (leakage). Could be filled from `_previous_day3` |
| Day-2 forecast temperature MAE vs observed: 0.7°C (GB weighted average) | The accuracy cost of using honest features |

## NESO benchmark: `data/processed/neso_benchmark.parquet`

Source: NESO Data Portal, *Day Ahead Half Hourly Demand Forecast Performance* (single CSV,
updated monthly), April 2021 onwards. The forecast to beat.

| Column | Meaning | Units |
|---|---|---|
| `timestamp_utc`, `settlement_date`, `settlement_period` | As in the demand table; built from date + period, not NESO's `Datetime` column | |
| `neso_forecast` | NESO's published day-ahead National Demand forecast | MW |
| `neso_outturn` | NESO's actual National Demand, from a slightly different measurement than `nd` | MW |
| `triad_avoidance` | Estimated demand reduction by users avoiding Triad charging peaks (313 non-zero rows) | MW |
| `published` | When the forecast was published. Timezone convention inconsistent (see below) | approx. |

**Validation (Oct 2026):**
- Timestamps align with the demand table: median |outturn − nd| is 38 MW unshifted vs
  450–950 MW when shifted by ±1–2 half-hours.
- `neso_outturn` is on average ~30 MW below `nd` (median absolute gap 0.15%), stable across
  years: a measurement difference, not a misalignment.
- All forecasts are published the day before the target date. Published hours read 08 in GMT
  months and 09 in BST months, the reverse of genuine UTC, so treat `published` as approximate
  (morning of the day before, ~08:00–10:00 UK time). Matches our 09:00 issue time.

**Scoring:** NESO and our model are both scored against our `nd`. NESO's MAPE is 2.50% against
`nd` vs 2.51% against its own outturn, so the choice doesn't affect the benchmark.

**NESO day-ahead MAPE vs `nd`:** 2021 2.13% · 2022 2.34% · 2023 2.33% · 2024 2.41% ·
2025 2.69% · 2026 (to Sep) 3.26% · overall 2.50%.
