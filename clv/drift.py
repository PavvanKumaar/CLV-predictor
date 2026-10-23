"""Validation-fitted probability calibration for the selected classifier."""
import numpy as np
from sklearn.linear_model import LogisticRegression


def logits(probabilities):
    p = np.clip(np.asarray(probabilities, float), 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p)).reshape(-1, 1)


def fit_sigmoid(probabilities, outcomes):
    y = np.asarray(outcomes)
    if len(np.unique(y)) < 2:
        return {"method": "none", "status": "insufficient_validation_classes"}
    model = LogisticRegression(C=1, max_iter=1000).fit(logits(probabilities), y)
    return {"method": "sigmoid", "slope": float(model.coef_[0, 0]),
            "intercept": float(model.intercept_[0]), "n": len(y),
            "fit_population": "established validation customers"}


def apply_sigmoid(probabilities, config):
    if config.get("method") != "sigmoid":
        return np.asarray(probabilities)
    z = np.clip(config["slope"] * logits(probabilities).ravel() + config["intercept"], -700, 700)
    return 1 / (1 + np.exp(-z))
