# Product Requirements Document: Customer Lifetime Value (CLV) Prediction System

**Version:** 1.0
**Status:** Draft
**Owner:** Pavvan
**Approach:** Tier 3 — Two/Three-Stage ML Pipeline (Option A)

---

## 1. Overview

### 1.1 Problem Statement
An online retail business with ~1,000+ customers has historical purchase data but cannot answer: *how much revenue will each customer generate in the next 90 days, and which customers should be prioritized?* Past spend alone is unreliable — it treats a consistent repeat buyer (Customer A), a one-time big spender gone quiet (Customer B), and a brand-new customer (Customer C) without distinguishing their very different future trajectories.

### 1.2 Goal
Build a predictive system that estimates 90-day forward CLV per customer and exposes it through an API and dashboard, enabling the business to rank and prioritize customers for marketing/retention spend.

### 1.3 Approach Summary (Option A)
Replace the probabilistic BG/NBD + Gamma-Gamma approach with a supervised ML pipeline composed of three modeling stages:
1. **Classifier** — P(customer purchases in next 90 days)
2. **Count Regressor** — expected number of transactions in next 90 days (Poisson/NB-style)
3. **Value Regressor** — expected spend per transaction, conditional on purchasing

Final CLV is composed from these three outputs, with a separate cold-start path for new customers.

---

## 2. Goals & Non-Goals

### 2.1 Goals
- Predict 90-day forward CLV per customer with measurable accuracy against a holdout period.
- Output a purchase probability, expected transaction count, expected value, and combined CLV per customer.
- Segment customers (VIP / Growth / At-Risk / Low-Priority) for business prioritization.
- Handle cold-start customers (no/minimal history) with a fallback estimate.
- Serve predictions via API and visualize them in a dashboard.
- Maintain a versioned model registry so retraining doesn't silently overwrite prior results.

### 2.2 Non-Goals (v1)
- Real-time/streaming prediction (batch scoring is sufficient).
- Multi-year LTV (scope is fixed at 90-day horizon).
- Full causal/uplift modeling of marketing interventions.
- Deep learning / sequence models (explicitly deferred to a future Tier 4 iteration).

---

## 3. Users & Use Cases
- **Marketing/Retention team (primary):** View ranked customer list, identify high-value-at-risk customers for retention campaigns.
- **Business stakeholder:** View aggregate dashboard — total predicted 90-day revenue, segment breakdown.
- **You (developer/portfolio):** Demonstrate an end-to-end ML system with defensible modeling choices and engineering practices.

---

## 4. System Architecture

```
Raw Transactions (CSV)
        │
        ▼
 ETL / Preprocessing (Python)
        │
        ▼
 PostgreSQL ── raw_transactions → transactions → customers
        │
        ▼
 Feature Engineering (RFM + trend/velocity features)
        │
        ▼
 ML Pipeline
   ├── Stage 1: Classifier (purchase propensity)
   ├── Stage 2: Count Regressor (expected transactions)
   └── Stage 3: Value Regressor (expected value per transaction)
        │
        ▼
 Combined CLV = P(purchase) × E[transactions] × E[value]
        │
        ▼
 clv_predictions table (PostgreSQL) + model_runs registry
        │
        ▼
 FastAPI Backend (reads predictions, serves REST endpoints)
        │
        ▼
 React Dashboard (customer table, segment charts, model status)
```

**Model artifact storage:** local filesystem in dev → S3-compatible blob storage if deployed.
**Database:** PostgreSQL as single system of record (see data modeling section below).

---

## 5. Data Modeling

### 5.1 Core Tables (unchanged from prior design)
- `raw_transactions` — ingested source data, untouched.
- `customers` — one row per customer.
- `transactions` — cleaned, normalized transaction log.
- `customer_rfm_summary` — precomputed features per customer per model version.
- `clv_predictions` — final output per customer per model version.
- `model_runs` — registry of training runs, params, validation metrics, artifact paths.

### 5.2 Updated Feature Set (for ML models, replacing raw RFM-only inputs)
| Feature | Description |
|---|---|
| `recency` | Days since last purchase |
| `frequency` | Number of purchases in calibration period |
| `T` | Customer age (days since first purchase) |
| `avg_order_value` | Mean transaction value |
| `monetary_std` | Std. deviation of transaction values (volatility) |
| `purchase_velocity` | Slope of purchase frequency over time (trend) |
| `interpurchase_time_mean` | Average days between purchases |
| `interpurchase_time_std` | Variability in days between purchases |
| `category_diversity` | Count of distinct product categories purchased |
| `tenure_bucket` | New / established / loyal (derived from T) |
| `last_order_recency_ratio` | recency / T — relative dormancy signal |

