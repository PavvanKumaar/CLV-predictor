"""Ordered drift ablations using saved models; no retraining or test-based selection."""
import argparse
import copy
import json
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from clv.ml import predict, metrics
from clv.drift import fit_sigmoid
from clv.revenue import compose, fit_cold_fallback, predict_cold_fallback, fit_calibration, apply_calibration
from clv.regressors import estimate, combined_scores, scores


def compare(directory):
    directory = Path(directory)
    bundle = joblib.load(directory / "full_model.joblib")
    frames = {name: pd.read_csv(directory / f"{name}_features.csv") for name in ("train", "validation", "test")}
    labels = {name: pd.read_csv(directory / f"{name}_labels.csv") for name in frames}
    for name, x in frames.items():
        if "first_order_value" not in x:
            raise ValueError("Use a full run with exported first_order_value")
        if not x.customer_id.equals(labels[name].customer_id):
            raise ValueError("Feature and label customer IDs must align")
    base = copy.copy(bundle)
    base.pop("probability_calibration", None)
    calibrated = copy.copy(base)
    v, t, tr = frames["validation"], frames["test"], frames["train"]
    vy, ty, train_y = labels["validation"], labels["test"], labels["train"]
    warm = ~v.is_cold_start
    calibrated["probability_calibration"] = fit_sigmoid(predict(base, v)[warm], vy.purchased[warm])
    count = {name: np.maximum(estimate(bundle["count_model"], x), 1) for name, x in frames.items()}
    value = {name: estimate(bundle["value_model"], x, bundle["value_logarithmic"]) for name, x in frames.items()}
    result = {"source_run": directory.name, "note": "Validation fits; historical test diagnostics only. No automatic winner selection.", "steps": {}}
    def evaluate(name, classifier, prior, buckets, scalar=False, count_factor=1):
        fallback = fit_cold_fallback(tr.first_order_value, train_y.revenue, tr.is_cold_start, prior, buckets)
        raw = {}
        for split in ("validation", "test"):
            x = frames[split]
            raw[split] = compose(predict(classifier, x), np.maximum(count[split] * count_factor, 1), value[split],
                                 x.is_cold_start, predict_cold_fallback(x.first_order_value, fallback))
        correction = fit_calibration(vy.revenue, raw["validation"]) if scalar else {"method": "none"}
        predicted = apply_calibration(raw["test"], correction)
        result["steps"][name] = {"combined": combined_scores(ty.revenue.to_numpy(), predicted),
            "classifier_test": metrics(ty.purchased, predict(classifier, t)), "cold_fallback": fallback,
            "revenue_correction": correction, "count_factor": count_factor,
            "cohorts": {cohort: combined_scores(ty.revenue[mask].to_numpy(), predicted[mask])
                        for cohort, mask in (("cold_start", t.is_cold_start), ("established", ~t.is_cold_start))}}
    evaluate("0_raw_baseline", base, 10, 4)
    evaluate("1_classifier_sigmoid", calibrated, 10, 4)
    evaluate("2_bucket_shrinkage", calibrated, 50, 2)
    evaluate("3_shared_scalar", calibrated, 50, 2, scalar=True)
    for split in ("validation", "test"):
        x, y = frames[split], labels[split]
        mask = ~x.is_cold_start & y.purchased.eq(1)
        result[f"stage2_{split}"] = scores(y.transaction_count[mask], count[split][mask], True)
    # Classifier calibration does not change a separately fitted conditional count model.
    factor = result["stage2_validation"]["actual_mean"] / result["stage2_validation"]["predicted_mean"]
    evaluate("4_count_scalar_without_revenue_scalar", calibrated, 50, 2, count_factor=factor)
    evaluate("4_count_scalar_with_refitted_revenue_scalar", calibrated, 50, 2, scalar=True, count_factor=factor)
    mask = ~t.is_cold_start & ty.purchased.eq(1)
    result["stage2_test_corrected"] = scores(ty.transaction_count[mask], np.maximum(count["test"][mask] * factor, 1), True)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_directory")
    parser.add_argument("--output", default="data/drift-comparison.json")
    args = parser.parse_args()
    result = compare(args.run_directory)
    Path(args.output).write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    print(pd.DataFrame({name: step["combined"] for name, step in result["steps"].items()}).T[
        ["aggregate_error_pct", "mae", "rmse"]].to_string())
