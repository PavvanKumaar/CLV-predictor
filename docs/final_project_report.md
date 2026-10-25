# CLV Prediction System – Final Project Report

## 1. Project Overview and Problem Statement
The CLV Prediction System addresses the **customer lifetime value (CLV)** forecasting problem for an e‑commerce retailer.  The goal is to predict the **total revenue a customer will generate in the next 90 days** based on their historical purchasing behaviour.  Accurate CLV estimates enable better marketing spend allocation, inventory planning, and customer segmentation.

## 2. Dataset Description and Preprocessing
- **Source:** `data/uci_orders.csv` (UCI Online Retail II dataset).  
- **Size:** 36,905 cleaned orders from **5,875** unique customers (see ingestion output in `clv/cli.py` – command `ingest`).
- **Pre‑processing steps** (implemented in `clv/features.py` → `build_frames`):
  1. Transactions are filtered to the **cut‑off date**; only purchases *before* the cut‑off are used for history.
  2. The **observation_end** date must be *exclusive* and later than all source transactions (validated on line 22 of `clv/features.py`).
  3. Customers with fewer than two orders or tenure < 30 days are flagged as **cold‑start** (column `is_cold_start`, line 42).
  4. All timestamps are normalised with `clv.data.timestamp` (line 18).

## 3. Feature Engineering and 90‑day CLV Target Definition
Feature construction lives in `clv/features.py` → `build_frames` (lines 17‑46):
- **Recency, frequency, tenure (T)**, average order value, monetary standard deviation, purchase velocity, inter‑purchase time statistics, category diversity, tenure bucket, and last‑order‑recency‑ratio are computed for each customer.
- The **90‑day revenue target** (`revenue` in the label dataframe) is the sum of order amounts for transactions occurring **from `cutoff` (inclusive) up to `cutoff + 90 days` (exclusive)** (line 24).
- The label also contains `purchased` (binary if any future order) and `transaction_count` (future count).

## 4. System Architecture and End‑to‑End Workflow
```
clv/cli.py   →  command‑line interface
   ├─ `features`   → snapshot → CSVs (features.csv, labels.csv)
   ├─ `train`      → Stage‑1 only (purchase probability)
   └─ `train‑all`  → Stage‑1 + Stage‑2 (count) + Stage‑3 (value) + post‑processing
```
The workflow (see `clv/ml.py` lines 74‑140 for Stage‑1 and lines 143‑267 for full pipeline) is:
1. **Snapshot creation** (`snapshot()` line 49) produces training, validation and test frames.
2. **Stage‑1** trains multiple classifiers (`candidates()` lines 40‑58) and selects the winner using validation Brier score (line 97).
3. **Stage‑2** and **Stage‑3** fit count and value regressors (`fit_stage` in `clv/regressors.py`).
4. **Cold‑start fallback** is fitted on training data (`fit_cold_fallback` line 86‑108).
5. **Revenue calibration** (`fit_postprocessing` line 31‑70) is optionally applied; in the current run the method is `none` (lines 292‑295 of `metrics.json`).
6. Final CLV is composed (`compose` line 5) and optionally capped/calibrated (lines 199‑202).

## 5. Model Stages
### Stage 1 – Purchase Probability Prediction
- Candidate models: Logistic Regression, Random Forest, LightGBM, CatBoost, XGBoost, Dummy (`candidates()` lines 40‑58). 
- **Winner:** **Logistic Regression** (selected by minimum validation Brier score, line 97 of `clv/ml.py`).
- **Validation performance:** Brier = 0.17497, ROC‑AUC = 0.76497 (see `metrics.json` → `validation → logistic`, lines 632‑639).

### Stage 2 – Transaction Count Prediction
- Models are trained via `fit_stage('count', …)` (line 158 of `clv/ml.py`).
- The **Mean** regressor achieved the best validation RMSE (1.68968) (see `metrics.json` → `stage2 → validation → mean`, lines 741‑744).

### Stage 3 – Order Value Prediction
- Trained with `fit_stage('value', …)` (line 159 of `clv/ml.py`).
- The **Mean** regressor again performed best on validation (RMSE = 2.73886) (see `metrics.json` → `stage3 → validation → mean`, lines 754‑757).

## 6. Cold‑Start Handling Using the Four‑Bucket Fallback
- Cold‑start customers are identified during feature construction (`is_cold_start` flag, line 42 of `features.py`).
- **Bucket fitting** (`fit_cold_fallback` lines 86‑108) creates **four buckets** based on quantiles of the first‑order value of training cold‑start customers.  The configuration is stored in `metrics.json` under `cold_start_fallback` (edges, estimates, counts).
- **Prediction** (`predict_cold_fallback` line 111) maps a validation/customer’s `first_order_value` to the appropriate bucket and returns the bucket’s revenue estimate.
- A **global scalar fallback** (`cold_start_clv`) is also computed (lines 191‑192) but is **only reported**, not used in the final CLV composition.

