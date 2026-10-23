import numpy as np
import pandas as pd
import pytest

from clv.reports import generate_clv_report


def test_report_joins_customer_ids_and_ranks_revenue(tmp_path):
    pd.DataFrame({"customer_id": ["001", "002", "003"],
                  "predicted_clv_90d": [100, 50, 0],
                  "segment": ["VIP", "Growth", "Low-Priority"]}).to_csv(tmp_path / "clv_predictions.csv", index=False)
    pd.DataFrame({"customer_id": ["003", "001", "002"], "revenue": [0, 80, 20]}).to_csv(tmp_path / "test_labels.csv", index=False)
    assert generate_clv_report(tmp_path).is_file()
    gains = pd.read_csv(tmp_path / "clv_revenue_gains.csv")
    np.testing.assert_allclose(gains.fraction_actual_revenue, [.8, 1, 1])
    groups = pd.read_csv(tmp_path / "clv_rank_groups.csv")
    assert groups.actual_mean.iloc[0] == 80
    pd.DataFrame({"customer_id": ["001"], "revenue": [80]}).to_csv(tmp_path / "test_labels.csv", index=False)
    with pytest.raises(ValueError, match="matching"):
        generate_clv_report(tmp_path)


def test_zero_revenue_report(tmp_path):
    pd.DataFrame({"customer_id": ["a"], "predicted_clv_90d": [0], "segment": ["VIP"]}).to_csv(tmp_path / "clv_predictions.csv", index=False)
    pd.DataFrame({"customer_id": ["a"], "revenue": [0]}).to_csv(tmp_path / "test_labels.csv", index=False)
    assert generate_clv_report(tmp_path).is_file()
    assert pd.read_csv(tmp_path / "clv_revenue_gains.csv").fraction_actual_revenue.isna().all()
