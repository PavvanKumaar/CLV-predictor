"""Conditional count/value models and held-out CLV evaluation."""
import math

import numpy as np
from sklearn.dummy import DummyRegressor
from sklearn.linear_model import GammaRegressor, PoissonRegressor
from sklearn.metrics import mean_absolute_error, mean_poisson_deviance, mean_squared_error
from sklearn.pipeline import Pipeline
from sklearn.base import BaseEstimator, RegressorMixin

from clv.features import FEATURES
from clv.ml import preprocessing


class NegativeBinomialRegressor(RegressorMixin, BaseEstimator):
    """Fixed-dispersion NB GLM; conservative alternative to Poisson."""

    def fit(self, x, y):
        import statsmodels.api as sm
        # Constant/missing features and correlated columns can be redundant even
        # without an explicit intercept. Fit an independent basis of training X.
        design = np.asarray(x, dtype=float)
        _, singular_values, right = np.linalg.svd(design, full_matrices=False)
        tolerance = singular_values[0] * max(design.shape) * np.finfo(float).eps
        rank = int((singular_values > tolerance).sum())
        if rank == 0:
            raise ValueError("Negative binomial training design has no independent columns")
        self.basis_ = right[:rank].T
        self.result_ = sm.GLM(y, design @ self.basis_, family=sm.families.NegativeBinomial(alpha=1)).fit(maxiter=50)
        return self

    def predict(self, x):
        design = np.asarray(x, dtype=float)
        # Previously saved models used the original columns directly.
        if hasattr(self, "basis_"):
            design = design @ self.basis_
        return self.result_.predict(design)


def options(stage):
    if stage == "count":
        models = {"mean": DummyRegressor(strategy="mean"), "poisson": PoissonRegressor(alpha=1, max_iter=500)}
        try:
            import statsmodels.api  # noqa: F401
            models["negative_binomial"] = NegativeBinomialRegressor()
        except ImportError:
            pass
        try:
            from lightgbm import LGBMRegressor
            models["lightgbm_poisson"] = LGBMRegressor(objective="poisson", n_estimators=120, num_leaves=15, min_child_samples=15, verbosity=-1, random_state=42, n_jobs=1)
        except ImportError:
            pass
        try:
            from xgboost import XGBRegressor
            models["xgboost_poisson"] = XGBRegressor(objective="count:poisson", n_estimators=120, max_depth=4, learning_rate=.05, random_state=42, n_jobs=1)
        except ImportError:
            pass
    else:
        models = {"mean": DummyRegressor(strategy="mean"), "gamma": GammaRegressor(alpha=1, max_iter=500)}
        try:
            from lightgbm import LGBMRegressor
            models["lightgbm_gamma"] = LGBMRegressor(objective="gamma", n_estimators=120, num_leaves=15, min_child_samples=15, verbosity=-1, random_state=42, n_jobs=1)
        except ImportError:
            pass
        try:
            from catboost import CatBoostRegressor
            models["catboost_log"] = CatBoostRegressor(iterations=120, depth=4, verbose=False, random_seed=42, thread_count=1, allow_writing_files=False)
        except ImportError:
            pass
        try:
            from xgboost import XGBRegressor
            models["xgboost_log"] = XGBRegressor(n_estimators=120, max_depth=4, learning_rate=.05, random_state=42, n_jobs=1)
        except ImportError:
            pass
    return models


def estimate(model, x, logarithmic=False):
    raw = model.predict(x[FEATURES])
    return np.maximum(np.expm1(raw) if logarithmic else raw, .01)


def scores(actual, predicted, count=False):
    if len(actual) == 0:
        return {"n": 0, "rmse": None, "mae": None, **({"poisson_deviance": None} if count else {})}
    result = {"n": len(actual), "rmse": float(np.sqrt(mean_squared_error(actual, predicted))), "mae": float(mean_absolute_error(actual, predicted)),
              "actual_mean": float(np.mean(actual)), "predicted_mean": float(np.mean(predicted)),
              "mean_bias": float(np.mean(np.asarray(predicted) - np.asarray(actual)))}
    if count:
        result["poisson_deviance"] = float(mean_poisson_deviance(actual, np.maximum(predicted, .01)))
    return result


def fit_stage(stage, train_x, train_y, valid_x, valid_y, test_x, test_y):
    label = "transaction_count" if stage == "count" else "mean_order_value"
    train_mask = (train_y.purchased == 1) & ~train_x.is_cold_start
    valid_mask = (valid_y.purchased == 1) & ~valid_x.is_cold_start
    test_mask = (test_y.purchased == 1) & ~test_x.is_cold_start
    if train_mask.sum() < 10 or valid_mask.sum() == 0:
        raise ValueError(f"Stage {stage} needs at least 10 established training purchasers and validation purchasers")
    models, comparisons, fitted = options(stage), {}, {}
    for name, estimator in models.items():
        logarithmic = name.endswith("_log")
        model = Pipeline([("preprocess", preprocessing()), ("model", estimator)])
        values = train_y.loc[train_mask, label].astype(float)
        model.fit(train_x.loc[train_mask, FEATURES], np.log1p(values) if logarithmic else values)
        predicted = estimate(model, valid_x.loc[valid_mask], logarithmic)
        comparisons[name] = scores(valid_y.loc[valid_mask, label].astype(float), predicted, stage == "count")
        fitted[name] = (model, logarithmic)
    primary, secondary = ("mae", "rmse") if stage == "value" else ("rmse", "mae")
    winner = min(comparisons, key=lambda name: (comparisons[name][primary], comparisons[name][secondary], name))
    model, logarithmic = fitted[winner]
    test_metrics = scores(test_y.loc[test_mask, label].astype(float), estimate(model, test_x.loc[test_mask], logarithmic), stage == "count")
    return {"winner": winner, "validation": comparisons, "test": test_metrics, "model": model, "logarithmic": logarithmic,
            "training_purchasers": int(train_mask.sum()),
            "selection": f"minimum validation {primary}; {secondary} breaks ties",
            "evaluation_population": "established customers who purchased in the outcome window"}


def combined_scores(actual, predicted):
    result = scores(actual, predicted)
    total = float(np.sum(actual))
    result["actual_revenue"] = total
    result["predicted_revenue"] = float(np.sum(predicted))
    result["aggregate_error_pct"] = float((np.sum(predicted) - total) / total * 100) if total else None
    top = np.argsort(-np.asarray(predicted), kind="stable")[:max(1, math.ceil(len(actual) * .1))]
    result["top_decile_revenue_share"] = float(np.asarray(actual)[top].sum() / total) if total else None
    return result
