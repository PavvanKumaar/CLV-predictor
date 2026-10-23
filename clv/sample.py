"""Synthetic behavior for plumbing tests, never evidence of business accuracy."""
from pathlib import Path

import numpy as np
import pandas as pd


def generate(path, customers=350, seed=42):
    rng = np.random.default_rng(seed)
    rows = []
    start, end = pd.Timestamp("2023-01-01"), pd.Timestamp("2025-10-01")
    for index in range(customers):
        customer_id = f"C{index:05d}"
        first = start + pd.Timedelta(days=int(rng.integers(0, 985)))
        rate = rng.choice([0.002, 0.012, 0.045])
        for day in pd.date_range(first, end - pd.Timedelta(days=1)):
            if day != first and rng.random() >= rate:
                continue
            rows.append({"customer_id": customer_id, "order_id": f"O{len(rows):08d}", "purchased_at": day.isoformat(), "amount": round(float(rng.lognormal(4, 0.5)), 2), "category": rng.choice(["home", "fashion", "electronics"]), "status": "completed"})
    rows.extend([dict(rows[0]), {**rows[1], "order_id": "BAD-RETURN", "status": "returned"}, {**rows[2], "order_id": "BAD-ID", "customer_id": ""}, {**rows[3], "order_id": "BAD-AMOUNT", "amount": -10}])
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)
    return {"path": str(path), "rows": len(rows), "seed": seed, "observation_end": "2025-10-01"}
