# CLV Predictor

Train a three-stage customer lifetime value model from order-level transaction data. The pipeline predicts whether a customer will purchase in the next 90 days, expected order count and order value for purchasers, and combined 90-day customer revenue. It selects models on a validation period, evaluates on a later test period, and saves reproducible model bundles, metrics, predictions, and a visual report.

## Quick start on Windows

The repository includes the UCI Online Retail II data converted to order-level rows at `data/uci_orders.csv`. This quick start uses SQLite and does not require Docker or PostgreSQL. Run these commands in PowerShell from the repository directory:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe -m pip install --no-deps -e .
Copy-Item .env.example .env
```

The lock file is for Windows with Python 3.12. The editable install registers the `clv` package; `--no-deps` avoids resolving a second set of dependencies after installing the lock.

Initialize the local database, import the included transactions, and run all three training stages:

```powershell
.\.venv\Scripts\python.exe -m clv.cli check
.\.venv\Scripts\python.exe -m clv.cli init-db
.\.venv\Scripts\python.exe -m clv.cli ingest data/uci_orders.csv
.\.venv\Scripts\python.exe -m clv.cli inspect
.\.venv\Scripts\python.exe -m clv.cli train-all --train-cutoff 2010-12-01 --validation-cutoff 2011-04-01 --test-cutoff 2011-09-01 --observation-end 2011-12-10
```

The command prints a JSON summary containing the run ID and output directory. Open the latest run under `artifacts/<run-id>/`. In particular:

- `clv_predictions.csv` contains customer-level actual and predicted 90-day CLV, including cold-start customers.
- `clv_report.png` visualizes aggregate error, customer accuracy, revenue gains, ranked groups, errors, and predicted segments.
- `metrics.json` contains validation and test metrics for the stages and combined CLV. Review `combined.aggregate_error_pct`, `combined.rmse`, and `combined.top_decile_revenue_share`.
- `full_model.joblib` contains the fitted pipeline and parameters for replay. Only load model bundles you trust.

SQLite creates `data/uci.db` automatically. The `.env` file sets `DATABASE_URL` and `ARTIFACT_DIR`; both can be changed there. `DATABASE_URL` may also be overridden for the current PowerShell session with `$env:DATABASE_URL = 'sqlite:///data/another.db'`.

The included dataset uses GBP order totals, and no currency conversion is applied. The sample date boundaries are chosen for this dataset. For your own data, choose cutoffs that leave enough history for training, validation, testing, and the full 90-day test outcome window. `--observation-end` is an exclusive timestamp asserting that source data is complete before that point; do not set it later than your actual source coverage.

## Use your own data

The ingestion format is one row per completed order. See [the data contract](docs/data-model.md). Use stable, globally unique order IDs, a customer ID, order timestamp, positive order total, and one reporting currency. Convert item-level rows into order totals before ingestion. The importer preserves raw input, rejects invalid rows, and makes repeated ingestion of the same source idempotent.

```powershell
.\.venv\Scripts\python.exe -m clv.cli init-db
.\.venv\Scripts\python.exe -m clv.cli ingest path\to\orders.csv
.\.venv\Scripts\python.exe -m clv.cli train-all --train-cutoff YYYY-MM-DD --validation-cutoff YYYY-MM-DD --test-cutoff YYYY-MM-DD --observation-end YYYY-MM-DD
```

The repository also includes the two original UCI Online Retail II item-line files. To convert those files yourself:

```powershell
.\.venv\Scripts\python.exe -m clv.cli convert-uci data/online_retail_09_10.csv data/online_retail_10_11.csv --output data/uci_orders.csv
```

The UCI adapter groups item lines by invoice, computes GBP order totals, and excludes cancellations, missing customer IDs, invalid quantities/prices/dates, and invoice IDs with inconsistent customer or timestamp. It does not infer product categories from descriptions.

## Commands

Run `python -m clv.cli --help` for the full command list. Common commands using the project interpreter:

```powershell
.\.venv\Scripts\python.exe -m clv.cli check       # Check database and package readiness
.\.venv\Scripts\python.exe -m clv.cli init-db    # Apply database migrations
.\.venv\Scripts\python.exe -m clv.cli sample     # Generate deterministic synthetic orders
.\.venv\Scripts\python.exe -m clv.cli inspect    # Count customers, raw rows, orders, and revenue
.\.venv\Scripts\python.exe -m clv.cli features --cutoff 2010-12-01 --observation-end 2011-12-10
.\.venv\Scripts\python.exe -m clv.cli train --train-cutoff 2010-12-01 --validation-cutoff 2011-04-01 --test-cutoff 2011-09-01 --observation-end 2011-12-10
.\.venv\Scripts\python.exe -m clv.cli train-all --train-cutoff 2010-12-01 --validation-cutoff 2011-04-01 --test-cutoff 2011-09-01 --observation-end 2011-12-10
```

`train` runs the stage-one purchase classifier. `train-all` runs the classifier, conditional count and order-value regressors, and combined CLV pipeline. It compares available model candidates and selects each stage using validation data. Calibration options and defaults are shown by `train-all --help` and described in [ordered drift results](docs/ordered-drift-results.md). Reported scores depend on the data and date split; the 0.75 ROC-AUC target is measured, not enforced. A score on synthetic data is not evidence of business performance.

Repeating ingestion reuses source records. Snapshots are immutable, and each training command creates a new model run. The demo command migrates the database, generates synthetic data, and runs stage one:

```powershell
.\.venv\Scripts\python.exe -m clv.cli demo
```

## Optional PostgreSQL

The default setup uses SQLite. To use PostgreSQL instead, start Docker Desktop, then run:

```powershell
docker compose up -d --wait
$env:DATABASE_URL = 'postgresql+psycopg://clv:clv_local@localhost:55432/clv'
.\.venv\Scripts\python.exe -m clv.cli init-db
.\.venv\Scripts\python.exe -m clv.cli ingest data/uci_orders.csv
.\.venv\Scripts\python.exe -m clv.cli train-all --train-cutoff 2010-12-01 --validation-cutoff 2011-04-01 --test-cutoff 2011-09-01 --observation-end 2011-12-10
```

The compose service binds PostgreSQL to loopback port 55432 and persists its data in a Docker volume. The credentials in `.env.example` are for local development only. The `DATABASE_URL` environment variable takes precedence over `.env`; set it in the same PowerShell window where you run the CLI.

## Optional local inspector

The read-only API and React inspector show model comparisons and paginated stage-one customer probabilities. In one terminal:

```powershell
.\.venv\Scripts\python.exe -m uvicorn clv.api:app --host 127.0.0.1 --port 8000
```

In another terminal:

```powershell
Set-Location frontend
npm ci
npm run dev
```

Open http://127.0.0.1:5173. API documentation is at http://127.0.0.1:8000/docs. These development endpoints are unauthenticated; keep them bound to loopback. Training is available through the CLI; no retraining HTTP endpoint is exposed.

## Configuration and scope

- `DATABASE_URL`: SQLAlchemy connection URL; defaults to `sqlite:///data/clv.db` if unset.
- `ARTIFACT_DIR`: output directory for training runs; defaults to `artifacts` if unset.
- `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`: local Compose database credentials and database name.
- `S3_ENDPOINT_URL`, `S3_BUCKET`, `SCHEDULER_ENABLED`: reserved placeholders; S3 uploads and scheduled jobs are not implemented.

The current scoring path evaluates labeled historical snapshots. Future-date unlabeled batch scoring and automated scheduling are not implemented.

## Project layout

- `clv/data.py`: raw preservation, row rejection, and idempotent ingestion.
- `clv/features.py`: as-of features and 90-day labels.
- `clv/ml.py`: temporal model experiments, selection, and saved artifacts.
- `clv/cli.py`: reproducible local commands.
- `clv/api.py`: read-only stage-one inspection API.
- `migrations/`: database schema migrations.
- `frontend/`: React inspector.
- `tests/`: unit and integration checks.
