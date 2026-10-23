# CLV Predictor

The data foundation, purchase classifier, conditional count and order-value regressors, combined 90-day CLV, and customer segments are implemented. The inspection screen displays classifier probabilities. Current-date scoring and production deployment remain future work.

## Quick start — PowerShell

Run from `C:\CLV-Predictor`:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe -m pip install --no-deps -e .
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m clv.cli demo
.\.venv\Scripts\python.exe -m pytest -q
```

The demo migrates the database, generates deterministic synthetic orders, ingests them, creates three snapshots, compares classifiers, and saves results. Repeating it reuses the source ingestion and immutable snapshots, and creates a new model run. Use a separate database for real data: the demo does not clear existing data.

To install from the manifest instead of the environment lock: `python -m pip install -e ".[models,dev]"`. The lock records the tested Windows/Python 3.12 environment; other platforms may resolve different wheels.

## Test each layer

```powershell
# Dependency readiness and database connection
.\.venv\Scripts\python.exe -m clv.cli check

# Database schema and known sample input
.\.venv\Scripts\python.exe -m clv.cli init-db
.\.venv\Scripts\python.exe -m clv.cli sample
.\.venv\Scripts\python.exe -m clv.cli ingest data/sample.csv
.\.venv\Scripts\python.exe -m clv.cli inspect

# Inspect customer-level feature and label CSVs side by side
.\.venv\Scripts\python.exe -m clv.cli features --cutoff 2025-07-01 --observation-end 2025-10-01

