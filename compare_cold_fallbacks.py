import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Helper: exit with a clear message if required data is missing
# ---------------------------------------------------------------------------
def abort(msg: str) -> None:
    print(f"[ERROR] {msg}", file=sys.stderr)
    sys.exit(1)

# ---------------------------------------------------------------------------
# 1. Locate validation feature/label CSVs
# ---------------------------------------------------------------------------
# The training command writes validation files inside the artifact directory of the run.
# The most recent run is identified by the artifact fingerprint in the request.
run_id = "f5b7a09325834ff1b734caf1a07d6754"
artifact_dir = Path("C:/CLV/CLV-predictor/artifacts") / run_id

features_path = artifact_dir / "validation_features.csv"
labels_path = artifact_dir / "validation_labels.csv"

if not features_path.is_file():
    abort(f"Validation features file not found at {features_path}")
if not labels_path.is_file():
    abort(f"Validation labels file not found at {labels_path}")

print(f"Loading validation data from {artifact_dir}…")
features = pd.read_csv(features_path)
labels = pd.read_csv(labels_path)

# ---------------------------------------------------------------------------
# 2. Verify required columns
# ---------------------------------------------------------------------------
required_feat_cols = {"customer_id", "is_cold_start", "first_order_value"}
required_label_cols = {"customer_id", "revenue"}

missing_feat = required_feat_cols - set(features.columns)
missing_lab = required_label_cols - set(labels.columns)

if missing_feat:
    abort(f"Missing columns in validation_features.csv: {sorted(missing_feat)}")
if missing_lab:
    abort(f"Missing columns in validation_labels.csv: {sorted(missing_lab)}")

# Ensure the two tables align on customer_id
if not features["customer_id"].equals(labels["customer_id"]):
    abort(
        "Customer IDs in validation_features.csv and validation_labels.csv do not align."
    )

# ---------------------------------------------------------------------------
# 3. Load cold‑start fallback configuration from metrics.json
# ---------------------------------------------------------------------------
metrics_path = artifact_dir / "metrics.json"
if not metrics_path.is_file():
    abort(f"metrics.json not found at {metrics_path}")

with metrics_path.open("r", encoding="utf-8") as f:
    metrics = json.load(f)

# Global scalar fallback
if "cold_start_clv" not in metrics:
    abort("Global cold‑start CLV (cold_start_clv) not present in metrics.json")
global_scalar = float(metrics["cold_start_clv"])

# Bucket fallback configuration
cold_fallback = metrics.get("cold_start_fallback")
if not cold_fallback:
    abort("cold_start_fallback section missing in metrics.json")

edges = cold_fallback.get("edges")
estimates = cold_fallback.get("estimates")
counts = cold_fallback.get("counts")
if edges is None or estimates is None or counts is None:
    abort("Cold‑start fallback configuration is incomplete (edges/estimates/counts missing).")

edges = list(map(float, edges))
estimates = list(map(float, estimates))
counts = list(map(int, counts))

# ---------------------------------------------------------------------------
# 4. Identify cold‑start customers in the validation set
# ---------------------------------------------------------------------------
cold_mask = features["is_cold_start"].astype(bool)
if not cold_mask.any():
    abort("No cold‑start customers found in the validation snapshot.")

cold_features = features[cold_mask].reset_index(drop=True)
cold_labels = labels[cold_mask].reset_index(drop=True)

# ---------------------------------------------------------------------------
# 5. Predictions
# ---------------------------------------------------------------------------
# Global scalar prediction – same value for every cold‑start customer
pred_global = np.full(len(cold_features), global_scalar, dtype=float)

# Bucket‑based prediction – assign each customer to a bucket using first_order_value
first_vals = cold_features["first_order_value"].astype(float).to_numpy()
# np.searchsorted works with a sorted list of edges; edges are already sorted.
bucket_ids = np.searchsorted(edges, first_vals, side="right")
# safety: bucket ids must be within range of estimates
if bucket_ids.max() >= len(estimates):
    abort("Bucket assignment produced an out‑of‑range index. Check edge configuration.")
pred_bucket = np.take(estimates, bucket_ids)

# ---------------------------------------------------------------------------
# 6. Evaluation helper
# ---------------------------------------------------------------------------
actual = cold_labels["revenue"].astype(float).to_numpy()

def evaluate(pred: np.ndarray, actual: np.ndarray):
    err = pred - actual
    mae = np.mean(np.abs(err))
    rmse = np.sqrt(np.mean(err ** 2))
    agg_err_pct = 100.0 * np.mean(err) / np.mean(actual) if np.mean(actual) != 0 else float("nan")
    return {
        "count": int(len(actual)),
        "actual_revenue_sum": float(actual.sum()),
        "predicted_revenue_sum": float(pred.sum()),
        "mae": mae,
        "rmse": rmse,
        "aggregate_error_pct": agg_err_pct,
    }

global_stats = evaluate(pred_global, actual)
bucket_stats = evaluate(pred_bucket, actual)

# ---------------------------------------------------------------------------
# 7. Bucket‑level breakdown
# ---------------------------------------------------------------------------
bucket_breakdown = []
for b_id in range(len(estimates)):
    mask = bucket_ids == b_id
    n = int(mask.sum())
    if n == 0:
        # Skip empty buckets – they may exist if the training data had no customers
        continue
    actual_mean = actual[mask].mean()
    pred_mean = pred_bucket[mask].mean()
    bucket_breakdown.append({
        "bucket": b_id,
        "customer_count": n,
        "actual_mean": float(actual_mean),
        "predicted_mean": float(pred_mean),
    })

# ---------------------------------------------------------------------------
# 8. Output results
# ---------------------------------------------------------------------------
print("=== Global scalar cold‑start fallback ===")
for k, v in global_stats.items():
    print(f"{k}: {v}")

print("\n=== Four‑bucket cold‑start fallback ===")
for k, v in bucket_stats.items():
    print(f"{k}: {v}")

print("\n=== Bucket‑level breakdown (validation cold‑start customers) ===")
for b in bucket_breakdown:
    print(
        f"Bucket {b['bucket']}: count={b['customer_count']}, "
        f"actual_mean={b['actual_mean']:.2f}, predicted_mean={b['predicted_mean']:.2f}"
    )

print("\nDone.")
