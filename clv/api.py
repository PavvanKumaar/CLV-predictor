from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import select, text

from clv.db import session
from clv.models import Customer, ModelRun, Stage1Prediction

app = FastAPI(title="CLV Predictor — Stage 1", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], allow_methods=["GET"], allow_headers=["*"])


def database():
    with session() as db:
        yield db


class PredictionResponse(BaseModel):
    customer_id: str
    model_version: str
    snapshot_id: str
    prob_purchase: float
    is_cold_start: bool


@app.get("/health")
def health(db=Depends(database)):
    db.execute(text("SELECT 1"))
    return {"status": "ok", "stage": 1}


@app.get("/customers")
def customers(limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0), db=Depends(database)):
    return [{"customer_id": row.customer_id} for row in db.scalars(select(Customer).order_by(Customer.customer_id).limit(limit).offset(offset))]


@app.get("/model/status")
def status(db=Depends(database)):
    row = db.scalar(select(ModelRun).order_by(ModelRun.trained_at.desc(), ModelRun.model_version.desc()).limit(1))
    if row is None:
        raise HTTPException(404, "No stage-one model has been trained")
    return {"status": row.status, **row.metadata_json}


@app.get("/stage1/predictions", response_model=list[PredictionResponse])
def predictions(model_version: str | None = None, limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0), db=Depends(database)):
    if model_version is None:
        run = db.scalar(select(ModelRun).order_by(ModelRun.trained_at.desc(), ModelRun.model_version.desc()).limit(1))
        if run is None:
            raise HTTPException(404, "No stage-one model has been trained")
        model_version = run.model_version
    rows = db.scalars(select(Stage1Prediction).where(Stage1Prediction.model_version == model_version).order_by(Stage1Prediction.prob_purchase.desc(), Stage1Prediction.customer_id).limit(limit).offset(offset))
    return [PredictionResponse.model_validate(row, from_attributes=True) for row in rows]