### 5.3 Labels (per stage, computed from holdout period)
| Stage | Label definition |
|---|---|
| Classifier | 1 if ≥1 purchase in holdout window, else 0 |
| Count Regressor | Number of transactions in holdout window (only rows where label=1) |
| Value Regressor | Mean transaction value in holdout window (only rows where label=1) |

### 5.4 Updated `clv_predictions` Schema
```sql
CREATE TABLE clv_predictions (
    customer_id             VARCHAR(20) REFERENCES customers(customer_id),
    prob_purchase            NUMERIC(5,4),
    expected_transactions    NUMERIC(6,2),
    expected_value_per_txn   NUMERIC(10,2),
    predicted_clv_90d        NUMERIC(10,2),
    segment                  VARCHAR(20),
    is_cold_start            BOOLEAN DEFAULT FALSE,
    model_version            VARCHAR(20),
    predicted_at             TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (customer_id, model_version)
);
```

### 5.5 Updated `model_runs` Schema (tracks 3 sub-models per run)
```sql
CREATE TABLE model_runs (
    model_version        VARCHAR(20) PRIMARY KEY,
    trained_at            TIMESTAMP DEFAULT NOW(),
    calibration_end_date  DATE,
    holdout_end_date      DATE,
    classifier_type       VARCHAR(30),
    classifier_auc        NUMERIC(5,4),
    count_regressor_type  VARCHAR(30),
    count_regressor_rmse  NUMERIC(10,2),
    value_regressor_type  VARCHAR(30),
    value_regressor_rmse  NUMERIC(10,2),
    combined_rmse         NUMERIC(10,2),
    artifact_path         TEXT
);
```

---

## 6. ML Pipeline Specification

### 6.1 Stage 1 — Purchase Classifier
- **Candidate models:** Logistic Regression (baseline) → Random Forest → CatBoost / LightGBM (primary candidates).
- **Target:** Binary (purchased in holdout window: yes/no).
- **Metrics:** AUC-ROC, Precision/Recall, calibration curve.
- **Output:** `prob_purchase` per customer.

### 6.2 Stage 2 — Count Regressor
- **Candidate models:** Poisson Regression (statsmodels/sklearn), Negative Binomial Regression, or LightGBM/XGBoost with `count:poisson` / Tweedie objective.
- **Target:** Number of transactions in holdout window (non-negative integer; trained on purchasers only).
- **Metrics:** RMSE, MAE, mean Poisson deviance.
- **Output:** `expected_transactions` per customer.

### 6.3 Stage 3 — Value Regressor
- **Candidate models:** LightGBM/XGBoost/CatBoost regressor on `log(1 + value)` target, or Gamma GLM.
- **Target:** Mean transaction value in holdout window (trained on purchasers only).
- **Metrics:** RMSE, MAE (on original scale, after inverse log-transform).
- **Output:** `expected_value_per_txn` per customer.

### 6.4 Combination Logic
```
predicted_clv_90d = prob_purchase × expected_transactions × expected_value_per_txn
```

### 6.5 Cold-Start Handling
- Customers below a minimum history threshold (e.g., <2 purchases or <30 days tenure) bypass Stages 1–3.
- Fallback: cohort-average CLV (segmented by acquisition channel/first-purchase category if available), flagged `is_cold_start = TRUE` in output.

### 6.6 Validation Strategy
- Time-based calibration/holdout split (90-day holdout window), consistent with prior design.
- Report per-stage metrics (Section 6.1–6.3) AND combined CLV error against actual holdout revenue, aggregate and per-customer.
- Lift/ranking evaluation: does the model correctly rank top-N customers by actual holdout spend?

---

## 7. Backend Specification (FastAPI)

### 7.1 Endpoints
| Endpoint | Method | Description |
|---|---|---|
| `/customers` | GET | Paginated customer list |
| `/predictions` | GET | All predictions, filterable by segment, sortable by CLV |
| `/predictions/{customer_id}` | GET | Single customer's full prediction breakdown (prob, count, value, CLV) |
| `/segments/summary` | GET | Aggregate stats per segment |
| `/model/status` | GET | Latest model version + per-stage validation metrics |
| `/pipeline/trigger` | POST (auth-protected) | Manually trigger retraining pipeline |

