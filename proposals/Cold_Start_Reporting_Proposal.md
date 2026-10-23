# Proposal: Cold-Start Label Correction & Revenue Accuracy Reporting

**Related to:** Fix 6 of the Pipeline Improvement Proposal (model run `2d1dbb68f6884f40b19f8909a3bc486b`)
**Issue:** The reported `cold_start_rate: 0.1321` is actually the cold-start **purchase probability**, not the **population share** of cold-start customers. This has been mislabeled in the pipeline output, and cold-start revenue accuracy has never been separately measured.

---

## 1. Problem

The original output conflates two distinct quantities under one ambiguous field name:

```json
"cold_start_rate": 0.13211120632545612
```

This value is `P(purchase | cold-start)` — the probability a cold-start customer makes a purchase — not the share of the customer base that is flagged cold-start. As a result:
- The true cold-start population size is currently unknown.
- Fix 6 in the earlier proposal was prioritized as "Medium" partly on the assumption that cold-start customers are a modest ~13% slice — this assumption may be wrong and needs to be re-verified.
- No revenue-accuracy check has been run on the cold-start segment specifically, despite 100% of these customers receiving a single flat `predicted_clv = 79.71`.

---

## 2. Proposed Fix

### 2.1 Correct the field naming
Split the single ambiguous field into two explicit, separately-tracked metrics:

```json
// Before
"cold_start_rate": 0.13211120632545612

// After
"cold_start_purchase_probability": 0.13211120632545612,
"cold_start_population_share": <computed>
```

### 2.2 Compute the true cold-start population share
Using the same cold-start threshold already defined in the pipeline (e.g., <2 calibration-period purchases or <30 days tenure), compute the actual share directly from the test-set customer table:

```python
cold_start_population_share = test_df["is_cold_start"].sum() / len(test_df)
```

### 2.3 Compute cold-start revenue accuracy
Isolate cold-start customers in the test set and compare predicted vs actual holdout revenue for that segment specifically:

```python
cold_start_df = test_df[test_df["is_cold_start"] == True]

actual_cold_start_revenue = cold_start_df["actual_holdout_revenue"].sum()
predicted_cold_start_revenue = cold_start_df["predicted_clv"].sum()

cold_start_revenue_error_pct = (
    (predicted_cold_start_revenue - actual_cold_start_revenue)
    / actual_cold_start_revenue
) * 100

cold_start_mae = (
    cold_start_df["predicted_clv"] - cold_start_df["actual_holdout_revenue"]
).abs().mean()
```

### 2.4 Report as a dedicated output block
Add a `cold_start` block to the pipeline's output JSON, parallel to the existing `combined` block:

```json
"cold_start": {
    "purchase_probability": 0.1321,
    "population_share": <value>,
    "n": <count>,
    "actual_revenue": <sum>,
    "predicted_revenue": <sum>,
    "revenue_error_pct": <value>,
    "mae": <value>
}
```

---

## 3. Decision Criteria Once Measured

| Result | Action |
|---|---|
| Population share is small AND revenue error is small | Flat constant (79.71) is adequate — no further work needed, keep Fix 6 as low/deprioritized. |
| Population share is small BUT revenue error is large | Revisit the flat constant's value (may be miscalibrated), but low urgency given limited blast radius. |
| Population share is large (regardless of error size) | A meaningful share of the customer base is riding on one untested constant — re-prioritize Fix 6 upward, implement the segmented fallback (e.g., by first-purchase value bucket or acquisition category) proposed in the original improvement plan. |

---

## 4. Secondary Diagnostic Value

Once corrected, `cold_start_purchase_probability` (0.1321) is also useful on its own — compare it against the warm-customer test purchase rate (0.4267) to gauge how strongly the model discounts new/thin-history customers. A gap that looks disproportionate relative to genuinely expected new-customer behavior may indicate the cold-start threshold itself (not just the fallback value) needs review.

---

## 5. Priority

This is a **measurement and labeling fix**, not a model change — low effort, should be implemented before the next full pipeline re-run so that Fix 6's priority level in the broader improvement plan can be set correctly based on real numbers rather than an ambiguous metric.

