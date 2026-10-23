from datetime import datetime

import pandas as pd
import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from clv.data import ingest, timestamp, transactions_frame
from clv.db import engine
from clv.features import build_frames, snapshot
from clv.models import Base, Customer, RawTransaction, Transaction


@pytest.fixture
def db():
    connection = engine("sqlite:///:memory:")
    Base.metadata.create_all(connection)
    with Session(connection) as result:
        yield result


def csv_file(tmp_path, rows):
    path = tmp_path / 'orders.csv'
    pd.DataFrame(rows, columns=['customer_id', 'order_id', 'purchased_at', 'amount', 'category']).to_csv(path, index=False)
    return path


def test_ingestion_preserves_rejections_and_is_idempotent(db, tmp_path):
    path = csv_file(tmp_path, [['A','1','2024-01-01',10,'home'], ['A','1','2024-01-01',10,'home'], ['', '2','2024-01-02',20,None], ['B','3','invalid',20,None], ['B','4','2024-01-02',-2,None]])
    first = ingest(db, path)
    assert (first['accepted'], first['rejected']) == (1, 4)
    assert ingest(db, path)['already_ingested']
    assert db.scalar(select(func.count()).select_from(RawTransaction)) == 5
    assert db.scalar(select(func.count()).select_from(Transaction)) == 1
    assert db.scalar(select(func.sum(Transaction.amount))) == 10


def test_order_conflict_and_database_constraints(db, tmp_path):
    ingest(db, csv_file(tmp_path, [['A','1','2024-01-01',10,None]]))
    result = ingest(db, csv_file(tmp_path, [['B','1','2024-01-01',30,None]]))
    assert result['rejected'] == 1
    assert db.scalar(select(RawTransaction.rejection_reason).where(RawTransaction.rejection_reason.is_not(None))) == 'conflicting order ID'
    db.add(Transaction(order_id='orphan', customer_id='missing', purchased_at=datetime(2024,1,1), amount=10, source_id=1))
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_features_labels_boundaries_and_leakage(db, tmp_path):
    path = csv_file(tmp_path, [['A','1','2024-01-01',10,'home'], ['A','2','2024-01-11',30,'fashion'], ['B','3','2024-01-20',50,None], ['A','4','2024-02-01',70,'future'], ['A','5','2024-05-01',90,'future'], ['NEW','6','2024-02-02',12,None]])
    ingest(db, path)
    frame = transactions_frame(db)
    x, y = build_frames(frame, '2024-02-01', '2024-06-01')
    a = x.set_index('customer_id').loc['A']
    assert a.frequency == 2 and a.recency == 21 and a['T'] == 31
    assert a.avg_order_value == 20 and a.monetary_std == 10
    assert a.interpurchase_time_mean == 10 and a.category_diversity == 2
    assert not a.is_cold_start
    assert 'NEW' not in set(x.customer_id)
    assert x.set_index('customer_id').loc['B'].is_cold_start
    assert y.set_index('customer_id').loc['A'].transaction_count == 1  # May 1 is exclusive horizon end in leap year
    historic, _ = build_frames(frame[frame.purchased_at < timestamp('2024-02-01')], '2024-02-01', '2024-06-01')
    pd.testing.assert_frame_equal(x, historic)
    identity, _, _ = snapshot(db, '2024-02-01', '2024-06-01')
    assert snapshot(db, '2024-02-01', '2024-06-01')[0] == identity


def test_incomplete_labels_and_timezones():
    frame = pd.DataFrame(columns=['customer_id', 'order_id', 'purchased_at', 'amount', 'category'])
    with pytest.raises(ValueError, match='fully observed'):
        build_frames(frame, '2025-01-01', '2025-02-01')
    assert timestamp('2024-01-01T05:30:00+05:30') == datetime(2024,1,1)
