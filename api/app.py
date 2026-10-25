import os
import pathlib
import json
from typing import Literal, List

import pandas as pd
import joblib
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator

import types, sys
from sklearn.base import BaseEstimator
# Dummy module injection removed – using real installed ML libraries (lightgbm, catboost, xgboost).
# Import inference utilities from the existing package
from clv.ml import predict as ml_predict
from clv.revenue import compose as revenue_compose, apply_postprocessing as revenue_postprocess
# Regressor helper – located in clv/regressors.py (import path may differ)
# The module provides an ``estimate`` function used during training.
try:
    from clv.regressors import estimate as reg_estimate
except ImportError as e:
    raise ImportError("Unable to import clv.regressors.estimate – ensure the package is in PYTHONPATH") from e




# ------------------------------------------------------------
# 1️⃣ Load the latest artifact bundle (full_model.joblib)
# ------------------------------------------------------------

ARTIFACT_ROOT = os.getenv("ARTIFACT_DIR", "artifacts")
PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]  # <project>/api/app.py -> <project>
artifact_root_path = (PROJECT_ROOT / ARTIFACT_ROOT).resolve()

if not artifact_root_path.is_dir():
    raise RuntimeError(f"Artifact root directory not found: {artifact_root_path}")

# Find sub‑directories that contain a ``full_model.joblib`` file
candidate_dirs = []
for sub in artifact_root_path.iterdir():
    if sub.is_dir() and (sub / "full_model.joblib").is_file():
        candidate_dirs.append(sub)

if not candidate_dirs:
    raise RuntimeError(f"No artifact directories with 'full_model.joblib' found under {artifact_root_path}")

# Choose the most‑recently‑modified directory (by modification time of the bundle file)
latest_dir = max(candidate_dirs, key=lambda d: (d / "full_model.joblib").stat().st_mtime)
bundle_path = latest_dir / "full_model.joblib"

bundle = joblib.load(bundle_path)

# ------------------------------------------------------------
# 2️⃣ Validate bundle integrity
# ------------------------------------------------------------
EXPECTED_FEATURES = [
    "recency",
    "frequency",
    "T",
    "avg_order_value",
    "monetary_std",
    "purchase_velocity",
    "interpurchase_time_mean",
    "interpurchase_time_std",
    "category_diversity",
    "category_missing",
    "tenure_bucket",
    "last_order_recency_ratio",
    "is_cold_start",
]

if bundle.get("definition_version") != "v1":
    raise RuntimeError("Model bundle has unexpected definition_version; expected 'v1'.")

bundle_features = bundle.get("features")
# Require at least the core features, is_cold_start optional
required_subset = set(EXPECTED_FEATURES) - {"is_cold_start"}
if not isinstance(bundle_features, list) or not required_subset.issubset(set(bundle_features)):
    raise RuntimeError(
        f"Model bundle missing required features. Expected at least {sorted(required_subset)}, got {bundle_features}"
    )

# Ensure required keys for inference are present
required_keys = [
    "pipeline",
    "cold_start_purchase_probability",
    "cold_start_fallback",
    "segment_thresholds",
    "revenue_calibration",
    "count_model",
    "value_model",
    "cold_start_clv",
    "model_version",
]
for k in required_keys:
    if k not in bundle:
        raise RuntimeError(f"Missing required key '{k}' in model bundle.")

# ------------------------------------------------------------
# 3️⃣ FastAPI app and request model
# ------------------------------------------------------------
app = FastAPI(title="CLV Predictor API (Demo)")

# CORS – only allow Vite dev origins
origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

class FeatureRequest(BaseModel):
    recency: float = Field(..., description="Days since last purchase")
    frequency: int = Field(..., ge=0, description="Number of historic purchases")
    T: float = Field(..., description="Customer tenure in days")
    avg_order_value: float = Field(..., gt=0)
    monetary_std: float = Field(..., ge=0)
    purchase_velocity: float = Field(...)
    interpurchase_time_mean: float = Field(..., ge=0)
    interpurchase_time_std: float = Field(..., ge=0)
    category_diversity: int = Field(..., ge=0)
    category_missing: int = Field(..., ge=0, le=1)
    tenure_bucket: Literal["new", "established", "loyal"]
    last_order_recency_ratio: float = Field(..., gt=0)
    is_cold_start: bool

    # Validator removed for Pydantic v2 compatibility

# ------------------------------------------------------------
# 4️⃣ Helper: segment assignment (mirrors training code)
# ------------------------------------------------------------
def assign_segment(clv: float, prob: float, frequency: int, thresholds: List[float]) -> str:
    lower, upper = thresholds[0], thresholds[1]
    if clv >= upper:
        return "VIP"
    if prob < 0.3 and frequency >= 2:
        return "At-Risk"
    if clv >= lower:
        return "Growth"
    return "Low-Priority"

# ------------------------------------------------------------
# 5️⃣ Endpoints
# ------------------------------------------------------------
@app.get("/health")
def health():
    return {"status": "ok", "model_version": bundle.get("model_version")}

