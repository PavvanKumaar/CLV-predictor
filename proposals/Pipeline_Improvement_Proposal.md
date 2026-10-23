# Proposal: Pipeline Accuracy Improvements

**Based on:** Model run `2d1dbb68f6884f40b19f8909a3bc486b`
**Problem:** Combined CLV pipeline shows a 46.16% aggregate revenue error on test (predicted $4,009,127 vs actual $2,743,032), despite individually reasonable per-stage validation metrics.
**Purpose of this document:** propose a prioritized set of fixes to close this gap, with reasoning for each and an execution order.

---

## 1. Summary of Current Results

| Metric | Value |
|---|---|
| Stage 1 winner | Logistic Regression (selected by Brier score) |
| Stage 1 test ROC-AUC | 0.752 |
| Stage 1 test Brier | 0.200 (validation: 0.175 — degraded on test) |
| Stage 2 winner | LightGBM (Poisson objective) |
| Stage 2 test RMSE / MAE | 2.498 / 1.085 |
| Stage 3 winner | Gamma GLM (selected by RMSE) |
| Stage 3 test RMSE / MAE | 530.68 / 375.98 |
| Combined test RMSE / MAE | 5522.68 / 640.90 |
| **Aggregate revenue error** | **46.16%** |
| Cold-start rate | 13.2% of customers, flat CLV = 79.71 |

**Root diagnosis:** the combination logic multiplies three independently-fit conditional expectations (`P(purchase) × E[count|purchase] × E[value|purchase]`). Each sub-model carries its own error, and multiplicative combination compounds these errors upward rather than letting them cancel — this is the primary driver of the overprediction.

---

## 2. Proposed Fixes

### Fix 1 — Add Post-Hoc Revenue Calibration
**Problem addressed:** 46.16% aggregate overprediction.
**Priority:** Highest — cheapest fix, directly targets the stated success metric.

**Proposed approach:**
- Compute `calibration_factor = actual_validation_revenue / predicted_validation_revenue`.
- Apply this scalar to all test-set `predicted_clv` values before final reporting.
- **Stronger alternative:** fit `IsotonicRegression(predicted_clv_val → actual_clv_val)` and apply it to test predictions instead of a flat scalar — corrects non-linear bias (e.g., overprediction concentrated among high-value customers) rather than a uniform shift.

**Expected outcome:** aggregate revenue error should drop sharply since this directly corrects the compounding bias at the final output stage, without needing to retrain any sub-model.

---

### Fix 2 — Re-Select Stage 3 Using MAE Instead of RMSE
**Problem addressed:** Stage 3 model choice appears locally suboptimal for the typical customer.
**Priority:** High — cheap to test, likely meaningful impact.

**Evidence:**
| Model | RMSE | MAE |
|---|---|---|
| gamma (current winner) | 516.27 | 333.59 |
| xgboost_log | 602.45 | **200.62** |
| catboost_log | 668.20 | 225.38 |

`gamma` wins on RMSE but loses badly on MAE — RMSE is outlier-sensitive, so `gamma` likely performs well on a few extreme values while underperforming on the bulk of typical customers. Since aggregate revenue error is driven by the bulk of customers, this mismatch is a plausible contributor.

**Proposed approach:**
- Re-run Stage 3 selection using MAE as the primary criterion (or a revenue-weighted metric — see Fix 5).
- Re-run the combined evaluation with `xgboost_log` substituted for `gamma` and compare `aggregate_error_pct`.

**Expected outcome:** improved typical-customer value prediction, likely reducing aggregate error further.

---

### Fix 3 — Add Per-Stage Test-Set Diagnostics
**Problem addressed:** currently no way to isolate which stage (1, 2, or 3) is driving the combined bias.
**Priority:** High — needed to validate Fixes 1 and 2, and to guide further tuning.

**Proposed approach:** on the test set, compute and report:
- `mean(predicted_prob_purchase)` vs actual test `purchase_rate` (0.4267)
- `mean(predicted_count | purchased)` vs actual mean count among purchasers
- `mean(predicted_value | purchased)` vs actual mean value among purchasers

**Expected outcome:** pinpoints exactly which stage(s) are over- or under-predicting, replacing guesswork with evidence for where to focus calibration effort.

---