# Train using non-overlapping 90-day outcome windows
.\.venv\Scripts\python.exe -m clv.cli train --train-cutoff 2025-01-01 --validation-cutoff 2025-04-01 --test-cutoff 2025-07-01 --observation-end 2025-10-01
```

Outputs are in `data/inspection/` and `artifacts/<run-id>/`. Each run includes a serialized preprocessing/model bundle, validation comparisons and final test metrics (`metrics.json`), features and labels for all three periods, and predictions. Stage-specific PNG reports are not generated. Only load model bundles you trust.

ROC-AUC, average precision (reported as PR-AUC), Brier score, precision/recall at 0.5, and top-decile purchaser lift are reported. Undefined single-class metrics are null. The 0.75 ROC-AUC target is measured, not enforced. A synthetic-data score is not evidence of business performance. Stage-1 lift ranks purchasers; revenue lift will be evaluated with the complete CLV pipeline.

## Open the local inspector

In one terminal:

```powershell
.\.venv\Scripts\python.exe -m uvicorn clv.api:app --host 127.0.0.1 --port 8000
```

In another:

```powershell
Set-Location frontend
npm.cmd ci
npm.cmd run dev
```

Open http://127.0.0.1:5173 for model comparisons and paginated customer probabilities. API documentation: http://127.0.0.1:8000/docs. Endpoints: `/health`, `/customers`, `/model/status`, `/stage1/predictions`. These development endpoints are unauthenticated; serve only on loopback. Training is available through the CLI; no retraining HTTP endpoint is exposed yet.

## PostgreSQL

Start Docker Desktop in **Linux containers** mode. Wait for its engine to show as running, then open PowerShell in `C:\CLV-Predictor` and run:

```powershell
docker version
docker compose config --quiet
docker compose up -d --wait
docker compose ps
docker compose exec db pg_isready -U clv -d clv
$env:DATABASE_URL='postgresql+psycopg://clv:clv_local@localhost:55432/clv'
.\.venv\Scripts\python.exe -m clv.cli init-db
.\.venv\Scripts\python.exe -m clv.cli check
.\.venv\Scripts\python.exe -m clv.cli ingest data/uci_orders.csv
.\.venv\Scripts\python.exe -m clv.cli inspect
.\.venv\Scripts\python.exe -m clv.cli train --train-cutoff 2010-12-01 --validation-cutoff 2011-04-01 --test-cutoff 2011-09-01 --observation-end 2011-12-10
```

To train **all three stages** and save the combined 90-day CLV predictions, use `train-all` with the same cutoffs. Run `init-db` first when upgrading an existing database so the stage-2/3 registry columns are added:

```powershell
.\.venv\Scripts\python.exe -m clv.cli init-db
.\.venv\Scripts\python.exe -m clv.cli train-all --train-cutoff 2010-12-01 --validation-cutoff 2011-04-01 --test-cutoff 2011-09-01 --observation-end 2011-12-10
```

The command compares classification candidates (constant, logistic, random forest, LightGBM, CatBoost, XGBoost), conditional count candidates (mean, Poisson, negative binomial, boosted Poisson), and conditional order-value candidates (mean, Gamma, boosted Gamma, log-value regressors). Each stage selects its winner on the validation period. Its final metrics, full model bundle, and `clv_predictions.csv` are saved under `artifacts/<run-id>/`; the database tables `model_runs` and `clv_predictions` hold the same run. Inspect `combined.aggregate_error_pct`, `combined.rmse`, and `combined.top_decile_revenue_share` in `metrics.json`. Cold-start customers use a training-only cohort CLV estimate and are flagged in the CSV.

`data/uci_orders.csv` is already generated from both UCI source files. The `DATABASE_URL` assignment is scoped to this PowerShell window. To use the dashboard against PostgreSQL, stop the running API and start it in this same window:

```powershell
.\.venv\Scripts\python.exe -m uvicorn clv.api:app --host 127.0.0.1 --port 8000
```

The PostgreSQL integration test inserts sample data. Give it its own database so it cannot mix with the imported UCI orders:

```powershell
docker compose exec db createdb -U clv clv_test
$env:TEST_POSTGRES_URL='postgresql+psycopg://clv:clv_local@localhost:55432/clv_test'
.\.venv\Scripts\python.exe -m pytest tests/test_postgres.py -q
```

This project uses host port **55432** because another local PostgreSQL container occupies 5432. If a previous PowerShell window still has `DATABASE_URL` set to port 5432, set it again to 55432 before running the app. If Docker reports a named-pipe permission error, check that Docker Desktop has finished starting and that your account can access its engine. Docker persists database contents in a named volume; `docker compose stop` retains records. The initial migration has a frozen schema copy in `migrations/schema_v1.py`; future schema changes require a new migration.

## Bring your own CSV

For the two UCI Online Retail II CSV files in `data/`, convert the item lines first and use a separate database:

```powershell
.\.venv\Scripts\python.exe -m clv.cli convert-uci data/online_retail_09_10.csv data/online_retail_10_11.csv --output data/uci_orders.csv
$env:DATABASE_URL='sqlite:///data/uci.db'
.\.venv\Scripts\python.exe -m clv.cli init-db
.\.venv\Scripts\python.exe -m clv.cli ingest data/uci_orders.csv
.\.venv\Scripts\python.exe -m clv.cli inspect
.\.venv\Scripts\python.exe -m clv.cli train --train-cutoff 2010-12-01 --validation-cutoff 2011-04-01 --test-cutoff 2011-09-01 --observation-end 2011-12-10
```

The UCI adapter groups item lines by invoice, computes GBP order totals, and excludes cancellations, missing customer IDs, invalid quantities/prices/dates, and invoice IDs with inconsistent customer or timestamp. No category is inferred from product descriptions.

See [the data contract](docs/data-model.md). Use one row per completed order, stable globally unique order IDs, positive order totals, one reporting currency, and sufficient history for three dated snapshots plus a complete final 90-day horizon. Convert item-level datasets to order-level totals before ingestion.

`--observation-end` is your assertion that all source purchases before this exclusive instant are available. It cannot be inferred reliably from the last purchase date. The loader and snapshot builder cannot detect missing source files. Do not supply an observation end beyond your actual coverage.

The current scoring path evaluates labeled snapshots. A future-date unlabeled batch-scoring command and automated scheduling will follow with later pipeline stages. APScheduler and S3 configuration placeholders are prepared, but scheduled jobs and S3 uploads are not enabled.

## Project layout

- `clv/data.py`: raw preservation, row rejection, idempotent ingestion.
- `clv/models.py`: relational schema and constraints.
- `clv/features.py`: as-of features and 90-day labels.
- `clv/ml.py`: temporal experiment, model selection, saved artifacts.
- `clv/cli.py`: reproducible local commands.
- `clv/api.py`: read-only stage-1 inspection API.
- `frontend/`: React, Tailwind, and Recharts inspector.
- `tests/`: fixtures, leakage boundaries, persistence, API and PostgreSQL checks.

## Combined CLV visual report

`train-all` creates `clv_report.png` in its run folder. It compares final 90-day CLV with observed test revenue: aggregate totals and error, customer accuracy, cumulative revenue gains, average revenue by ranked group, customer errors, and revenue by predicted segment. All test customers, including cold-start customers, are included. Currency units follow the input data; no conversion is applied. The scatter and error axes use symmetric log scales to retain zero values and make large outliers visible.

`clv_revenue_gains.csv` and `clv_rank_groups.csv` supply the ranking chart data. Stage-specific metrics and predictions remain available as data files. Historical PNGs are archived under `legacy_stage1/` so only the combined report appears at the top of full-run folders.

## Revenue accuracy improvements

The historical proposal first pass implemented: stage 3 selects by validation MAE; stage 2 retains validation RMSE selection. Final CLV applies a validation-fitted revenue ratio saved in `full_model.joblib` as `revenue_calibration`. Test labels never fit this correction. `metrics.json` includes explicit `stage1`, `stage2`, `stage3`, `combined_raw`, `combined`, `combined_validation`, and `cohort_test` sections. Stage metrics report actual/predicted means; cohorts report customer shares and revenue accuracy. That historical run used `cold_start_rate` for fallback purchase probability, not customer share; new runs use the explicit names described below. See [first-pass results](docs/pipeline-improvement-results.md) for the measured gains, calibration limitations, and remaining experiments.

## Cold-start reporting and calibration experiments

New `train-all` runs default to a training-fitted 99th-percentile revenue cap, followed by validation-fitted isotonic calibration separately for cold-start and established customers. Calibration is always fitted after capping. The cap is not reapplied to calibrated output. CLI controls: `--calibration none|scalar|isotonic`, `--cap-quantile 0.99`, `--no-revenue-cap`, and `--shared-calibration`.

New public metrics and bundles use `cold_start_purchase_probability`; metrics separately expose `cold_start_population_share` and a dedicated `cold_start` revenue-accuracy block. Existing bundles with the historical field can still predict. Metrics expose `combined_raw`, `combined_capped`, and final `combined`; `clv_evaluation.csv` records these three predictions plus actual revenue per customer. Full bundles save all cap and cohort calibration parameters, including isotonic thresholds.

Follow [manual commands and comparisons](docs/manual-ml-verification.md) to train and verify the new proposal yourself. The previous run did not contain outlier capping, despite that assumption in the proposal. No new UCI performance claim is made for these experimental defaults.

## Next pass: segmented cold-start fallback

Current `train-all` defaults disable capping and revenue calibration. Cold-start CLV is now estimated from training-only first-order-value quartile buckets, shrunk toward the overall training fallback. Full-run feature exports contain auxiliary `first_order_value`; full bundles save `cold_start_fallback` for replay. New metrics include `cold_start_bucket_test` and `cohort_validation`, plus raw/capped/calibrated established-cohort comparisons in `cohort_test`.

`--cap-quantile` now fits a cap from validation revenue (e.g. `0.99` or `0.999`). `--calibration` controls cold-start calibration; `--established-calibration` independently controls established calibration. Both default to `none`; shared calibration remains available as an explicit experiment. This supersedes the earlier defaults documented above. Follow the updated manual verification guide for commands. No new full-data score is claimed before running these experiments.

## Ordered classifier and count drift pass

Selected classifiers now use validation-fitted sigmoid recalibration by default. Cold-start fallback defaults to two first-order-value buckets with prior strength 50. Revenue calibration and cap stay off. Conditional count correction is opt-in (`--count-calibration scalar`). See [ordered results and commands](docs/ordered-drift-results.md) for the staged comparison, including the revenue/MAE tradeoff and saved-model replay command.