@app.post("/predict")
def predict(request: FeatureRequest):
    # Convert request to a single‑row DataFrame preserving column order
    data = request.dict()
    df = pd.DataFrame([data])

    try:
        # Stage‑1 purchase probability
        prob_arr = ml_predict(bundle, df)
        prob = float(prob_arr[0])

        # Stage‑2 & 3 regressors (count and value)
        # Resolve count model and its logarithmic flag.
        count_entry = bundle.get("count_model")
        if isinstance(count_entry, dict):
            count_model = count_entry.get("model")
            count_log = bool(count_entry.get("logarithmic", False))
        else:
            count_model = count_entry
            count_log = bool(bundle.get("count_logarithmic", False))
        # Resolve value model and its logarithmic flag.
        value_entry = bundle.get("value_model")
        if isinstance(value_entry, dict):
            value_model = value_entry.get("model")
            value_log = bool(value_entry.get("logarithmic", False))
        else:
            value_model = value_entry
            value_log = bool(bundle.get("value_logarithmic", False))
        # Debug: print model types
        print('DEBUG count_model type:', type(count_model))
        print('DEBUG value_model type:', type(value_model))
        # Perform estimation using resolved models
        count_arr = reg_estimate(count_model, df, count_log)
        value_arr = reg_estimate(value_model, df, value_log)
        count = float(count_arr[0])
        value = float(value_arr[0])

        # Raw CLV composition
        raw_clv_arr = revenue_compose(prob_arr, [count], [value], df["is_cold_start"].to_numpy(), bundle["cold_start_clv"])
        raw_clv = float(raw_clv_arr[0])

        # Calibration / post‑processing
        calibrated_arr = revenue_postprocess(
            raw_clv_arr, df["is_cold_start"].to_numpy(), bundle["revenue_calibration"]
        )
        calibrated_clv = float(calibrated_arr[0])

        # Segment assignment – uses calibrated CLV
        segment = assign_segment(
            calibrated_clv, prob, data["frequency"], bundle["segment_thresholds"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Inference error: {str(e)}")

    # Ensure all numbers are finite before returning
    for name, val in {
        "prob_purchase": prob,
        "expected_transactions": count,
        "expected_value_per_txn": value,
        "predicted_clv_90d": calibrated_clv,
    }.items():
        if not (float(val) == float(val)):
            raise HTTPException(status_code=500, detail=f"Non‑finite result for {name}")

    return {
        "prob_purchase": prob,
        "expected_transactions": count,
        "expected_value_per_txn": value,
        "predicted_clv_90d": calibrated_clv,
        "segment": segment,
        "is_cold_start": data["is_cold_start"],
        "model_version": bundle.get("model_version"),
        "note": "SAMPLE / DEMO ONLY — offline-trained model",
    }


# ------------------------------------------------------------
# 6️⃣ Stage-1 demo, model status, and predictions endpoints
# ------------------------------------------------------------

@app.post("/stage1/demo")
def run_stage1_demo():
    """Run the full Stage 1 demo: generate synthetic data, ingest, train classifier, store predictions."""
    import os as _os
    from clv.cli import migrate
    from clv.sample import generate
    from clv.data import ingest
    from clv.ml import train
    from clv.db import session as db_session

    try:
        migrate()
        generate("data/sample.csv")
        with db_session() as db:
            ingestion = ingest(db, "data/sample.csv")
            report = train(
                db,
                "2025-01-01",
                "2025-04-01",
                "2025-07-01",
                "2025-10-01",
                _os.getenv("ARTIFACT_DIR", "artifacts"),
            )
            report["ingestion"] = ingestion
        return report
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Demo pipeline failed: {exc}")


@app.get("/model/status")
def model_status():
    """Return the latest Stage-1 model run metadata from the database."""
    from clv.db import session as db_session
    from clv.models import ModelRun
    from sqlalchemy import select

    with db_session() as db:
        row = db.scalar(
            select(ModelRun)
            .order_by(ModelRun.trained_at.desc(), ModelRun.model_version.desc())
            .limit(1)
        )
    if row is None:
        raise HTTPException(404, "No stage-one model has been trained")
    return {"status": row.status, **row.metadata_json}


@app.get("/stage1/predictions")
def stage1_predictions(
    model_version: str = None,
    limit: int = 50,
    offset: int = 0,
):
    """Return Stage-1 purchase-probability predictions from the database."""
    from clv.db import session as db_session
    from clv.models import ModelRun, Stage1Prediction
    from sqlalchemy import select

    with db_session() as db:
        if model_version is None:
            run = db.scalar(
                select(ModelRun)
                .order_by(ModelRun.trained_at.desc(), ModelRun.model_version.desc())
                .limit(1)
            )
            if run is None:
                raise HTTPException(404, "No stage-one model has been trained")
            model_version = run.model_version
        rows = db.scalars(
            select(Stage1Prediction)
            .where(Stage1Prediction.model_version == model_version)
            .order_by(Stage1Prediction.prob_purchase.desc(), Stage1Prediction.customer_id)
            .limit(limit)
            .offset(offset)
        )
        return [
            {
                "customer_id": r.customer_id,
                "model_version": r.model_version,
                "snapshot_id": r.snapshot_id,
                "prob_purchase": r.prob_purchase,
                "is_cold_start": r.is_cold_start,
            }
            for r in rows
        ]
