import importlib.metadata
import json
import math
import os
import platform
import uuid
from datetime import timedelta
from pathlib import Path

import joblib
os.environ.setdefault("MPLCONFIGDIR", str(Path("artifacts/.matplotlib").resolve()))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.calibration import calibration_curve
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, precision_score, recall_score, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from clv.data import timestamp
from clv.features import CATEGORICAL_FEATURES, FEATURES, NUMERIC_FEATURES, snapshot
from clv.models import ModelRun, Snapshot, Stage1Prediction


def metrics(y, probability):
    y, probability = np.asarray(y), np.asarray(probability)
    top = np.argsort(-probability, kind="stable")[:max(1, math.ceil(len(y) * 0.1))]
    base = float(y.mean())
    return {"n": len(y), "purchase_rate": base, "roc_auc": float(roc_auc_score(y, probability)) if len(np.unique(y)) == 2 else None,
            "pr_auc": float(average_precision_score(y, probability)) if y.sum() else None,
            "brier": float(brier_score_loss(y, probability)), "precision_at_0_5": float(precision_score(y, probability >= 0.5, zero_division=0)),
            "recall_at_0_5": float(recall_score(y, probability >= 0.5, zero_division=0)),
            "top_decile_lift": float(y[top].mean() / base) if base else None}


def candidates():
    result = {"constant": DummyClassifier(strategy="prior"), "logistic": LogisticRegression(max_iter=2000, random_state=42),
              "random_forest": RandomForestClassifier(n_estimators=150, min_samples_leaf=8, random_state=42, n_jobs=1)}
    skipped = []
    try:
        from lightgbm import LGBMClassifier
        result["lightgbm"] = LGBMClassifier(n_estimators=100, num_leaves=15, min_child_samples=15, verbosity=-1, random_state=42, n_jobs=1)
    except ImportError:
        skipped.append("lightgbm")
    try:
        from catboost import CatBoostClassifier
        result["catboost"] = CatBoostClassifier(iterations=100, depth=4, verbose=False, random_seed=42, thread_count=1, allow_writing_files=False)
    except ImportError:
        skipped.append("catboost")
    return result, skipped


def preprocessing():
    return ColumnTransformer([("numeric", Pipeline([("impute", SimpleImputer(strategy="median")), ("scale", StandardScaler())]), NUMERIC_FEATURES),
                              ("categorical", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CATEGORICAL_FEATURES)])


def predict(bundle, frame):
    probabilities = bundle["pipeline"].predict_proba(frame[FEATURES])[:, 1]
    return np.where(frame.is_cold_start, bundle["cold_start_rate"], probabilities)