---

## 6. Subsequent Fixes for Better Overall Results

These build on the latest run's before/after numbers:

| Metric | Before | After |
|---|---|---|
| Revenue error | +46.2% | −24.3% |
| Customer MAE | 640.9 | 411.4 |
| Customer RMSE | 5,522.7 | 2,015.7 |

RMSE and MAE both improved substantially — the outlier-capping and MAE-driven Stage 3 reselection worked as intended. Revenue error, however, flipped sign and overshot (from +46.2% overprediction to −24.3% underprediction), indicating the calibration step and the outlier-capping step are currently stacking rather than working independently. The following fixes address that, in priority order.

### Fix 8 — Recompute the Calibration Factor Against Post-Cap Predictions
**Problem:** if `calibration_factor = actual_val_revenue / predicted_val_revenue` was computed before (or without accounting for) outlier capping from Fix 7, it is now double-correcting — the cap already pulled down the inflated high-end predictions, and the stale calibration factor pulls the result down again.
**Proposed approach:** recompute `calibration_factor` using validation predictions *after* winsorization/capping has been applied, not the raw pre-cap predictions. Re-apply this corrected factor to test predictions.
**Priority:** Highest — directly targets the −24.3% overcorrection.

### Fix 9 — Replace Flat Scalar Calibration with Isotonic Regression
**Problem:** a flat scalar calibration factor cannot distinguish "overpredicted because of outliers" (already fixed by Fix 7's capping) from "overpredicted across the board" (may still need correction) — applying one uniform correction to both cases is a likely source of the overshoot.
**Proposed approach:** fit `IsotonicRegression(predicted_clv_val → actual_clv_val)` on the post-cap validation predictions, and apply it to test predictions instead of a single scalar. This allows the correction to vary by predicted-value range rather than shifting every customer by the same amount.
**Priority:** High — more robust long-term fix than Fix 8 alone.

### Fix 10 — Decouple the Calibration and Outlier-Capping Steps
**Problem:** currently the two corrections appear to run in sequence against stale reference values, rather than being independently tunable.
**Proposed approach:** restructure the pipeline so outlier capping (Fix 7) is applied first and finalized, then calibration (Fix 8/9) is fit and applied strictly on top of the already-capped output — never recompute capping after calibration or vice versa in the same pass.
**Priority:** High — structural fix that prevents this class of overcorrection from recurring in future model versions.

### Fix 11 — Re-run Per-Stage Test Diagnostics on the Corrected Pipeline
**Problem:** it is not yet known whether the −24.3% underprediction is concentrated in one stage (e.g., Stage 1 now predicting purchase probability too low after recalibration) or spread evenly across all three.
**Proposed approach:** re-run the per-stage diagnostics proposed in the original improvement plan (mean predicted purchase probability vs actual test purchase rate; mean predicted count vs actual among purchasers; mean predicted value vs actual among purchasers) on this corrected run, specifically to confirm Fixes 8–10 closed the gap without introducing a new stage-specific bias.
**Priority:** Medium — validation step, not a fix in itself, but required before declaring this round complete.

### Fix 12 — Extend Revenue Calibration to the Cold-Start Segment Separately
**Problem:** the global calibration factor (Fix 8/9) is currently fit across all customers, including cold-start customers who receive a single flat constant (79.71). If cold-start customers behave very differently from warm customers (as suggested by the 13.2% cold-start purchase probability vs 42.67% warm test purchase rate), folding them into one global calibration risks miscalibrating both segments simultaneously.
**Proposed approach:** once Section 2–3 of this proposal produces the `cold_start_population_share` and `cold_start_revenue_error_pct` numbers, fit calibration separately for the cold-start segment (or confirm it can safely share the global calibration if its error profile turns out to be similar).
**Priority:** Medium — depends on the outcome of Sections 2–3 above; escalate to High if cold-start population share turns out to be large.

### Target for This Round
- Revenue error brought into the ±15% band (per the original PRD success threshold), without giving back the RMSE/MAE gains already achieved.
- Confirmation via Fix 11 diagnostics that the correction is evenly distributed, not just shifted to a different customer segment.

