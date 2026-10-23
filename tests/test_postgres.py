"""Opt-in integration check against a disposable PostgreSQL database."""
import os

import pytest
from sqlalchemy import inspect

from clv.cli import migrate
from clv.data import ingest
from clv.db import engine, session
from clv.features import snapshot
from clv.sample import generate


@pytest.mark.skipif(not os.getenv('TEST_POSTGRES_URL'), reason='Set TEST_POSTGRES_URL to a disposable PostgreSQL database')
def test_postgres_migration_ingestion_snapshot(tmp_path, monkeypatch):
    monkeypatch.setenv('DATABASE_URL', os.environ['TEST_POSTGRES_URL'])
    migrate()
    assert 'stage1_predictions' in inspect(engine()).get_table_names()
    path = tmp_path / 'orders.csv'
    generate(path, customers=25)
    with session() as db:
        ingest(db, path)
        identity, features, labels = snapshot(db, '2025-01-01', '2025-10-01')
        assert len(features) == len(labels) > 0 and identity