def train(session, train_cutoff, validation_cutoff, test_cutoff, observation_end, artifact_root="artifacts"):
    cutoffs = [timestamp(x) for x in (train_cutoff, validation_cutoff, test_cutoff)]
    if any(a + timedelta(days=90) > b for a, b in zip(cutoffs, cutoffs[1:])):
        raise ValueError("Cutoffs must be chronological with at least 90 days between them")
    snapshots = [snapshot(session, cutoff, observation_end) for cutoff in cutoffs]
    train_id, train_x, train_y = snapshots[0]
    _, valid_x, valid_y = snapshots[1]
    test_id, test_x, test_y = snapshots[2]
    warm = ~train_x.is_cold_start
    y = train_y.purchased[warm]
    if len(np.unique(y)) < 2 or len(y) < 10:
        raise ValueError("Training needs at least 10 established customers and both target classes")
    cold = train_x.is_cold_start
    cold_rate = float((train_y.purchased[cold].sum() + train_y.purchased.mean() * 10) / (cold.sum() + 10))
    estimators, skipped = candidates()
    comparisons, bundles = {}, {}
    for name, estimator in estimators.items():
        pipeline = Pipeline([("preprocess", preprocessing()), ("model", estimator)])
        pipeline.fit(train_x.loc[warm, FEATURES], y)
        bundle = {"pipeline": pipeline, "cold_start_rate": cold_rate, "features": FEATURES, "definition_version": "v1"}
        comparisons[name] = metrics(valid_y.purchased, predict(bundle, valid_x))
        bundles[name] = bundle
    # Validation alone selects the winner. Test results never influence this choice.
    winner = min(comparisons, key=lambda name: (comparisons[name]["brier"], -(comparisons[name]["roc_auc"] or 0), name))
    bundle = bundles[winner]
    probability = predict(bundle, test_x)
    test_metrics = metrics(test_y.purchased, probability)
    version = uuid.uuid4().hex
    directory = Path(artifact_root).resolve() / version
    directory.mkdir(parents=True, exist_ok=False)
    bundle.update({"model_version": version, "classifier_type": winner, "train_snapshot": train_id})
    joblib.dump(bundle, directory / "model.joblib")
    predicted = test_x[["customer_id", "is_cold_start"]].copy()
    predicted["snapshot_id"], predicted["model_version"] = test_id, version
    predicted["prob_purchase"] = probability
    predicted.to_csv(directory / "predictions.csv", index=False)
    for name, (identity, x, labels) in zip(["train", "validation", "test"], snapshots):
        x.to_csv(directory / f"{name}_features.csv", index=False)
        labels.to_csv(directory / f"{name}_labels.csv", index=False)
    fraction, mean = calibration_curve(test_y.purchased, probability, n_bins=10, strategy="quantile")
    fig, axis = plt.subplots()
    axis.plot([0, 1], [0, 1], "--", color="gray")
    axis.plot(mean, fraction, "o-")
    axis.set(xlabel="Predicted purchase probability", ylabel="Observed purchase rate", title="Stage 1: untouched test period")
    fig.savefig(directory / "calibration.png", bbox_inches="tight")
    plt.close(fig)
    order = np.argsort(-probability, kind="stable")
    lift = pd.DataFrame({"fraction_customers": np.arange(1, len(order)+1) / len(order), "cumulative_purchases": np.cumsum(test_y.purchased.to_numpy()[order])})
    lift.to_csv(directory / "lift.csv", index=False)
    fig, axis = plt.subplots()
    denominator = max(int(test_y.purchased.sum()), 1)
    axis.plot(lift.fraction_customers, lift.cumulative_purchases / denominator)
    axis.plot([0, 1], [0, 1], "--", color="gray")
    axis.set(xlabel="Fraction of ranked customers", ylabel="Fraction of actual purchasers", title="Stage 1: cumulative gains")
    fig.savefig(directory / "lift.png", bbox_inches="tight")
    plt.close(fig)
    report = {"model_version": version, "winner": winner, "selection": "minimum validation Brier score; ROC-AUC breaks ties", "validation": comparisons,
              "test": test_metrics, "warm_test": metrics(test_y.purchased[~test_x.is_cold_start], probability[~test_x.is_cold_start]) if (~test_x.is_cold_start).any() else None,
              "cold_start_rate": cold_rate, "cold_start_test_count": int(test_x.is_cold_start.sum()), "skipped_candidates": skipped,
              "snapshots": [x[0] for x in snapshots], "dataset_fingerprint": session.get(Snapshot, train_id).dataset_fingerprint,
              "parameters": {name: estimator.get_params() for name, estimator in estimators.items()},
              "cutoffs": [x.isoformat() for x in cutoffs], "observation_end": timestamp(observation_end).isoformat(),
              "feature_definition": "v1", "seed": 42, "python": platform.python_version(), "versions": {p: importlib.metadata.version(p) for p in ["pandas", "numpy", "scikit-learn", "SQLAlchemy"]},
              "artifact_path": str(directory), "auc_target_met": test_metrics["roc_auc"] is not None and test_metrics["roc_auc"] >= 0.75}
    (directory / "metrics.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    session.add(ModelRun(model_version=version, status="stage1_complete", classifier_type=winner, classifier_auc=test_metrics["roc_auc"], metadata_json=report, artifact_path=str(directory)))
    session.flush()
    for row in predicted.to_dict("records"):
        session.add(Stage1Prediction(**row))
    session.commit()
    return report
