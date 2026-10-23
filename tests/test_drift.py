import json
import numpy as np
from clv.drift import fit_sigmoid, apply_sigmoid


def test_sigmoid_corrects_probability_bias_and_serializes():
    p = np.full(100, .2)
    y = np.r_[np.ones(60), np.zeros(40)]
    config = json.loads(json.dumps(fit_sigmoid(p, y)))
    assert abs(apply_sigmoid(p, config).mean() - .6) < .01
    assert np.isfinite(apply_sigmoid([0, 1], config)).all()
    assert fit_sigmoid([.1, .2], [0, 0])["method"] == "none"
