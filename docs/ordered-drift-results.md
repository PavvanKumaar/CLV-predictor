# Ordered drift pass

Source: saved full run `cf0f9ba56a8441abbb9e99767fb5cad0`, same train/validation/test exports and fitted model candidates. Corrections fit validation only; bucket estimates fit training only. This is an ordered ablation, not a fresh independent holdout or an automatic model selection procedure.

| Step | Revenue error % | MAE | RMSE |
|---|---:|---:|---:|
| Raw baseline: four buckets, prior 10 | -20.69 | 411.62 | 1987.80 |
| 1: selected classifier + validation sigmoid | -20.43 | 412.52 | 1990.47 |
| 2: two cold buckets, prior 50 | -20.41 | 412.94 | 1990.42 |
| 3: shared validation revenue scalar | -24.77 | 410.41 | 2022.83 |
| 4: count scalar, revenue scalar disabled | -11.80 | 418.72 | 1941.07 |
| 4: count scalar + refitted revenue scalar | -24.63 | 409.44 | 2018.26 |

Stage 1 Brier improved from 0.20038 to 0.19786. Mean probability bias improved from -5.26 to -4.29 percentage points. Calibration fits a regularized logistic mapping of log odds on established validation customers after base classifier selection. Cold-start purchase probabilities retain their separate historical fallback. Validation calibration scores are fit diagnostics and can be optimistic.

Stage 2's model is independent of Stage 1: changing purchase probabilities does not change its conditional predictions. Its raw validation mean was 2.02 versus 2.25 actual; raw test mean was 2.04 versus 2.48 actual among established purchasers. An optional validation mean-ratio correction is therefore implemented. The resulting revenue error falls within 15% on this historical period, with worse MAE. This tradeoff must be checked on another period before adoption. The correction does not use predicted-purchaser filtering, which would change the evaluation population.

Two buckets and prior strength 50 reduce sensitivity to sparse training bucket means. They barely improve aggregate error in this period; no claim is made that the cold-start issue is solved. Bucket counts and cohort test metrics remain available for investigation. Bucket-specific correction parameters are not fitted from test errors.

## Defaults and controls

- Classifier sigmoid calibration enabled (`--classifier-calibration none` restores raw probabilities).
- Two cold-start buckets, prior strength 50 (`--cold-buckets 4 --cold-prior-strength 10` restores the previous fallback).
- Revenue calibration and cap remain disabled by default.
- Count correction is opt-in with `--count-calibration scalar`.
- All learned corrections are saved with their model bundles. Old bundles without correction metadata retain their original predictions.

## Reproduce the ordered comparison

```powershell
$env:OMP_NUM_THREADS = '1'
$env:OPENBLAS_NUM_THREADS = '1'
.\.venv\Scripts\python.exe -m clv.experiments artifacts/cf0f9ba56a8441abbb9e99767fb5cad0
```

This writes `data/drift-comparison.json` and prints the combined scores. It reuses saved models and does not change the source run. All splits must contain matching customer IDs and auxiliary `first_order_value`.

## Full new training run with optional count correction

```powershell
$env:DATABASE_URL = 'sqlite:///data/uci.db'
.\.venv\Scripts\python.exe -m clv.cli train-all `
  --train-cutoff 2010-12-01 `
  --validation-cutoff 2011-04-01 `
  --test-cutoff 2011-09-01 `
  --observation-end 2011-12-10 `
  --classifier-calibration sigmoid `
  --cold-prior-strength 50 --cold-buckets 2 `
  --calibration none --established-calibration none `
  --no-revenue-cap --count-calibration scalar
```

For the step-3 scalar revenue comparison, disable count correction (`--count-calibration none`) and use `--calibration scalar --shared-calibration`. Stage 2 reports `test_raw`, `test`, and `drift_correction`. Stage 1 records `stage1_raw_test`, final `test`, and `stage1_calibration_validation`. Test results never set correction factors.
