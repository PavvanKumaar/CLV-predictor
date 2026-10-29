from datetime import date, datetime
from decimal import Decimal
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, text

from clv.db import session
from clv.models import Customer, ModelRun, Stage1Prediction, CLVPrediction


app = FastAPI(
    title="CLV Predictor API",
    description="Customer purchase propensity and lifetime value prediction API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)


# ---------------------------------------------------------
# DATABASE DEPENDENCY
# ---------------------------------------------------------

def database():
    with session() as db:
        yield db


# ---------------------------------------------------------
# RESPONSE SERIALIZATION
# ---------------------------------------------------------

def serialize_value(value: Any) -> Any:
    """Convert database-specific values into JSON-safe values."""
    if isinstance(value, Decimal):
        return float(value)

    if isinstance(value, (datetime, date)):
        return value.isoformat()

    if isinstance(value, dict):
        return {key: serialize_value(item) for key, item in value.items()}

    if isinstance(value, list):
        return [serialize_value(item) for item in value]

    return value


def serialize_model(row: Any) -> dict:
    """Convert an ORM row into a dictionary."""
    data = {
        column.name: getattr(row, column.name)
        for column in row.__table__.columns
    }
    return serialize_value(data)


# ---------------------------------------------------------
# HEALTH CHECK
# ---------------------------------------------------------

@app.get("/health")
def health(db=Depends(database)):
    db.execute(text("SELECT 1"))
    return {
        "status": "ok",
        "message": "CLV Predictor API is running",
    }


# ---------------------------------------------------------
# CUSTOMERS
# ---------------------------------------------------------

@app.get("/customers")
def get_customers(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db=Depends(database),
):
    rows = db.scalars(
        select(Customer)
        .order_by(Customer.customer_id)
        .limit(limit)
        .offset(offset)
    ).all()

    return [{"customer_id": row.customer_id} for row in rows]


# ---------------------------------------------------------
# MODEL STATUS
# ---------------------------------------------------------

@app.get("/model/status")
def get_model_status(db=Depends(database)):
    run = db.scalar(
        select(ModelRun)
        .order_by(
            ModelRun.trained_at.desc(),
            ModelRun.model_version.desc(),
        )
        .limit(1)
    )

    if run is None:
        raise HTTPException(
            status_code=404,
            detail="No model run was found. Train the model first.",
        )

    result = {
        "model_version": run.model_version,
        "status": run.status,
        "trained_at": serialize_value(run.trained_at),
    }

    metadata = run.metadata_json or {}
    if isinstance(metadata, dict):
        for key, value in metadata.items():
            if key not in result:
                result[key] = serialize_value(value)

    return result


# ---------------------------------------------------------
# STAGE 1: PURCHASE PROPENSITY
# ---------------------------------------------------------

@app.get("/stage1/predictions")
def get_purchase_predictions(
    model_version: str | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db=Depends(database),
):
    if model_version is None:
        latest_run = db.scalar(
            select(ModelRun)
            .join(
                Stage1Prediction,
                Stage1Prediction.model_version == ModelRun.model_version,
            )
            .order_by(
                ModelRun.trained_at.desc(),
                ModelRun.model_version.desc(),
            )
            .limit(1)
        )

        if latest_run is None:
            raise HTTPException(
                status_code=404,
                detail="No purchase propensity predictions were found.",
            )

        model_version = latest_run.model_version

    rows = db.scalars(
        select(Stage1Prediction)
        .where(Stage1Prediction.model_version == model_version)
        .order_by(
            Stage1Prediction.prob_purchase.desc(),
            Stage1Prediction.customer_id,
        )
        .limit(limit)
        .offset(offset)
    ).all()

    return [serialize_model(row) for row in rows]


# ---------------------------------------------------------
# CLV PREDICTIONS
# ---------------------------------------------------------

@app.get("/clv/predictions")
def get_clv_predictions(
    model_version: str | None = None,
    customer_id: str | None = None,
    segment: str | None = None,
    cold_start: bool | None = None,
    min_clv: float | None = None,
    max_clv: float | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db=Depends(database),
):
    # Choose the newest model version that actually has saved CLV predictions.
    if model_version is None:
        latest_version = db.scalar(
            select(CLVPrediction.model_version)
            .join(
                ModelRun,
                ModelRun.model_version == CLVPrediction.model_version,
            )
            .order_by(
                ModelRun.trained_at.desc(),
                ModelRun.model_version.desc(),
            )
            .limit(1)
        )

        # Fallback for databases where a prediction exists but its model run
        # is absent or not joinable for some reason.
        if latest_version is None:
            latest_version = db.scalar(
                select(CLVPrediction.model_version)
                .order_by(CLVPrediction.predicted_at.desc())
                .limit(1)
            )

        if latest_version is None:
            return []

        model_version = latest_version

    query = select(CLVPrediction).where(
        CLVPrediction.model_version == model_version
    )

    if customer_id:
        query = query.where(CLVPrediction.customer_id == customer_id)

    if segment:
        query = query.where(CLVPrediction.segment == segment)

    if cold_start is not None:
        query = query.where(CLVPrediction.is_cold_start == cold_start)

    if min_clv is not None:
        query = query.where(CLVPrediction.predicted_clv_90d >= min_clv)

    if max_clv is not None:
        query = query.where(CLVPrediction.predicted_clv_90d <= max_clv)

    rows = db.scalars(
        query.order_by(
            CLVPrediction.predicted_clv_90d.desc(),
            CLVPrediction.customer_id,
        )
        .limit(limit)
        .offset(offset)
    ).all()

    return [serialize_model(row) for row in rows]


# ---------------------------------------------------------
# CLV SUMMARY
# ---------------------------------------------------------

@app.get("/clv/summary")
def get_clv_summary(
    model_version: str | None = None,
    db=Depends(database),
):
    if model_version is None:
        model_version = db.scalar(
            select(CLVPrediction.model_version)
            .join(
                ModelRun,
                ModelRun.model_version == CLVPrediction.model_version,
            )
            .order_by(
                ModelRun.trained_at.desc(),
                ModelRun.model_version.desc(),
            )
            .limit(1)
        )

        if model_version is None:
            model_version = db.scalar(
                select(CLVPrediction.model_version)
                .order_by(CLVPrediction.predicted_at.desc())
                .limit(1)
            )

    if model_version is None:
        return {
            "model_version": None,
            "count": 0,
            "total_predicted_clv": 0,
            "average_predicted_clv": 0,
            "average_purchase_probability": 0,
            "average_expected_transactions": 0,
            "cold_start_count": 0,
            "cold_start_share": 0,
            "segments": {},
            "message": "No CLV predictions found. Run the training and prediction pipeline first.",
        }

    rows = db.scalars(
        select(CLVPrediction).where(
            CLVPrediction.model_version == model_version
        )
    ).all()

    if not rows:
        return {
            "model_version": model_version,
            "count": 0,
            "total_predicted_clv": 0,
            "average_predicted_clv": 0,
            "average_purchase_probability": 0,
            "average_expected_transactions": 0,
            "cold_start_count": 0,
            "cold_start_share": 0,
            "segments": {},
            "message": "No predictions exist for this model version.",
        }

    count = len(rows)
    total_clv = sum(float(row.predicted_clv_90d or 0) for row in rows)
    average_clv = total_clv / count
    average_purchase_probability = sum(
        float(row.prob_purchase or 0) for row in rows
    ) / count
    average_expected_transactions = sum(
        float(row.expected_transactions or 0) for row in rows
    ) / count
    cold_start_count = sum(1 for row in rows if row.is_cold_start)

    segments: dict[str, int] = {}
    for row in rows:
        name = row.segment or "Unassigned"
        segments[name] = segments.get(name, 0) + 1

    return {
        "model_version": model_version,
        "count": count,
        "total_predicted_clv": round(total_clv, 2),
        "average_predicted_clv": round(average_clv, 2),
        "average_purchase_probability": round(average_purchase_probability, 6),
        "average_expected_transactions": round(average_expected_transactions, 4),
        "cold_start_count": cold_start_count,
        "cold_start_share": round(cold_start_count / count, 6),
        "segments": segments,
        "note": "CLV values are model predictions, not actual realized revenue.",
    }


# Run with:
# python -m uvicorn clv.api:app --host 127.0.0.1 --port 8000 --reload
