# Pipeline improvement: first-pass results

Implemented the proposal's recommended first pass (fixes 1–3), plus the cold-start accuracy diagnostics from fix 6. All candidate selection and calibration use validation outcomes; test outcomes are used only for evaluation. The historical test is now a development diagnostic and should not be reused as proof of future business accuracy.

## Same-period comparison

Cutoffs: 2010-12-01 / 2011-04-01 / 2011-09-01; source coverage ends 2011-12-10. Values follow the UCI source's GBP currency, despite the proposal's dollar notation.

| Metric | Previous pipeline | First pass, raw | First pass, calibrated |
|---|---:|---:|---:|
| Aggregate revenue error | +46.16% | -20.50% | -24.30% |
| Customer MAE | 640.90 | 413.82 | 411.42 |
| Customer RMSE | 5522.68 | 1987.74 | 2015.66 |
| RMSE / MAE | 8.62 | 4.80 | 4.90 |
| Top-decile actual revenue captured | 56.10% | 58.80% | 58.80% |

New run: `8c8abc83223443579171af55e02c54a5`. Stage 1 remains logistic and stage 2 remains LightGBM Poisson. Selecting stage 3 by validation MAE changes its winner from Gamma to XGBoost log-value. The validation-fitted scalar is 0.952306. It removes validation aggregate bias by construction but worsens test aggregate bias. Improved performance is measured for this period, not guaranteed for new data. A scalar preserves ranking unless its factor is zero.

## Diagnostics and interpretation

The product of conditional count and order-value expectations assumes separability. Multiplication alone does not prove upward bias; the separate averages and combined raw/calibrated results help test this diagnosis.

`stage1.test` includes actual and predicted purchase rates. `stage2.test` and `stage3.test` include actual/predicted conditional means and mean bias for established purchasers. Empty conditional populations have null error metrics. `cohort_test` measures combined revenue accuracy across all customers, split by history path.

Cold-start customers are 1,590 of 5,245 customers (30.31%), not 13.2%. The latter number was the fallback purchase probability. Their actual mean test revenue is 137.24; raw fallback revenue is 79.71 and calibrated fallback revenue is 75.90. The fallback is materially low on this period.

## Remaining proposal items

Classifier calibration, joint candidate selection, segmented cold-start fallback, and outlier caps are not included in this first pass. The ±15% aggregate-error target remains unmet. These choices need validation-based experiments and a fresh later holdout; applying a correction fitted to the observed test error would invalidate evaluation. MAE selection improves typical customer errors but does not itself optimize aggregate revenue. A cap would require validation support because this run already underpredicts total revenue.

## Verification

Ten tests passed across revenue calibration, full training with saved-model replay, report generation, foundation ingestion/features, and UCI conversion. A real UCI full training run completed and produced the combined PNG. The existing HTTP pipeline test stalls inside Windows asyncio socket-pair creation in the API test client; it was stopped after collecting a traceback. This is separate from the successful training and saved-model checks.