## 7. Model Selection and Validation Results
| Stage | Selected model | Validation metric(s) |
|-------|----------------|----------------------|
| Purchase probability | Logistic Regression | Brier = 0.17497, ROC‑AUC = 0.76497 |
| Transaction count | Mean regressor | RMSE = 1.68968, MAE = 0.92556 |
| Order value | Mean regressor | RMSE = 2.73886, MAE = 1.43846 |
| Cold‑start fallback (validation) | Four‑bucket vs. global scalar | **Four‑bucket**: MAE = ₹127.78, RMSE = ₹304.01, agg % = +0.45 % (see `compare_cold_fallbacks.py` output). Global scalar: MAE = ₹131.60, RMSE = ₹304.94, agg % = +3.15 % |
| Combined CLV (validation) | Raw + calibrated (identical) | RMSE ≈ 1,139, MAE ≈ 296.44, aggregate error = +5.79 % (lines 339‑348 of `metrics.json`). |

## 8. Final Evaluation Metrics
### Validation (held‑out snapshot)
- **Combined CLV (raw & calibrated):** RMSE = 1,139.00, MAE = 296.44, aggregate error = +5.79 %.
- **Cold‑start validation:** Four‑bucket MAE = ₹127.78, RMSE = ₹304.01, agg % = +0.45 %.

### Test (final hold‑out) – already used in experiments
- **Combined revenue (test):**
  - Actual = ₹2,743,032.12
  - Predicted ≈ ₹2,182,568.51
  - Aggregate error ≈ ‑20.43 % (see `metrics.json` → `combined_raw` lines 321‑324).
- **Cold‑start revenue (test):**
  - Actual = ₹218,210.05
  - Predicted ≈ ₹121,379.36
  - Aggregate error ≈ ‑44.38 % (see `metrics.json` → `cold_start` lines 726‑728).
> **Note:** The test set has already been used for model‑level evaluation and should not be presented as a completely untouched hold‑out.

## 9. Technical Challenges and How They Were Addressed
| Challenge | Solution |
|-----------|----------|
| **Cold‑start sparsity** – Very few historical transactions for new customers. | Built a **four‑bucket revenue fallback** using first‑order value (lines 86‑108) and added a **prior strength** of 10 pseudo‑observations (lines 191‑192) to shrink bucket estimates.
| **Potential data leakage** – Risk of using future information when creating labels. | Enforced strict cutoff/observation windows (`observation_end` exclusive, line 22 of `features.py`). Validation and test metrics are computed **after** all model fitting.
| **Model over‑fitting in Stage‑2/3** – Complex regressors did not improve validation scores. | Defaulted to the **mean regressor** for count and value, which gave the lowest validation RMSE and avoided over‑fitting.
| **Revenue outliers** – High‑value customers could dominate error metrics. | Provided a **cap‑then‑calibrate** framework (`fit_postprocessing`), but the current run kept `method='none'`. The framework is ready for future experiments.

## 10. Known Limitations and Future Improvements
- **Cold‑start bucket variance** – Bucket 0 still under‑predicts revenue; raising `cold_prior_strength` or increasing bucket granularity could stabilise estimates.
- **Revenue calibration disabled** – Using a scalar or isotonic calibration could correct systematic bias, especially on the test set.
- **Simple count/value models** – Mean regressors ignore covariate information; exploring tree‑based or Poisson models may improve accuracy for high‑frequency customers.
- **Hold‑out strategy** – The test set has been used for reporting; a truly unseen hold‑out would be needed for final production evaluation.
- **Feature set** – Additional behavioural features (e.g., recency‑frequency‑monetary (RFM) interactions, time‑between purchases) could be engineered.

## 11. Installation, Configuration, and Execution
1. **Clone the repository** (already present at `C:\CLV\CLV-predictor`).
2. **Create a virtual environment** (Python 3.12) and install dependencies:
   ```powershell
   python -m venv .venv312
   .\.venv312\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```
3. **Initialize the database** (SQLite by default):
   ```bash
   python -m clv.cli init-db
   ```
4. **Ingest the dataset** (if not already done):
   ```bash
   python -m clv.cli ingest data/uci_orders.csv
   ```
5. **Run feature engineering** (example for the validation cutoff used in the report):
   ```bash
   python -m clv.cli features --cutoff 2011-04-01 --observation-end 2011-12-10 --output data/validation_snapshot
   ```
6. **Train the full pipeline** (the run that generated the reported artifacts):
   ```bash
   python -m clv.cli train-all \
       --train-cutoff 2010-12-01 \
       --validation-cutoff 2011-04-01 \
       --test-cutoff 2011-09-01 \
       --observation-end 2011-12-10 \
       --cold-prior-strength 1 \
       --cold-buckets 4
   ```
   The artifacts will be written to `artifacts/<run‑id>/` (e.g., the folder used for this report).
7. **Inspect results** – the JSON report `metrics.json` contains all validation and test metrics; the CSVs contain per‑customer predictions.

## 12. Conclusion
The CLV Prediction System demonstrates a **complete, reproducible pipeline** that transforms raw e‑commerce transaction data into a 90‑day revenue forecast.  Validation results show a **combined CLV RMSE of ~1.14 k** and a **cold‑start bucket fallback that outperforms a simple global scalar** on the validation slice.  Test‑set performance indicates room for improvement, especially for cold‑start customers and high‑value outliers.  The architecture is modular, allowing future experimentation with richer features, alternative calibrations, and more sophisticated regressors before considering production deployment.