### 7.2 Design Notes
- Inference is decoupled from API requests — pipeline writes to `clv_predictions`, API only reads (fast response times).
- Pydantic schemas for strict response typing.
- API-key auth on `/pipeline/trigger`.

---

## 8. Frontend Specification (React)

| View | Contents |
|---|---|
| **Dashboard** | Total predicted 90-day revenue, segment counts, current model version + validation metrics |
| **Customer Table** | Sortable/filterable table: customer_id, prob_purchase, expected_transactions, expected_value, predicted_clv, segment; CSV export |
| **Customer Detail** | Per-customer breakdown of all three model outputs + raw transaction history timeline |
| **Segment Visualization** | Scatter: prob_purchase vs predicted_clv, colored by segment; bar chart of segment revenue share |

---

## 9. Tech Stack Summary

| Layer | Tool |
|---|---|
| Language | Python 3.10+ |
| ML models | scikit-learn (Logistic Regression, Random Forest), LightGBM, CatBoost, XGBoost, statsmodels (Poisson/NB/Gamma GLM) |
| Data processing | pandas, numpy |
| Database | PostgreSQL (primary), SQLite (local dev) |
| Model storage | Local filesystem (dev), S3-compatible blob store (deployed) |
| Backend | FastAPI, SQLAlchemy, Pydantic |
| Frontend | React, Tailwind, recharts |
| Scheduling | APScheduler or cron (periodic retraining) |

---

## 10. Milestones / Task Breakdown

### Phase 1 — Data Foundation
- [ ] Set up PostgreSQL schema (all tables in Section 5)
- [ ] Build ingestion script (CSV → `raw_transactions`)
- [ ] Build cleaning pipeline (`raw_transactions` → `transactions`, `customers`)
- [ ] Implement calibration/holdout time-split logic
- [ ] Build feature engineering script (Section 5.2 feature set) → `customer_rfm_summary`

### Phase 2 — ML Pipeline
- [ ] Implement label generation for all 3 stages (Section 5.3)
- [ ] Train + compare classifiers (Logistic Regression → Random Forest → CatBoost/LightGBM); select winner
- [ ] Train + compare count regressors (Poisson/NB vs boosted Poisson objective); select winner
- [ ] Train + compare value regressors (log-transformed LightGBM/XGBoost vs Gamma GLM); select winner
- [ ] Implement combination logic + cold-start fallback
- [ ] Build evaluation script (per-stage + combined metrics, lift chart)
- [ ] Populate `model_runs` and `clv_predictions` tables

### Phase 3 — Backend
- [ ] Scaffold FastAPI project (routers, schemas, db session)
- [ ] Implement all endpoints (Section 7.1)
- [ ] Add auth on `/pipeline/trigger`
- [ ] Add error handling (404s for unknown customer_id, etc.)

### Phase 4 — Frontend
- [ ] Scaffold React app, API client
- [ ] Build Dashboard view
- [ ] Build Customer Table view (sort/filter/export)
- [ ] Build Customer Detail view
- [ ] Build Segment Visualization components

### Phase 5 — Polish & Delivery
- [ ] Write README (architecture diagram, setup instructions, results, limitations)
- [ ] Document model comparison tables (per stage) with actual metrics
- [ ] Add unit tests for preprocessing + feature engineering
- [ ] Deploy (backend + frontend) if pursuing live demo
- [ ] Record short demo GIF/video for portfolio

---

## 11. Success Metrics
- Classifier AUC-ROC ≥ 0.75 on holdout.
- Combined CLV prediction aggregate revenue error within an acceptable band (e.g., ±15% of actual holdout revenue) — exact threshold to be set after baseline run.
- Top-10% predicted-CLV customers account for a disproportionately high share of actual holdout revenue (lift validation).
- All endpoints respond in <300ms (since inference is pre-computed, not live).

## 12. Risks & Open Questions
- Independence/data-sufficiency: does the dataset have enough repeat customers to train Stage 2/3 reliably?
- Cold-start accuracy is inherently limited — document this as a known limitation rather than over-engineering a fix in v1.
- Dataset choice (Online Retail II vs Olist vs FinWhiz data) affects which optional features (category, country) are available — finalize before Phase 1 begins.
