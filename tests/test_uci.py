import pandas as pd

from clv.uci import convert


def test_uci_aggregation_and_exclusions(tmp_path):
    columns = ["InvoiceNo", "StockCode", "Description", "Quantity", "InvoiceDate", "UnitPrice", "CustomerID", "Country"]
    first = tmp_path / "year1.csv"
    second = tmp_path / "year2.csv"
    pd.DataFrame([["1", "A", "a", 2, "12/1/2009 7:45", 3, "123", "UK"],
                  ["1", "B", "b", 1, "12/1/2009 7:45", 5, "123", "UK"],
                  ["C2", "A", "cancel", -1, "12/2/2009 7:45", 3, "123", "UK"],
                  ["3", "A", "unknown", 1, "12/2/2009 7:45", 3, None, "UK"]], columns=columns).to_csv(first, index=False)
    pd.DataFrame([["4", "A", "a", 1, "12/1/2010 7:45", 7, "456", "UK"],
                  ["4", "A", "a", 1, "12/1/2010 8:45", 7, "456", "UK"]], columns=columns).to_csv(second, index=False)
    output = tmp_path / "orders.csv"
    report = convert([first, second], output)
    orders = pd.read_csv(output)
    assert report["orders"] == 1
    assert report["excluded_conflicting_invoice_lines"] == 2
    assert orders.iloc[0].amount == 11
