// src/pages/ModelPerformance.tsx
import React, { useState } from 'react';
import { modelPerformance } from '../data/modelPerformance';

const Card: React.FC<{title:string; value:string}> = ({title,value}) => (
  <div className="rounded-lg bg-white p-4 shadow-sm hover:shadow-md transition-shadow">
    <h3 className="text-sm font-medium text-gray-500">{title}</h3>
    <p className="text-2xl font-bold text-gray-800 mt-1">{value}</p>
  </div>
);

const ModelPerformance: React.FC = () => {
  const [view, setView] = useState<'validation'|'test'>('validation');

  const stage1 = modelPerformance.stage1[view];
  const stage2 = modelPerformance.stage2[view];
  const stage3 = modelPerformance.stage3.validation; // test not reported
  const combined = modelPerformance.combined[view];
  const cold = modelPerformance.coldStart[view];
  const established = modelPerformance.established[view];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Model Performance</h1>
          <p className="text-gray-600">Evaluation of each modelling stage and overall CLV prediction.</p>
        </div>
        <span className="inline-flex items-center rounded-full bg-yellow-100 px-3 py-1 text-sm font-medium text-yellow-800">
          SAMPLE DATA
        </span>
      </div>

      {/* Dataset selector */}
      <div className="flex items-center space-x-4">
        <label className="text-sm font-medium text-gray-700">Dataset:</label>
        <select
          value={view}
          onChange={e => setView(e.target.value as any)}
          className="rounded border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
        >
          <option value="validation">Validation (held‑out snapshot)</option>
          <option value="test">Test (final hold‑out – previously used)</option>
        </select>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        <Card title="Combined RMSE" value={combined?.rmse?.toFixed(0) ?? 'N/A'} />
        <Card title="Combined MAE" value={combined?.mae?.toFixed(0) ?? 'N/A'} />
        <Card title="Aggregate error %" value={combined?.aggregate_error_pct?.toFixed(2) ?? 'N/A'} />
      </div>

      {/* Stage 1 metrics */}
      <section className="mt-6">
        <h2 className="text-xl font-semibold mb-2">Stage 1 – Purchase Probability</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Card title="Brier score" value={stage1?.brier?.toFixed(3) ?? 'N/A'} />
          <Card title="ROC‑AUC" value={stage1?.roc_auc?.toFixed(3) ?? 'N/A'} />
          <Card title="PR‑AUC" value={stage1?.pr_auc?.toFixed(3) ?? 'N/A'} />
          <Card title="Precision @0.5" value={stage1?.precision_at_0_5?.toFixed(3) ?? 'N/A'} />
          <Card title="Recall @0.5" value={stage1?.recall_at_0_5?.toFixed(3) ?? 'N/A'} />
        </div>
      </section>

      {/* Stage 2 metrics */}
      <section className="mt-6">
        <h2 className="text-xl font-semibold mb-2">Stage 2 – Transaction Count</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Card title="RMSE" value={stage2?.rmse?.toFixed(2) ?? 'N/A'} />
          <Card title="MAE" value={stage2?.mae?.toFixed(2) ?? 'N/A'} />
        </div>
      </section>

      {/* Stage 3 metrics */}
      <section className="mt-6">
        <h2 className="text-xl font-semibold mb-2">Stage 3 – Order‑Value</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Card title="RMSE" value={stage3?.rmse?.toFixed(2) ?? 'N/A'} />
          <Card title="MAE" value={stage3?.mae?.toFixed(2) ?? 'N/A'} />
        </div>
        {view === 'test' && (
          <p className="text-sm text-gray-500 mt-2">Test‑set metrics for Stage 3 are not reported in the official documentation.</p>
        )}
      </section>

      {/* Cohort results */}
      <section className="mt-6">
        <h2 className="text-xl font-semibold mb-2">Cohort‑specific CLV results</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <Card title="Cold‑start RMSE" value={cold?.rmse?.toFixed(2) ?? 'N/A'} />
          <Card title="Cold‑start MAE" value={cold?.mae?.toFixed(2) ?? 'N/A'} />
          <Card title="Cold‑start error %" value={cold?.aggregate_error_pct?.toFixed(2) ?? 'N/A'} />
          <Card title="Established RMSE" value={established?.rmse?.toFixed(2) ?? 'N/A'} />
          <Card title="Established MAE" value={established?.mae?.toFixed(2) ?? 'N/A'} />
          <Card title="Established error %" value={established?.aggregate_error_pct?.toFixed(2) ?? 'N/A'} />
        </div>
      </section>

      {/* Disclaimer */}
      <div className="p-4 bg-gray-50 border-l-4 border-yellow-400 mt-6">
        <p className="text-sm text-gray-700">
          <strong>Note:</strong> These figures are historical evaluation results from the project report. They are not live predictions. The test set has already been used for reporting and should not be considered an untouched hold‑out.
        </p>
      </div>
    </div>
  );
};

export default ModelPerformance;
