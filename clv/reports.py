"""Visual evaluation of combined 90-day CLV on an observed holdout period."""
import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str(Path("artifacts/.matplotlib").resolve()))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
import numpy as np
import pandas as pd


def generate_clv_report(directory):
    """Join saved predictions to outcomes by customer, then render the final report."""
    directory = Path(directory)
    predictions = pd.read_csv(directory / "clv_predictions.csv", dtype={"customer_id": str})
    labels = pd.read_csv(directory / "test_labels.csv", dtype={"customer_id": str})
    frame = predictions.merge(labels[["customer_id", "revenue"]], on="customer_id",
                              how="outer", validate="one_to_one", indicator=True)
    if frame.empty or not frame["_merge"].eq("both").all():
        raise ValueError("CLV report requires matching predictions and outcomes for every customer")
    actual = frame.revenue.to_numpy(dtype=float)
    predicted = frame.predicted_clv_90d.to_numpy(dtype=float)
    if not np.isfinite(np.r_[actual, predicted]).all() or (np.r_[actual, predicted] < 0).any():
        raise ValueError("CLV report requires finite, nonnegative revenue and predictions")
    ranked = frame.sort_values("predicted_clv_90d", ascending=False, kind="stable").copy()
    total = actual.sum()
    error = predicted - actual
    top_n = max(1, int(np.ceil(len(frame) * .1)))
    top_share = ranked.revenue.iloc[:top_n].sum() / total if total else None
    bias = f"{(predicted.sum() - total) / total:+.1%}" if total else "N/A (zero actual revenue)"
    gains = pd.DataFrame({"fraction_customers": np.arange(1, len(frame) + 1) / len(frame),
                          "cumulative_actual_revenue": ranked.revenue.cumsum().to_numpy()})
    gains["fraction_actual_revenue"] = gains.cumulative_actual_revenue / total if total else np.nan
    ranked["rank_group"] = np.minimum(np.arange(len(frame)) * 10 // len(frame) + 1, 10)
    groups = ranked.groupby("rank_group").agg(customers=("customer_id", "size"),
        actual_mean=("revenue", "mean"), predicted_mean=("predicted_clv_90d", "mean"))
    segments = frame.groupby("segment")[["revenue", "predicted_clv_90d"]].sum()
    with plt.rc_context({"axes.spines.top": False, "axes.spines.right": False,
                         "axes.titlesize": 11, "font.size": 9}):
        fig, axes = plt.subplots(2, 3, figsize=(17, 10), layout="constrained")
        fig.suptitle(f"Combined CLV | 90-day holdout evaluation\nRun {directory.name}", fontsize=16)
        ax = axes[0, 0]
        ax.bar(["Actual", "Predicted"], [total, predicted.sum()], color=["#536777", "#16877b"])
        ax.set(title=f"Total revenue | error {bias}", ylabel="Revenue (source currency)")
        ax.ticklabel_format(axis="y", style="plain")
        ax = axes[0, 1]
        ax.scatter(actual, predicted, s=9, alpha=.25, color="#16877b", rasterized=True)
        maximum = max(actual.max(), predicted.max(), 1)
        ax.plot([0, maximum], [0, maximum], "--", color="#536777", label="Perfect prediction")
        ax.set(xscale="symlog", yscale="symlog", xlabel="Actual 90-day revenue",
               ylabel="Predicted 90-day revenue", title="Customer accuracy | symmetric log axes")
        ax.legend()
        ax = axes[0, 2]
        if total:
            ax.plot(np.r_[0, gains.fraction_customers], np.r_[0, gains.fraction_actual_revenue], color="#16877b")
            ax.set_title(f"Revenue captured | top 10%: {top_share:.1%}")
        else:
            ax.text(.5, .5, "No actual revenue; gains unavailable", ha="center", transform=ax.transAxes)
            ax.set_title("Revenue captured")
        ax.plot([0, 1], [0, 1], "--", color="#536777", label="Random ranking")
        ax.set(xlabel="Customers ranked by predicted CLV", ylabel="Share of actual revenue", xlim=(0, 1), ylim=(0, 1))
        ax.xaxis.set_major_formatter(PercentFormatter(1))
        ax.yaxis.set_major_formatter(PercentFormatter(1))
        ax.legend()
        ax = axes[1, 0]
        ax.plot(groups.index, groups.actual_mean, "o-", label="Actual", color="#536777")
        ax.plot(groups.index, groups.predicted_mean, "o-", label="Predicted", color="#16877b")
        ax.set(title="Average revenue by ranked group", xlabel="Rank group (1 = highest CLV)", ylabel="Mean revenue per customer", xticks=groups.index)
        ax.legend()
        ax = axes[1, 1]
        # Space bins in signed-log coordinates so extreme errors do not hide the center.
        signed_log = np.sign(error) * np.log1p(np.abs(error))
        low, high = signed_log.min(), signed_log.max()
        if low == high:
            low, high = low - .5, high + .5
        edges = np.linspace(low, high, 51)
        edges = np.sign(edges) * np.expm1(np.abs(edges))
        ax.hist(error, bins=edges, color="#16877b")
        ax.axvline(0, linestyle="--", color="#536777")
        ax.set_xscale("symlog")
        ax.set(title=f"Customer errors | MAE {np.abs(error).mean():,.2f}\nRMSE {np.sqrt(np.mean(error**2)):,.2f}",
               xlabel="Predicted minus actual revenue (symmetric log)", ylabel="Customers")
        ax = axes[1, 2]
        positions = np.arange(len(segments))
        ax.bar(positions - .2, segments.revenue, width=.4, color="#536777", label="Actual")
        ax.bar(positions + .2, segments.predicted_clv_90d, width=.4, color="#16877b", label="Predicted")
        ax.set(title="Revenue by predicted segment", ylabel="Revenue (source currency)", xticks=positions, xticklabels=segments.index)
        ax.legend()
        output = directory / "clv_report.png"
        try:
            fig.savefig(output, dpi=150)
        finally:
            plt.close(fig)
    gains.to_csv(directory / "clv_revenue_gains.csv", index=False)
    groups.to_csv(directory / "clv_rank_groups.csv")
    return output
