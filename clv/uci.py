"""Convert UCI Online Retail II item lines into canonical completed orders."""
from pathlib import Path

import pandas as pd


def convert(paths, output):
    pieces = []
    stats = {}
    for source in map(Path, paths):
        data = pd.read_csv(source, dtype={"InvoiceNo": "string", "CustomerID": "string"}, low_memory=False)
        expected = {"InvoiceNo", "InvoiceDate", "CustomerID", "Quantity", "UnitPrice"}
        if not expected.issubset(data.columns):
            raise ValueError(f"{source}: missing {sorted(expected - set(data.columns))}")
        data["InvoiceNo"] = data.InvoiceNo.str.strip()
        data["CustomerID"] = data.CustomerID.str.strip().str.replace(r"\.0$", "", regex=True)
        dates = pd.to_datetime(data.InvoiceDate, format="%m/%d/%Y %H:%M", errors="coerce")
        cancel = data.InvoiceNo.str.upper().str.startswith("C", na=False)
        valid = (data.InvoiceNo.notna() & data.CustomerID.notna() & (data.CustomerID != "")
                 & ~cancel & (data.Quantity > 0) & (data.UnitPrice > 0) & dates.notna())
        clean = data.loc[valid, ["InvoiceNo", "CustomerID", "Quantity", "UnitPrice"]].copy()
        clean["InvoiceDate"] = dates[valid]
        clean["line_total"] = (clean.Quantity * clean.UnitPrice).round(2)
        clean["source"] = source.name
        pieces.append(clean)
        stats[source.name] = {"source_lines": len(data), "excluded_lines": int((~valid).sum()),
                              "valid_lines": len(clean), "date_min": str(dates.min()), "date_max": str(dates.max())}
    joined = pd.concat(pieces, ignore_index=True)
    # Invoice identifiers must identify one customer and one invoice timestamp.
    identity = joined.groupby("InvoiceNo").agg(customers=("CustomerID", "nunique"), timestamps=("InvoiceDate", "nunique"))
    conflicted = identity.index[(identity.customers != 1) | (identity.timestamps != 1)]
    excluded_conflicts = int(joined.InvoiceNo.isin(conflicted).sum())
    joined = joined[~joined.InvoiceNo.isin(conflicted)]
    orders = joined.groupby(["InvoiceNo", "CustomerID", "InvoiceDate"], sort=True).line_total.sum().reset_index()
    orders = orders[orders.line_total > 0]
    result = pd.DataFrame({"customer_id": orders.CustomerID, "order_id": orders.InvoiceNo,
                           "purchased_at": orders.InvoiceDate.dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                           "amount": orders.line_total.round(2), "category": "", "status": "completed"})
    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(target, index=False)
    return {"sources": stats, "excluded_conflicting_invoice_lines": excluded_conflicts,
            "orders": len(result), "customers": result.customer_id.nunique(), "order_total_gbp": round(float(result.amount.sum()), 2),
            "first_order": result.purchased_at.min(), "last_order": result.purchased_at.max(), "output": str(target)}
