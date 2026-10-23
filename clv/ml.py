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
import numpy as np
import pandas as pd
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
from clv.models import CLVPrediction, ModelRun, Snapshot, Stage1Prediction


def metrics(y, probability):
    y, probability = np.asarray(y), np.asarray(probability)
    top = np.argsort(-probability, kind="stable")[:max(1, math.ceil(len(y) * 0.1))]
    base = float(y.mean())
    return {"n": len(y), "purchase_rate": base, "predicted_purchase_rate": float(probability.mean()), "mean_probability_bias": float(probability.mean() - base), "roc_auc": float(roc_auc_score(y, probability)) if len(np.unique(y)) == 2 else None,
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
    try:
        from xgboost import XGBClassifier
        result["xgboost"] = XGBClassifier(n_estimators=100, max_depth=4, learning_rate=0.05, objective="binary:logistic", tree_method="hist", random_state=42, n_jobs=1)
    except ImportError:
        skipped.append("xgboost")
    return result, skipped


def preprocessing():
    return ColumnTransformer([("numeric", Pipeline([("impute", SimpleImputer(strategy="median")), ("scale", StandardScaler())]), NUMERIC_FEATURES),
                              ("categorical", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CATEGORICAL_FEATURES)])


def predict(bundle, frame):
    probabilities = bundle["pipeline"].predict_proba(frame[FEATURES])[:, 1]
    from clv.drift import apply_sigmoid
    probabilities = apply_sigmoid(probabilities, bundle.get("probability_calibration", {}))
    cold_probability = bundle.get("cold_start_purchase_probability", bundle.get("cold_start_rate"))
    return np.where(frame.is_cold_start, cold_probability, probabilities)


def train(session, train_cutoff, validation_cutoff, test_cutoff, observation_end, artifact_root="artifacts", classifier_calibration="sigmoid"):
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
        bundle = {"pipeline": pipeline, "cold_start_purchase_probability": cold_rate, "features": FEATURES, "definition_version": "v1"}
        comparisons[name] = metrics(valid_y.purchased, predict(bundle, valid_x))
        bundles[name] = bundle
    # Validation alone selects the winner. Test results never influence this choice.
    winner = min(comparisons, key=lambda name: (comparisons[name]["brier"], -(comparisons[name]["roc_auc"] or 0), name))
    bundle = bundles[winner]
    raw_test_metrics = metrics(test_y.purchased, predict(bundle, test_x))
    raw_valid_probability = predict(bundle, valid_x)
    if classifier_calibration == "sigmoid":
        from clv.drift import fit_sigmoid
        mask = ~valid_x.is_cold_start
        bundle["probability_calibration"] = fit_sigmoid(raw_valid_probability[mask], valid_y.purchased[mask])
    elif classifier_calibration != "none":
        raise ValueError("Unknown classifier calibration")
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
    report = {"model_version": version, "winner": winner, "selection": "minimum validation Brier score; ROC-AUC breaks ties", "validation": comparisons,
              "test": test_metrics, "warm_test": metrics(test_y.purchased[~test_x.is_cold_start], probability[~test_x.is_cold_start]) if (~test_x.is_cold_start).any() else None,
              "cold_start_purchase_probability": cold_rate, "cold_start_population_share": float(test_x.is_cold_start.mean()), "cold_start_test_count": int(test_x.is_cold_start.sum()), "skipped_candidates": skipped,
              "snapshots": [x[0] for x in snapshots], "dataset_fingerprint": session.get(Snapshot, train_id).dataset_fingerprint,
              "parameters": json.loads(json.dumps({name: estimator.get_params() for name, estimator in estimators.items()}, default=str), parse_constant=lambda value: value),
              "cutoffs": [x.isoformat() for x in cutoffs], "observation_end": timestamp(observation_end).isoformat(),
              "feature_definition": "v1", "seed": 42, "python": platform.python_version(), "versions": {p: importlib.metadata.version(p) for p in ["pandas", "numpy", "scikit-learn", "SQLAlchemy"]},
              "artifact_path": str(directory), "auc_target_met": test_metrics["roc_auc"] is not None and test_metrics["roc_auc"] >= 0.75}
    report["classifier_calibration"] = bundle.get("probability_calibration", {"method": "none"})
    report["stage1_raw_test"] = raw_test_metrics
    report["stage1_calibration_validation"] = {"raw": metrics(valid_y.purchased, raw_valid_probability),
        "calibrated": metrics(valid_y.purchased, predict(bundle, valid_x)),
        "note": "Fit diagnostics on validation, not independent evaluation"}
    (directory / "metrics.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    session.add(ModelRun(model_version=version, status="stage1_complete", classifier_type=winner, classifier_auc=test_metrics["roc_auc"], metadata_json=report, artifact_path=str(directory)))
    session.flush()
    for row in predicted.to_dict("records"):
        session.add(Stage1Prediction(**row))
    session.commit()
    return report


def train_full(session, train_cutoff, validation_cutoff, test_cutoff, observation_end, artifact_root="artifacts",
               calibration_method="none", cap_quantile=None, separate_cohorts=True, established_calibration="none", classifier_calibration="sigmoid",
               cold_prior_strength=50, cold_buckets=2, count_calibration="none"):
    """Fit all stages on the same temporal snapshots; evaluate final CLV on test only."""
    from clv.regressors import combined_scores, estimate, fit_stage
    from clv.reports import generate_clv_report
    from clv.revenue import compose, fit_postprocessing, apply_postprocessing, fit_cold_fallback, predict_cold_fallback
    from clv.data import transactions_frame
    if cap_quantile is not None and not 0 < cap_quantile <= 1:
        raise ValueError("Revenue cap quantile must be in (0, 1]")
    if calibration_method not in {"none", "scalar", "isotonic"}:
        raise ValueError("Unknown revenue calibration method")
    report = train(session, train_cutoff, validation_cutoff, test_cutoff, observation_end, artifact_root, classifier_calibration)
    snapshots = [snapshot(session, cutoff, observation_end) for cutoff in (train_cutoff, validation_cutoff, test_cutoff)]
    (_, train_x, train_y), (_, valid_x, valid_y), (test_id, test_x, test_y) = snapshots
    count = fit_stage("count", train_x, train_y, valid_x, valid_y, test_x, test_y)
    value = fit_stage("value", train_x, train_y, valid_x, valid_y, test_x, test_y)
    directory = Path(report["artifact_path"])
    bundle = joblib.load(directory / "model.joblib")
    probability = predict(bundle, test_x)
    count_factor = 1.0
    if count_calibration == "scalar":
        purchaser_mask = valid_y.purchased.eq(1) & ~valid_x.is_cold_start
        valid_counts = np.maximum(estimate(count["model"], valid_x.loc[purchaser_mask], count["logarithmic"]), 1)
        count_factor = float(valid_y.transaction_count[purchaser_mask].mean() / valid_counts.mean())
    elif count_calibration != "none":
        raise ValueError("Unknown count calibration")
    count["test_raw"] = count["test"]
    count["drift_correction"] = {"method": count_calibration, "factor": count_factor,
        "fit_population": "established validation purchasers"}
    from clv.regressors import scores
    test_purchasers = test_y.purchased.eq(1) & ~test_x.is_cold_start
    count["test"] = scores(test_y.transaction_count[test_purchasers], np.maximum(
        np.maximum(estimate(count["model"], test_x.loc[test_purchasers], count["logarithmic"]), 1) * count_factor, 1), True)
    expected_count = np.maximum(np.maximum(estimate(count["model"], test_x, count["logarithmic"]), 1) * count_factor, 1)
    expected_value = estimate(value["model"], test_x, value["logarithmic"])
    # The fallback uses training outcomes only, with 10 prior observations.
    # Auxiliary first-order values are cutoff-safe and exported for bundle replay.
    orders = transactions_frame(session).sort_values(["purchased_at", "order_id"])
    for name, x, cutoff in zip(("train", "validation", "test"), (train_x, valid_x, test_x),
                              (train_cutoff, validation_cutoff, test_cutoff)):
        first = orders[orders.purchased_at < timestamp(cutoff)].groupby("customer_id").amount.first()
        x["first_order_value"] = x.customer_id.map(first)
        x.to_csv(directory / f"{name}_features.csv", index=False)
    cold_fallback = fit_cold_fallback(train_x.first_order_value, train_y.revenue, train_x.is_cold_start, cold_prior_strength, cold_buckets)
    test_cold_clv = predict_cold_fallback(test_x.first_order_value, cold_fallback)
    valid_cold_clv = predict_cold_fallback(valid_x.first_order_value, cold_fallback)
    cold = train_x.is_cold_start
    prior = float(train_y.revenue.mean())
    cold_clv = float((train_y.loc[cold, "revenue"].sum() + 10 * prior) / (int(cold.sum()) + 10))
    raw_clv = compose(probability, expected_count, expected_value, test_x.is_cold_start, test_cold_clv)
    valid_count = np.maximum(np.maximum(estimate(count["model"], valid_x, count["logarithmic"]), 1) * count_factor, 1)
    valid_value = estimate(value["model"], valid_x, value["logarithmic"])
    raw_valid_clv = compose(predict(bundle, valid_x), valid_count, valid_value, valid_x.is_cold_start, valid_cold_clv)
    calibration = fit_postprocessing(train_y.revenue, valid_y.revenue, raw_valid_clv, valid_x.is_cold_start,
                                     calibration_method, cap_quantile, separate_cohorts, established_calibration)
    predicted_clv = apply_postprocessing(raw_clv, test_x.is_cold_start, calibration)
    report["revenue_calibration"] = calibration
    capped_clv = np.minimum(raw_clv, calibration["cap"]) if calibration["cap"] is not None else raw_clv.copy()
    report["combined_capped"] = combined_scores(test_y.revenue.to_numpy(dtype=float), capped_clv)
    report["combined_raw"] = combined_scores(test_y.revenue.to_numpy(dtype=float), raw_clv)
    report["combined_validation"] = {
        "raw": combined_scores(valid_y.revenue.to_numpy(dtype=float), raw_valid_clv),
        "calibrated": combined_scores(valid_y.revenue.to_numpy(dtype=float), apply_postprocessing(raw_valid_clv, valid_x.is_cold_start, calibration)),
        "note": "Calibration fit diagnostics, not independent evaluation"}
    report["cohort_validation"] = {}
    final_valid_clv = apply_postprocessing(raw_valid_clv, valid_x.is_cold_start, calibration)
    for name, mask in (("cold_start", valid_x.is_cold_start), ("established", ~valid_x.is_cold_start)):
        report["cohort_validation"][name] = {
            "raw": combined_scores(valid_y.revenue[mask].to_numpy(dtype=float), raw_valid_clv[mask]),
            "calibrated": combined_scores(valid_y.revenue[mask].to_numpy(dtype=float), final_valid_clv[mask]),
            "note": "Calibration fit diagnostics, not independent evaluation"}
    report["cohort_test"] = {}
    for name, mask in (("cold_start", test_x.is_cold_start), ("established", ~test_x.is_cold_start)):
        report["cohort_test"][name] = {
            "customer_count": int(mask.sum()), "customer_share": float(mask.mean()),
            "raw": combined_scores(test_y.revenue[mask].to_numpy(dtype=float), raw_clv[mask]),
            "capped": combined_scores(test_y.revenue[mask].to_numpy(dtype=float), capped_clv[mask]),
            "calibrated": combined_scores(test_y.revenue[mask].to_numpy(dtype=float), predicted_clv[mask])}
    report["cold_start_bucket_test"] = []
    bucket_ids = np.searchsorted(cold_fallback["edges"], test_x.first_order_value, side="right")
    for bucket in range(len(cold_fallback["estimates"])):
        mask = test_x.is_cold_start & (bucket_ids == bucket)
        report["cold_start_bucket_test"].append({"bucket": bucket, "training_count": cold_fallback["counts"][bucket],
            "raw": combined_scores(test_y.revenue[mask].to_numpy(dtype=float), raw_clv[mask]),
            "calibrated": combined_scores(test_y.revenue[mask].to_numpy(dtype=float), predicted_clv[mask])})
    report["stage1"] = {"winner": report["winner"], "selection": report["selection"],
        "validation": report["validation"], "test": report["test"], "warm_test": report["warm_test"],
        "cold_start_purchase_probability": report["cold_start_purchase_probability"]}
    cold_scores = report["cohort_test"]["cold_start"]["calibrated"]
    report["cold_start"] = {**cold_scores,
        "purchase_probability": report["cold_start_purchase_probability"],
        "actual_purchase_rate": float(test_y.purchased[test_x.is_cold_start].mean()) if test_x.is_cold_start.any() else None,
        "population_share": report["cold_start_population_share"],
        "revenue_error_pct": cold_scores["aggregate_error_pct"],
        "prediction_path": "training first-order-value buckets, optional validation cap and cohort calibration"}
    pd.DataFrame({"customer_id": test_x.customer_id, "is_cold_start": test_x.is_cold_start,
                  "first_order_value": test_x.first_order_value, "cold_start_bucket_clv": test_cold_clv,
                  "raw_clv": raw_clv, "capped_clv": capped_clv,
                  "calibrated_clv": predicted_clv, "actual_revenue": test_y.revenue}).to_csv(directory / "clv_evaluation.csv", index=False)
    # These conditional components are unavailable for cold-start customers.
    expected_count = np.where(test_x.is_cold_start, 0, expected_count)
    expected_value = np.where(test_x.is_cold_start, 0, expected_value)
    combined = combined_scores(test_y.revenue.astype(float).to_numpy(), predicted_clv)
    thresholds = np.quantile(predicted_clv, [.25, .75])
    segments = np.where(predicted_clv >= thresholds[1], "VIP", np.where((probability < .3) & (test_x.frequency.to_numpy() >= 2), "At-Risk", np.where(predicted_clv >= thresholds[0], "Growth", "Low-Priority")))
    predictions = pd.DataFrame({"customer_id": test_x.customer_id, "snapshot_id": test_id, "model_version": report["model_version"],
                                "prob_purchase": probability, "expected_transactions": expected_count,
                                "expected_value_per_txn": expected_value, "predicted_clv_90d": predicted_clv,
                                "segment": segments, "is_cold_start": test_x.is_cold_start})
    predictions.to_csv(directory / "clv_predictions.csv", index=False)
    generate_clv_report(directory)
    full_bundle = {**bundle, "count_model": count["model"], "count_calibration": count["drift_correction"], "value_model": value["model"],
                   "value_logarithmic": value["logarithmic"], "cold_start_clv": cold_clv, "cold_start_fallback": cold_fallback, "segment_thresholds": thresholds, "revenue_calibration": calibration}
    joblib.dump(full_bundle, directory / "full_model.joblib")
    for stage, fitted in (("stage2", count), ("stage3", value)):
        report[stage] = {key: fitted[key] for key in ("winner", "selection", "evaluation_population", "validation", "test", "training_purchasers")}
    report["stage2"]["test_raw"] = count["test_raw"]
    report["stage2"]["drift_correction"] = count["drift_correction"]
    report["combined"] = combined
    report["cold_start_clv"] = cold_clv
    report["cold_start_fallback"] = cold_fallback
    report["cold_start_prediction_mean"] = float(predicted_clv[test_x.is_cold_start].mean()) if test_x.is_cold_start.any() else None
    report["combination_note"] = "Conditional stage-2 count times conditional stage-3 value assumes separability; measured against test revenue"
    (directory / "metrics.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    run = session.get(ModelRun, report["model_version"])
    run.status = "complete"
    run.count_regressor_type = count["winner"]
    run.count_regressor_rmse = count["test"]["rmse"]
    run.value_regressor_type = value["winner"]
    run.value_regressor_rmse = value["test"]["rmse"]
    run.combined_rmse = combined["rmse"]
    run.metadata_json = report
    session.add_all(CLVPrediction(**row) for row in predictions.to_dict("records"))
    session.commit()
    return report
