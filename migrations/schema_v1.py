from datetime import datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, ForeignKey, Integer, JSON, Numeric, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class IngestionBatch(Base):
    __tablename__ = "ingestion_batches"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    filename: Mapped[str] = mapped_column(String(512))
    ingested_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    row_count: Mapped[int] = mapped_column(Integer)
    accepted: Mapped[int] = mapped_column(Integer, default=0)
    rejected: Mapped[int] = mapped_column(Integer, default=0)
    source_csv: Mapped[str] = mapped_column(String)


class RawTransaction(Base):
    __tablename__ = "raw_transactions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_id: Mapped[str] = mapped_column(ForeignKey("ingestion_batches.id"))
    row_number: Mapped[int] = mapped_column(Integer)
    payload: Mapped[dict] = mapped_column(JSON)
    rejection_reason: Mapped[str | None] = mapped_column(String)
    __table_args__ = (UniqueConstraint("batch_id", "row_number"),)


class Customer(Base):
    __tablename__ = "customers"
    customer_id: Mapped[str] = mapped_column(String(128), primary_key=True)


class Transaction(Base):
    __tablename__ = "transactions"
    order_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.customer_id"), index=True)
    purchased_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    amount: Mapped[float] = mapped_column(Numeric(14, 2))
    category: Mapped[str | None] = mapped_column(String(256))
    source_id: Mapped[int] = mapped_column(ForeignKey("raw_transactions.id"), unique=True)
    __table_args__ = (CheckConstraint("amount > 0"),)


class Snapshot(Base):
    __tablename__ = "data_snapshots"
    snapshot_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    cutoff: Mapped[datetime] = mapped_column(DateTime)
    horizon_days: Mapped[int] = mapped_column(Integer)
    observation_end: Mapped[datetime] = mapped_column(DateTime)
    dataset_fingerprint: Mapped[str] = mapped_column(String(64))
    definition_version: Mapped[str] = mapped_column(String(20), default="v1")


class Features(Base):
    __tablename__ = "customer_rfm_summary"
    snapshot_id: Mapped[str] = mapped_column(ForeignKey("data_snapshots.snapshot_id"), primary_key=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.customer_id"), primary_key=True)
    values: Mapped[dict] = mapped_column(JSON)
    is_cold_start: Mapped[bool] = mapped_column(Boolean)


class Label(Base):
    __tablename__ = "snapshot_labels"
    snapshot_id: Mapped[str] = mapped_column(ForeignKey("data_snapshots.snapshot_id"), primary_key=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.customer_id"), primary_key=True)
    purchased: Mapped[int] = mapped_column(Integer)
    transaction_count: Mapped[int] = mapped_column(Integer)
    revenue: Mapped[float] = mapped_column(Numeric(14, 2))
    mean_order_value: Mapped[float | None] = mapped_column(Numeric(14, 2))
    __table_args__ = (CheckConstraint("purchased IN (0, 1)"), CheckConstraint("transaction_count >= 0"))


class ModelRun(Base):
    __tablename__ = "model_runs"
    model_version: Mapped[str] = mapped_column(String(64), primary_key=True)
    trained_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    status: Mapped[str] = mapped_column(String(32))
    classifier_type: Mapped[str | None] = mapped_column(String(64))
    classifier_auc: Mapped[float | None] = mapped_column(Float)
    metadata_json: Mapped[dict] = mapped_column(JSON)
    artifact_path: Mapped[str] = mapped_column(String(1024))


class Stage1Prediction(Base):
    __tablename__ = "stage1_predictions"
    model_version: Mapped[str] = mapped_column(ForeignKey("model_runs.model_version"), primary_key=True)
    snapshot_id: Mapped[str] = mapped_column(ForeignKey("data_snapshots.snapshot_id"), primary_key=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.customer_id"), primary_key=True)
    prob_purchase: Mapped[float] = mapped_column(Float)
    is_cold_start: Mapped[bool] = mapped_column(Boolean)
    __table_args__ = (CheckConstraint("prob_purchase >= 0 AND prob_purchase <= 1"),)


class CLVPrediction(Base):
    __tablename__ = "clv_predictions"
    model_version: Mapped[str] = mapped_column(ForeignKey("model_runs.model_version"), primary_key=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.customer_id"), primary_key=True)
    snapshot_id: Mapped[str] = mapped_column(ForeignKey("data_snapshots.snapshot_id"), primary_key=True)
    prob_purchase: Mapped[float] = mapped_column(Float)
    expected_transactions: Mapped[float] = mapped_column(Float)
    expected_value_per_txn: Mapped[float] = mapped_column(Numeric(14, 2))
    predicted_clv_90d: Mapped[float] = mapped_column(Numeric(14, 2))
    segment: Mapped[str] = mapped_column(String(32))
    is_cold_start: Mapped[bool] = mapped_column(Boolean)
    predicted_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    __table_args__ = (CheckConstraint("prob_purchase >= 0 AND prob_purchase <= 1"), CheckConstraint("expected_transactions >= 0 AND expected_value_per_txn >= 0 AND predicted_clv_90d >= 0"))
