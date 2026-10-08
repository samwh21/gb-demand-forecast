# GB Day-Ahead Electricity Demand Forecast – Design

## 1. Problem
Great Britain's electricity system operator (NESO) must balance supply and demand
every half hour. Accurate day-ahead demand forecasts reduce balancing costs and risk.
This project builds a service that forecasts **National Demand (ND)** for each of the
48 half-hour settlement periods of **tomorrow**, issued by **09:00 UK time today** –
the same setup as NESO's own day-ahead forecast.

## 2. Users and decisions supported
- Primary (hypothetical): an energy trader or balancing analyst deciding tomorrow's
  positions.
- Output: 48 point forecasts plus an 80% prediction interval, via API and dashboard.

## 3. Success metrics
- **Primary:** Mean Absolute Percentage Error (MAPE) over a held-out backtest period,
  compared against NESO's published day-ahead forecast.
- **Secondary:** MAE (MW), error at the daily peak, 80% interval coverage
  (target: 78–82%).
- **Minimum bar:** clearly beat a seasonal-naive baseline (same period, one week earlier).

## 4. Data sources
| Source | What | Notes |
|---|---|---|
| NESO Historic Demand Data | Half-hourly ND, 2018 onwards | CKAN API |
| NESO Demand Data Update | Recent outturn | For daily updates |
| NESO Day Ahead Half Hourly Demand Forecast Performance | NESO's forecasts + errors | Benchmark |
| Open-Meteo Historical Forecast API | Archived weather forecasts | Used for training to avoid leakage |
| UK bank holidays (`holidays` package) | Calendar features | |

## 5. Key constraint: no information from the future
Every feature must be available at 09:00 on the issue day:
- Weather features use **forecasts as issued**, not observed weather.
- Demand lags use only data published before the issue time (e.g. same period
  2 and 7 days before the target).
- The backtest simulates this exactly and is unit-tested for leakage.

## 6. Approach (high level)
1. Ingest and validate data (Pandera schemas).
2. Backtest baselines, then LightGBM with calendar, lag and weather features.
3. Quantile models for prediction intervals.
4. Track experiments and register models in MLflow.
5. Serve via FastAPI in Docker; schedule daily forecasts and weekly retraining with Airflow.
6. Monitor accuracy and data drift (Evidently); retrain via champion/challenger.

## 7. Out of scope
- Regional or grid-supply-point forecasts.
- Intraday (same-day) forecasting.
- Price forecasting.

## 8. Risks and open questions
- 2020 lockdown distorts demand – exclude or flag?
- Clock-change days have 46/50 settlement periods – timestamps must handle these.
- NESO changed its data source in 2026 – check for discontinuities.
- Archived weather forecasts only go back to ~2021/22 – may limit the training window.
- Yearly historic files lag by ~4 weeks; recent data must come from the Demand Data Update dataset.
- Leak-free (day-2) forecast weather starts 5 February 2024, giving about 2⅔ years of honest training data.
- Leak-free forecast weather: temperature and wind from 5 Feb 2024, radiation from 7 Mar 2024. Modelling period starts 8 Mar 2024.
- Cloud cover forecasts missing 17–22 Apr 2026 (archive gap); left as missing, not filled from observations to avoid leakage.

## 9. Milestones
- [ ] Data ingestion + validation
- [ ] Backtest framework + baselines
- [ ] LightGBM model beating seasonal naive
- [ ] API + Docker
- [ ] Airflow scheduling + retraining
- [ ] Monitoring + CI/CD
- [ ] Dashboard, deployment, write-up
