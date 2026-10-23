# Manual verification of the cold-start reporting proposal

The current defaults use a training-fitted cold-start fallback segmented by first-order-value quartiles, with shrinkage toward the overall training fallback (10 prior customers per bucket). Bucket boundaries and estimates never use validation/test outcomes. Acquisition channel is unavailable in the current input. The classifier features are unchanged; full-run feature exports include an auxiliary `first_order_value` for saved-model replay.

Established revenue calibration and capping are disabled by default. Optional caps are now fitted on validation revenue, followed by any requested calibration. `--calibration` controls cold-start calibration (or the shared calibrator with `--shared-calibration`); `--established-calibration` independently controls established customers. With shared calibration, the cohort-specific option is ignored.

## 1. Prepare and check

Run in PowerShell. Use the existing UCI SQLite database so the comparison uses the same data and dates. These commands do not change `.env` and do not involve PostgreSQL.

```powershell
Set-Location C:\CLV-Predictor
$env:DATABASE_URL = 'sqlite:///data/uci.db'
$env:ARTIFACT_DIR = 'artifacts'
$env:OMP_NUM_THREADS = '1'
$env:OPENBLAS_NUM_THREADS = '1'
$env:MKL_NUM_THREADS = '1'

.\.venv\Scripts\python.exe -m clv.cli init-db
.\.venv\Scripts\python.exe -m clv.cli check
.\.venv\Scripts\python.exe -m clv.cli ingest data/uci_orders.csv
.\.venv\Scripts\python.exe -m clv.cli inspect
.\.venv\Scripts\python.exe -m pytest tests/test_revenue.py tests/test_reports.py tests/test_foundation.py tests/test_uci.py -q
```

Ingestion reuses the existing source batch when the file is unchanged. Check the package status for LightGBM, CatBoost, XGBoost and statsmodels if reproducing the prior candidate comparison. Stop and resolve an error before continuing. The existing HTTP test is excluded because Windows socket-pair initialization stalled in this environment; full training and report tests do not depend on it.

## 2. Train the new pipeline

```powershell
.\.venv\Scripts\python.exe -m clv.cli train-all `
  --train-cutoff 2010-12-01 `
  --validation-cutoff 2011-04-01 `
  --test-cutoff 2011-09-01 `
  --observation-end 2011-12-10 `
  --calibration none `
  --no-revenue-cap |
  Out-File -Encoding utf8 data/manual-clv-result.json

if ($LASTEXITCODE -ne 0) { throw 'Training failed; inspect the error above.' }
$run = Get-Content data/manual-clv-result.json -Raw | ConvertFrom-Json
$run.artifact_path
```

This creates a new run; previous model files and metrics are retained. Both cohort calibrators are disabled in this recommended run. Cold-start threshold is unchanged: fewer than two historical orders OR less than 30 days tenure. Customers with no pre-cutoff orders are absent from this transaction-based input.

## 3. Inspect the scores, corrections and PNG

```powershell
$run.combined_raw | Format-List
$run.combined_capped | Format-List
$run.combined | Format-List
$run.cold_start | Format-List
$run.stage1.test | Format-List
$run.stage2.test | Format-List
$run.stage3.test | Format-List
$run.revenue_calibration | ConvertTo-Json -Depth 10

Start-Process (Join-Path $run.artifact_path 'clv_report.png')
Import-Csv (Join-Path $run.artifact_path 'clv_evaluation.csv') | Select-Object -First 10 | Format-Table

$errorPct = $run.combined.aggregate_error_pct
if ($null -eq $errorPct) {
  'Revenue target unavailable: actual revenue is zero.'
} else {
  'Within +/-15% revenue target: ' + ([Math]::Abs($errorPct) -le 15)
}
```

`combined_raw`, `combined_capped`, and `combined` isolate the effects of each step. `cold_start` includes population count/share, fallback purchase probability, observed purchase rate, revenue totals, error and MAE. Stage 1 reports all-customer probabilities and established-customer metrics separately; stages 2–3 report conditional metrics for established purchasers. Zero actual revenue produces a null percentage error, not a zero error.

## 4. Compare with the preceding run

```powershell
$baseline = Get-Content artifacts/8c8abc83223443579171af55e02c54a5/metrics.json -Raw | ConvertFrom-Json
@(
  [pscustomobject]@{ Run='Previous'; ErrorPct=$baseline.combined.aggregate_error_pct; MAE=$baseline.combined.mae; RMSE=$baseline.combined.rmse }
  [pscustomobject]@{ Run='New'; ErrorPct=$run.combined.aggregate_error_pct; MAE=$run.combined.mae; RMSE=$run.combined.rmse }
) | Format-Table -AutoSize
```

Keep the candidate set, feature version, dataset fingerprint, snapshots and dates identical for a comparable result. The previous calibrated error is -24.30%, MAE 411.42, RMSE 2015.66. Check all three quantities, along with cold-start errors and ranking performance. Improvements are not guaranteed by calibration.

For controlled comparisons, repeat the training command with these options instead; each invocation creates a new run. Save its JSON under a different filename if retaining all command outputs.

| Experiment | Options |
|---|---|
| Previous behavior: shared scalar, no cap | `--calibration scalar --no-revenue-cap --shared-calibration` |
| Raw composition | `--calibration none --no-revenue-cap` |
| Cap only | `--calibration none --cap-quantile 0.99` |
| Cold-start isotonic only, no cap | `--calibration isotonic --no-revenue-cap` |
| Established scalar only, no cap | `--calibration none --established-calibration scalar --no-revenue-cap` |
| Both cohorts isotonic, no cap | `--calibration isotonic --established-calibration isotonic --no-revenue-cap` |
| Higher validation cap only | `--calibration none --cap-quantile 0.999` |
| Shared isotonic with cap | `--calibration isotonic --cap-quantile 0.99 --shared-calibration` |

Repeated comparisons on this historical test make it a development diagnostic. A fresh later holdout is needed before claiming business generalization. Historical runs retain their original metric schema; only new runs contain the dedicated cold-start block and explicit field names.

## Next-pass comparisons

Inspect `$run.cohort_test.established.raw`, `.capped`, and `.calibrated` for established-only comparisons. `cold_start_fallback` records training bucket edges, estimates, counts and shrinkage; `cold_start_bucket_test` reports observed per-bucket test accuracy. `cohort_validation` reports calibration fit diagnostics, not independent performance. `cold_start_clv` is retained as the historical flat baseline; new cold-start predictions use `cold_start_fallback` instead. The saved full bundle contains the bucket configuration.

No full-data improvement is claimed before the manual run. Use a fresh holdout for eventual evaluation after these repeated development comparisons. The 4.7-point established-cohort advantage is prior diagnostic evidence, not an automatic test-set selection rule in the new code.
