"""Order-level CSV ingestion. All times are normalized to UTC, stored without tz."""
import csv
import hashlib
import io
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

import pandas as pd
from sqlalchemy import select

from clv.models import Customer, IngestionBatch, RawTransaction, Transaction


def timestamp(value):
    result = pd.Timestamp(value)
    if pd.isna(result):
        raise ValueError("missing timestamp")
    return (result.tz_localize("UTC") if result.tzinfo is None else result.tz_convert("UTC")).tz_localize(None).to_pydatetime()


def ingest(session, path):
    source = Path(path).read_bytes()
    digest = hashlib.sha256(source).hexdigest()
    existing = session.get(IngestionBatch, digest)
    if existing:
        return {"batch_id": digest, "accepted": existing.accepted, "rejected": existing.rejected, "already_ingested": True}
    content = source.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(content))
    required = {"customer_id", "order_id", "purchased_at", "amount"}
    if not required.issubset(reader.fieldnames or []):
        raise ValueError(f"CSV must contain {sorted(required)}")
    rows = list(reader)
    batch = IngestionBatch(id=digest, filename=Path(path).name, row_count=len(rows), source_csv=content)
    session.add(batch)
    session.flush()
    accepted = rejected = 0
    for index, payload in enumerate(rows, 2):
        raw = RawTransaction(batch_id=digest, row_number=index, payload=payload)
        session.add(raw)
        session.flush()
        try:
            if None in payload:
                raise ValueError("too many CSV fields")
            customer_id = (payload["customer_id"] or "").strip()
            order_id = (payload["order_id"] or "").strip()
            if not customer_id or not order_id or max(len(customer_id), len(order_id)) > 128:
                raise ValueError("missing or overlong identifier")
            status = (payload.get("status") or "completed").strip().lower()
            if status != "completed":
                raise ValueError("cancelled, returned, or non-completed order")
            amount = Decimal(payload["amount"])
            if not amount.is_finite() or amount <= 0 or amount >= Decimal("1000000000000"):
                raise ValueError("amount must be finite, positive, and below 1 trillion")
            amount = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            if amount <= 0:
                raise ValueError("amount rounds to zero")
            purchased_at = timestamp(payload["purchased_at"])
            category = (payload.get("category") or "").strip() or None
            if category and len(category) > 256:
                raise ValueError("category exceeds 256 characters")
            previous = session.get(Transaction, order_id)
            if previous:
                same = previous.customer_id == customer_id and previous.purchased_at == purchased_at and previous.amount == amount and previous.category == category
                raise ValueError("duplicate order" if same else "conflicting order ID")
            if session.get(Customer, customer_id) is None:
                session.add(Customer(customer_id=customer_id))
                session.flush()
            session.add(Transaction(order_id=order_id, customer_id=customer_id, purchased_at=purchased_at, amount=amount, category=category, source_id=raw.id))
            session.flush()
            accepted += 1
        except (ValueError, TypeError, InvalidOperation, OverflowError) as error:
            raw.rejection_reason = str(error)
            rejected += 1
    batch.accepted, batch.rejected = accepted, rejected
    session.commit()
    return {"batch_id": digest, "accepted": accepted, "rejected": rejected, "already_ingested": False}


def transactions_frame(session):
    rows = session.scalars(select(Transaction).order_by(Transaction.purchased_at, Transaction.order_id)).all()
    return pd.DataFrame([{"customer_id": r.customer_id, "order_id": r.order_id, "purchased_at": r.purchased_at, "amount": float(r.amount), "category": r.category} for r in rows], columns=["customer_id", "order_id", "purchased_at", "amount", "category"])
