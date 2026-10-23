"""Shared raw CLV composition and validation-only revenue calibration."""
import numpy as np


def compose(probability, count, value, cold_mask, cold_clv):
    return np.where(cold_mask, cold_clv, np.asarray(probability) * np.maximum(count, 1) * np.asarray(value))


def fit_calibration(actual_validation, raw_validation):
    actual, raw = np.asarray(actual_validation, dtype=float), np.asarray(raw_validation, dtype=float)
    if actual.shape != raw.shape or not actual.size:
        raise ValueError("Calibration requires aligned, nonempty validation outcomes and predictions")
    if not np.isfinite(np.r_[actual, raw]).all() or (np.r_[actual, raw] < 0).any():
        raise ValueError("Calibration requires finite nonnegative revenue")
    predicted_total = float(raw.sum())
    # A zero total cannot be corrected by multiplication; preserve predictions explicitly.
    return {"method": "validation_revenue_ratio", "factor": float(actual.sum() / predicted_total) if predicted_total else 1.0,
            "status": "fitted" if predicted_total else "identity_zero_predicted_revenue",
            "fit_population": "all validation customers including cold start",
            "actual_validation_revenue": float(actual.sum()), "raw_validation_revenue": predicted_total}


def apply_calibration(raw, calibration):
    if calibration["method"] == "none":
        return np.asarray(raw, dtype=float)
    if calibration["method"] == "isotonic":
        return np.interp(raw, calibration["x_thresholds"], calibration["y_thresholds"])
    return np.asarray(raw) * calibration["factor"]


def fit_postprocessing(training_revenue, actual_validation, raw_validation, cold_validation,
                       method="isotonic", cap_quantile=None, separate_cohorts=True, established_method="none"):
    """Fit optional cap on validation revenue, then calibrate capped outputs."""
    from sklearn.isotonic import IsotonicRegression
    if method not in {"none", "scalar", "isotonic"} or established_method not in {"none", "scalar", "isotonic"}:
        raise ValueError("Unknown revenue calibration method")
    if cap_quantile is not None and not 0 < cap_quantile <= 1:
        raise ValueError("Revenue cap quantile must be in (0, 1]")
    training = np.asarray(training_revenue, dtype=float)
    actual = np.asarray(actual_validation, dtype=float)
    raw = np.asarray(raw_validation, dtype=float)
    cold = np.asarray(cold_validation, dtype=bool)
    if not training.size or not np.isfinite(training).all() or (training < 0).any():
        raise ValueError("Revenue cap requires finite nonnegative training outcomes")
    fit_calibration(actual, raw)  # Validate the shared revenue contract.
    if cold.shape != raw.shape:
        raise ValueError("Cold-start mask must match validation predictions")
    cap = float(np.quantile(actual, cap_quantile)) if cap_quantile is not None else None
    capped = np.minimum(raw, cap) if cap is not None else raw

    def fit_group(mask, group_method):
        if not mask.any():
            return {"method": "none", "status": "identity_no_validation_customers", "n": 0}
        if group_method == "scalar":
            fitted = fit_calibration(actual[mask], capped[mask])
        elif group_method == "isotonic":
            model = IsotonicRegression(y_min=0, out_of_bounds="clip").fit(capped[mask], actual[mask])
            fitted = {"method": "isotonic", "status": "fitted",
                      "x_thresholds": model.X_thresholds_.tolist(), "y_thresholds": model.y_thresholds_.tolist()}
        else:
            fitted = {"method": "none", "status": "disabled"}
        fitted.update(n=int(mask.sum()), fit_population="validation customers in this cohort after capping")
        return fitted

    masks = {"cold_start": cold, "established": ~cold} if separate_cohorts else {"all": np.ones(len(raw), dtype=bool)}
    return {"method": "cap_then_calibrate", "calibration_method": method,
            "cap": cap, "cap_quantile": cap_quantile, "cap_fit_population": "validation revenue only",
            "separate_cohorts": separate_cohorts,
            "cohorts": {name: fit_group(mask, established_method if name == "established" else method) for name, mask in masks.items()},
            "order": ["raw_combination", "validation_fitted_cap", "validation_fitted_calibration"]}


def apply_postprocessing(raw, cold_mask, config):
    raw, cold = np.asarray(raw, dtype=float), np.asarray(cold_mask, dtype=bool)
    if raw.shape != cold.shape:
        raise ValueError("Cold-start mask must match predictions")
    capped = np.minimum(raw, config["cap"]) if config["cap"] is not None else raw.copy()
    if not config["separate_cohorts"]:
        return apply_calibration(capped, config["cohorts"]["all"])
    result = capped.copy()
    for name, mask in (("cold_start", cold), ("established", ~cold)):
        result[mask] = apply_calibration(capped[mask], config["cohorts"][name])
    return result


def fit_cold_fallback(first_order_values, revenue, cold_mask, prior_strength=50, n_buckets=2):
    """Training-only first-order quartiles with shrinkage for sparse buckets."""
    values, actual, cold = np.asarray(first_order_values, float), np.asarray(revenue, float), np.asarray(cold_mask, bool)
    if values.shape != actual.shape or cold.shape != actual.shape or actual.ndim != 1 or not actual.size:
        raise ValueError("Cold fallback requires aligned nonempty training arrays")
    if not np.isfinite(np.r_[values, actual]).all() or (np.r_[values, actual] < 0).any():
        raise ValueError("Cold fallback requires finite nonnegative training values")
    if n_buckets not in (2, 4):
        raise ValueError("Cold-start bucket count must be 2 or 4")
    if prior_strength <= 0:
        raise ValueError("Cold-start prior strength must be positive")
    prior = float((actual[cold].sum() + prior_strength * actual.mean()) / (cold.sum() + prior_strength))
    edges = np.unique(np.quantile(values[cold], np.arange(1, n_buckets) / n_buckets)).tolist() if cold.any() else []
    if cold.any():
        edges = [edge for edge in edges if values[cold].min() < edge < values[cold].max()]
    buckets = np.searchsorted(edges, values, side="right")
    estimates, counts = [], []
    for index in range(len(edges) + 1):
        mask = cold & (buckets == index)
        counts.append(int(mask.sum()))
        estimates.append(float((actual[mask].sum() + prior_strength * prior) / (mask.sum() + prior_strength)))
    return {"method": "first_order_value_buckets", "fit_population": "training cold-start customers only",
            "edges": edges, "estimates": estimates, "counts": counts, "prior": prior, "prior_strength": prior_strength, "requested_buckets": n_buckets}


def predict_cold_fallback(first_order_values, config):
    buckets = np.searchsorted(config["edges"], np.asarray(first_order_values, float), side="right")
    return np.asarray(config["estimates"])[buckets]
