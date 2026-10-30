import json
import os

import pytest
from fastapi import HTTPException

from clv.api import get_model_metrics


def artifact(root, version, timestamp, report=None):
    directory = root / version
    directory.mkdir()
    bundle = directory / 'full_model.joblib'
    bundle.write_bytes(b'not loaded by metrics endpoint')
    os.utime(bundle, (timestamp, timestamp))
    if report is not None:
        (directory / 'metrics.json').write_text(json.dumps(report), encoding='utf-8')


def test_latest_completed_artifact_metrics(tmp_path, monkeypatch):
    monkeypatch.setenv('ARTIFACT_DIR', str(tmp_path))
    artifact(tmp_path, 'older', 100, {'model_version': 'older', 'combined': {'mae': 9}})
    artifact(tmp_path, 'latest', 200, {'model_version': 'latest', 'combined': {'mae': 0}, 'test': {'roc_auc': None}})
    incomplete = tmp_path / 'incomplete'
    incomplete.mkdir()
    (incomplete / 'metrics.json').write_text('{}')
    assert get_model_metrics() == {'model_version': 'latest', 'combined': {'mae': 0}, 'test': {'roc_auc': None}}


def test_missing_artifact(tmp_path, monkeypatch):
    monkeypatch.setenv('ARTIFACT_DIR', str(tmp_path))
    with pytest.raises(HTTPException) as error:
        get_model_metrics()
    assert error.value.status_code == 404


def test_latest_invalid_metrics_do_not_fall_back(tmp_path, monkeypatch):
    monkeypatch.setenv('ARTIFACT_DIR', str(tmp_path))
    artifact(tmp_path, 'older', 100, {'model_version': 'older'})
    artifact(tmp_path, 'latest', 200, {'model_version': 'wrong'})
    with pytest.raises(HTTPException) as error:
        get_model_metrics()
    assert error.value.status_code == 503


def test_validation_baselines_are_returned_from_same_artifact(tmp_path, monkeypatch):
    monkeypatch.setenv('ARTIFACT_DIR', str(tmp_path))
    report = {
        'model_version': 'latest', 'winner': 'logistic',
        'validation': {'constant': {'brier': 0.2, 'n': 10}, 'logistic': {'brier': 0.15, 'n': 10}},
        'stage2': {'winner': 'poisson', 'validation': {'mean': {'rmse': 2, 'n': 5}}},
    }
    artifact(tmp_path, 'latest', 100, report)
    assert get_model_metrics() == report
