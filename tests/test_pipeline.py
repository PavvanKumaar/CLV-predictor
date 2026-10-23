import joblib
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from clv.api import app
from clv.cli import migrate
from clv.data import ingest
from clv.db import session
from clv.ml import predict, train
from clv.models import Stage1Prediction
from clv.sample import generate


def test_pipeline_migrations_reload_and_api(tmp_path, monkeypatch):
    monkeypatch.setenv('DATABASE_URL', 'sqlite:///' + str(tmp_path / 'integration.db'))
    migrate()
    migrate()
    path = tmp_path / 'sample.csv'
    generate(path, customers=100)
    with session() as db:
        ingest(db, path)
        with pytest.raises(ValueError, match='90 days'):
            train(db, '2025-01-01', '2025-02-01', '2025-07-01', '2025-10-01')
        report = train(db, '2025-01-01', '2025-04-01', '2025-07-01', '2025-10-01', tmp_path / 'artifacts')
        assert db.scalar(select(func.count()).select_from(Stage1Prediction)) == report['test']['n']
    directory = report['artifact_path']
    bundle = joblib.load(directory + '/model.joblib')
    features = pd.read_csv(directory + '/test_features.csv')
    saved = pd.read_csv(directory + '/predictions.csv')
    np.testing.assert_allclose(predict(bundle, features), saved.prob_purchase, atol=1e-14)
    assert saved.prob_purchase.between(0,1).all()
    client = TestClient(app)
    assert client.get('/health').status_code == 200
    assert client.get('/model/status').json()['winner'] == report['winner']
    assert len(client.get('/stage1/predictions?limit=3').json()) == 3
    assert client.get('/stage1/predictions?limit=0').status_code == 422
    assert client.get('/customers').status_code == 200