### Fix 4 — Recalibrate the Stage 1 Classifier
**Problem addressed:** Brier score degrades from validation (0.175) to test (0.200); `warm_test` purchase rate (0.524) vs overall test purchase rate (0.4267) suggests distribution drift across the three training cutoffs (Dec 2010 / Apr 2011 / Sep 2011).
**Priority:** Medium — addresses a real but secondary contributor.

**Proposed approach:**
- Apply `CalibratedClassifierCV` (Platt scaling or isotonic) on top of the existing logistic model.
- Re-fit using the most recent cutoff weighted more heavily (or exclusively), since customer purchase behavior appears to have shifted over the 2-year window and recent behavior is more representative of the test period.

**Expected outcome:** more reliable purchase probabilities feeding into the combination step, reducing compounding error at the source.

---

### Fix 5 — Align Model Selection Metrics With the Actual Business Goal
**Problem addressed:** each stage was selected using stage-local metrics (Brier, Poisson deviance, RMSE) rather than the metric that actually matters — combined revenue accuracy.
**Priority:** Medium — more compute-intensive but directly optimizes the real target.

**Proposed approach:**
- Narrow each stage to its top 2–3 candidates using local metrics (as already done).
- Run the **full combined pipeline** for each candidate combination (e.g., all Stage 1 × Stage 2 × Stage 3 permutations among top candidates).
- Select the final combination based on `aggregate_error_pct` and combined MAE, not stage-local metrics in isolation.

**Expected outcome:** a globally-optimal model combination rather than three locally-optimal but potentially mismatched sub-models — this is the likely explanation for how `gamma` won Stage 3 locally while still contributing to a large combined error.

---

### Fix 6 — Validate and Segment Cold-Start Handling
**Problem addressed:** 13.2% of customers receive a single flat CLV value (79.71) with no reported accuracy check.
**Priority:** Medium.

**Proposed approach:**
- Compute actual average holdout revenue for cold-start customers in the test set and compare against the flat value of 79.71.
- If materially off, segment the fallback (e.g., by first-purchase value bucket or acquisition category) instead of using one global constant.

**Expected outcome:** improved accuracy for a meaningful minority segment that is currently unvalidated and likely contributing unmeasured error.

---

### Fix 7 — Cap Outlier Predictions
**Problem addressed:** combined RMSE (5522.68) is ~8.6x combined MAE (640.90), indicating a small number of customers receive wildly overpredicted CLV.
**Priority:** Lower — a safety net rather than a root-cause fix.

**Proposed approach:**
- Winsorize or cap `predicted_clv` at a reasonable percentile (e.g., 99th percentile of historical actual spend) before final reporting.
- Manually inspect the worst-predicted customers to confirm the hypothesis that Stage 1 × Stage 2 × Stage 3 overpredictions are compounding together for the same customers.

**Expected outcome:** reduces the impact of extreme outlier predictions on both the reported metrics and any business decisions (e.g., marketing budget allocation) built on top of them.

---

## 3. Recommended Execution Order

| Order | Fix | Effort | Expected Impact |
|---|---|---|---|
| 1 | Fix 1 — Revenue calibration | Low | High |
| 2 | Fix 2 — Re-select Stage 3 by MAE | Low | High |
| 3 | Fix 3 — Per-stage test diagnostics | Low | High (enables validating 1 & 2) |
| 4 | Fix 4 — Recalibrate classifier | Medium | Medium |
| 5 | Fix 6 — Validate cold-start segment | Medium | Medium |
| 6 | Fix 5 — Combined-metric model selection | High | Medium–High |
| 7 | Fix 7 — Cap outlier predictions | Low | Low–Medium (safety net) |

**Suggested approach:** implement Fixes 1–3 first as a fast pass, re-run the combined evaluation, and check whether `aggregate_error_pct` drops meaningfully before investing in Fixes 4–7.

---

## 4. Success Criteria for This Round of Fixes

- Aggregate revenue error (`aggregate_error_pct`) reduced from 46.16% to within an acceptable band (e.g., ±15%, per the original PRD success metric).
- Combined RMSE-to-MAE ratio reduced, indicating fewer extreme outlier predictions.
- Stage-by-stage test diagnostics available and documented for future model versions.
- Cold-start segment accuracy validated and, if needed, improved beyond a single flat constant.
