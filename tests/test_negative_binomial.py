import warnings

import joblib
import numpy as np
import pytest

pytest.importorskip("statsmodels")
from statsmodels.tools.sm_exceptions import SingularMatrixWarning
from clv.regressors import NegativeBinomialRegressor


def test_redundant_and_zero_columns_fit_and_reload(tmp_path):
    rng = np.random.default_rng(42)
    feature = rng.normal(size=100)
    independent = np.column_stack([np.ones(100), feature])
    redundant = np.column_stack([independent, feature * 2, np.zeros(100), np.ones(100)])
    labels = rng.poisson(np.exp(.5 + .2 * feature)) + 1
    with warnings.catch_warnings():
        warnings.simplefilter("error", SingularMatrixWarning)
        model = NegativeBinomialRegressor().fit(redundant, labels)
        reference = NegativeBinomialRegressor().fit(independent, labels)
    assert model.basis_.shape[1] == 2
    np.testing.assert_allclose(model.predict(redundant), reference.predict(independent), rtol=1e-5)
    joblib.dump(model, tmp_path / "model.joblib")
    np.testing.assert_allclose(joblib.load(tmp_path / "model.joblib").predict(redundant), model.predict(redundant))
