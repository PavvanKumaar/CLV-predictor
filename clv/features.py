import hashlib
import json
from datetime import timedelta

import numpy as np
import pandas as pd
from sqlalchemy import select

from clv.data import timestamp, transactions_frame
from clv.models import Features, IngestionBatch, Label, Snapshot

NUMERIC_FEATURES = ["recency", "frequency", "T", "avg_order_value", "monetary_std", "purchase_velocity", "interpurchase_time_mean", "interpurchase_time_std", "category_diversity", "last_order_recency_ratio", "category_missing"]
CATEGORICAL_FEATURES = ["tenure_bucket"]
FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES


def build_frames(transactions, cutoff, observation_end, horizon=90):
    cutoff, observation_end = timestamp(cutoff), timestamp(observation_end)
    if horizon <= 0 or observation_end < cutoff + timedelta(days=horizon):
        raise ValueError("Every label requires a fully observed positive horizon")
    if len(transactions) and (transactions.purchased_at >= observation_end).any():
        raise ValueError("observation_end must be exclusive and after all source transactions")
    history = transactions[transactions.purchased_at < cutoff]
    future = transactions[(transactions.purchased_at >= cutoff) & (transactions.purchased_at < cutoff + timedelta(days=horizon))]
    feature_rows, label_rows = [], []
    for customer_id, group in history.groupby("customer_id", sort=True):
        group = group.sort_values(["purchased_at", "order_id"])
        dates = group.purchased_at
        tenure = (cutoff - dates.iloc[0]).total_seconds() / 86400
        recency = (cutoff - dates.iloc[-1]).total_seconds() / 86400
        intervals = dates.diff().dt.total_seconds().dropna() / 86400
        # Six equal, backward-looking 30-day bins, oldest to newest.
        ages = (cutoff - dates).dt.total_seconds() / 86400
        bins = [int(((ages > 30 * i) & (ages <= 30 * (i + 1))).sum()) for i in range(5, -1, -1)]
        row = {"customer_id": customer_id, "recency": recency, "frequency": len(group), "T": tenure,
               "avg_order_value": float(group.amount.mean()), "monetary_std": float(group.amount.std(ddof=0)),
               "purchase_velocity": float(np.polyfit(np.arange(6), bins, 1)[0]),
               "interpurchase_time_mean": float(intervals.mean()) if len(intervals) else 0.0,
               "interpurchase_time_std": float(intervals.std(ddof=0)) if len(intervals) else 0.0,
               "category_diversity": int(group.category.dropna().nunique()), "category_missing": int(group.category.isna().all()),
               "tenure_bucket": "new" if tenure < 30 else "established" if tenure < 365 else "loyal",
               "last_order_recency_ratio": recency / max(tenure, 1e-9), "is_cold_start": len(group) < 2 or tenure < 30}
        feature_rows.append(row)
        target = future[future.customer_id == customer_id]
        label_rows.append({"customer_id": customer_id, "purchased": int(len(target) > 0), "transaction_count": len(target), "revenue": float(target.amount.sum()), "mean_order_value": float(target.amount.mean()) if len(target) else None})
    return pd.DataFrame(feature_rows), pd.DataFrame(label_rows)


def snapshot(session, cutoff, observation_end, horizon=90):
    frame = transactions_frame(session)
    features, labels = build_frames(frame, cutoff, observation_end, horizon)
    if features.empty:
        raise ValueError("No customer history exists before cutoff")
    batches = list(session.scalars(select(IngestionBatch.id).order_by(IngestionBatch.id)))
    fingerprint = hashlib.sha256(json.dumps(batches).encode()).hexdigest()
    cutoff, observation_end = timestamp(cutoff), timestamp(observation_end)
    identity = hashlib.sha256(f"v1|{fingerprint}|{cutoff.isoformat()}|{observation_end.isoformat()}|{horizon}".encode()).hexdigest()
    if not session.get(Snapshot, identity):
        session.add(Snapshot(snapshot_id=identity, cutoff=cutoff, observation_end=observation_end, horizon_days=horizon, dataset_fingerprint=fingerprint))
        session.flush()
        for row in features.to_dict("records"):
            session.add(Features(snapshot_id=identity, customer_id=row["customer_id"], is_cold_start=row["is_cold_start"], values={name: row[name] for name in FEATURES}))
        for row in labels.to_dict("records"):
            if pd.isna(row["mean_order_value"]):
                row["mean_order_value"] = None
            session.add(Label(snapshot_id=identity, **row))
        session.commit()
    return identity, features, labels
