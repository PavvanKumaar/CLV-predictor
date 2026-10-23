import numpy as np
import pytest

from clv.revenue import (compose, fit_calibration, apply_calibration,
                         fit_postprocessing, apply_postprocessing, fit_cold_fallback, predict_cold_fallback)


def test_validation_factor_is_reused_without_test_outcomes():
    calibration = fit_calibration([50, 50], [100, 100])
    assert calibration["factor"] == .5
    np.testing.assert_allclose(apply_calibration([200, 40], calibration), [100, 20])
    np.testing.assert_allclose(compose([.5, .9], [2, 5], [100, 200], [False, True], 80), [100, 80])


def test_calibration_zero_and_invalid_inputs():
    assert fit_calibration([10], [0])["factor"] == 1
    assert fit_calibration([0], [10])["factor"] == 0
    with pytest.raises(ValueError):
        fit_calibration([1], [np.nan])
    with pytest.raises(ValueError):
        fit_calibration([], [])


@pytest.mark.parametrize("count_method", ["none", "scalar"])
def test_full_training_saves_reusable_calibration_and_stage_diagnostics(tmp_path, monkeypatch, count_method):
    import joblib
    import pandas as pd
    from sklearn.dummy import DummyClassifier, DummyRegressor
    from clv.cli import migrate
    from clv.data import ingest
    from clv.db import session
    import clv.ml as ml
    import clv.regressors as regressors
    from clv.sample import generate

    monkeypatch.setenv("DATABASE_URL", "sqlite:///" + str(tmp_path / "training.db"))
    monkeypatch.setattr(ml, "candidates", lambda: ({"constant": DummyClassifier(strategy="prior")}, []))
    monkeypatch.setattr(regressors, "options", lambda stage: {"mean": DummyRegressor(strategy="mean")})
    migrate()
    source = tmp_path / "orders.csv"
    generate(source, customers=100)
    with session() as db:
        ingest(db, source)
        report = ml.train_full(db, "2025-01-01", "2025-04-01", "2025-07-01", "2025-10-01", tmp_path / "runs", count_calibration=count_method)
    from pathlib import Path
    directory = Path(report["artifact_path"])
    bundle = joblib.load(directory / "full_model.joblib")
    features = pd.read_csv(directory / "test_features.csv")
    saved = pd.read_csv(directory / "clv_predictions.csv")
    raw = compose(ml.predict(bundle, features),
        np.maximum(regressors.estimate(bundle["count_model"], features), 1) * bundle["count_calibration"]["factor"],
        regressors.estimate(bundle["value_model"], features, bundle["value_logarithmic"]),
        features.is_cold_start, predict_cold_fallback(features.first_order_value, bundle["cold_start_fallback"]))
    np.testing.assert_allclose(apply_postprocessing(raw, features.is_cold_start, bundle["revenue_calibration"]), saved.predicted_clv_90d)
    assert "mae" in report["stage3"]["selection"]
    assert "predicted_purchase_rate" in report["stage1"]["test"]
    assert "predicted_mean" in report["stage2"]["test"]
    assert "predicted_mean" in report["stage3"]["test"]
    assert sum(group["customer_count"] for group in report["cohort_test"].values()) == len(saved)
    assert (directory / "clv_report.png").is_file()
    assert not (directory / "calibration.png").exists()
    assert "cold_start_rate" not in report
    assert report["cold_start"]["population_share"] == saved.is_cold_start.mean()
    cold_labels = pd.read_csv(directory / "test_labels.csv").loc[saved.is_cold_start]
    assert report["cold_start"]["actual_revenue"] == pytest.approx(cold_labels.revenue.sum())
    assert report["cold_start"]["predicted_revenue"] == pytest.approx(saved.loc[saved.is_cold_start, "predicted_clv_90d"].sum())
    assert (directory / "clv_evaluation.csv").is_file()


def test_cap_is_fit_on_validation_then_scalar_fit_on_capped_validation():
    config = fit_postprocessing([0, 10], [100, 100], [200, 400], [False, False],
                                method="scalar", cap_quantile=1, separate_cohorts=False)
    assert config["cap"] == 100
    assert config["cohorts"]["all"]["factor"] == 1
    np.testing.assert_allclose(apply_postprocessing([500, 20], [False, True], config), [100, 20])


def test_separate_isotonic_cohorts_roundtrip_and_out_of_bounds():
    import json
    config = fit_postprocessing([1, 1000], [20, 20, 100, 200], [10, 10, 100, 200],
                                [True, True, False, False], cap_quantile=None, established_method="isotonic")
    config = json.loads(json.dumps(config, allow_nan=False))
    np.testing.assert_allclose(apply_postprocessing([10, 150, 9999], [True, False, False], config), [20, 150, 200])
    assert config["cap"] is None


def test_empty_cohort_and_zero_validation_revenue():
    config = fit_postprocessing([1, 2], [0, 0], [1, 2], [False, False], established_method="isotonic")
    assert config["cohorts"]["cold_start"]["status"] == "identity_no_validation_customers"
    np.testing.assert_allclose(apply_postprocessing([1, 1], [False, True], config), [0, 1])
    with pytest.raises(ValueError):
        fit_postprocessing([1], [1], [1], [True], cap_quantile=0)


def test_segmented_fallback_learns_training_buckets_and_handles_sparse_groups():
    import json
    config = fit_cold_fallback([10, 10, 100, 100], [10, 10, 200, 200], [True]*4)
    config = json.loads(json.dumps(config))
    predictions = predict_cold_fallback([1, 10000], config)
    assert predictions[0] < predictions[1]
    assert config["counts"] == [2, 2]
    no_cold = fit_cold_fallback([10, 20], [50, 70], [False, False])
    np.testing.assert_allclose(predict_cold_fallback([0, 1000], no_cold), [60, 60])


def test_default_postprocessing_leaves_raw_cohorts_unchanged():
    config = fit_postprocessing([1], [50, 100], [10, 20], [True, False], method="none")
    np.testing.assert_allclose(apply_postprocessing([100, 200], [True, False], config), [100, 200])


def test_stronger_prior_shrinks_bucket_difference():
    weak = fit_cold_fallback([10, 10, 100, 100], [10, 10, 200, 200], [True]*4, prior_strength=10)
    strong = fit_cold_fallback([10, 10, 100, 100], [10, 10, 200, 200], [True]*4, prior_strength=50)
    assert np.ptp(strong["estimates"]) < np.ptp(weak["estimates"])
