export function baselineComparisons(report) {
  return [
    ['Purchase probability', report, 'constant', 'brier', 'Brier score'],
    ['Transaction count', report.stage2, 'mean', 'rmse', 'RMSE'],
    ['Order value', report.stage3, 'mean', 'mae', 'MAE']
  ].map(([stage, model, baselineName, metric, label]) => {
    const baseline = model?.validation?.[baselineName];
    const selected = model?.validation?.[model?.winner];
    const base = baseline?.[metric];
    const actual = selected?.[metric];
    const comparable = Number.isFinite(base) && Number.isFinite(actual)
      && base >= 0 && actual >= 0 && Number.isFinite(baseline?.n)
      && baseline.n > 0 && baseline.n === selected?.n;
    const improvement = comparable && base > 0 ? (base - actual) / base * 100 : null;
    let inference = 'Comparable validation scores are unavailable.';
    if (comparable) {
      if (model.winner === baselineName) inference = 'The baseline was selected; no improvement over the baseline.';
      else if (actual === base) inference = 'The selected model matches the baseline on this metric.';
      else if (improvement !== null) inference = `${Math.abs(improvement).toFixed(1)}% ${improvement > 0 ? 'lower' : 'higher'} error than the baseline (${improvement > 0 ? 'better' : 'worse'}).`;
      else inference = 'The baseline has zero error; the selected model has higher error.';
    }
    return { stage, baselineName, winner: model?.winner, label, base, actual, comparable, inference };
  });
}

export function revenueInference(combined) {
  if (!Number.isFinite(combined?.aggregate_error_pct)) return 'Aggregate revenue error is unavailable.';
  const error = combined.aggregate_error_pct;
  if (error === 0) return 'Total predicted revenue matches actual revenue on the test set; individual customer errors may remain.';
  return `Total predicted revenue ${error < 0 ? 'underestimates' : 'overestimates'} actual test revenue by ${Math.abs(error).toFixed(2)}%. This measures total revenue bias, not individual customer accuracy.`;
}
