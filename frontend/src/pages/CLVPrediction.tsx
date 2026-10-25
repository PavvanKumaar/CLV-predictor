// src/pages/CLVPrediction.tsx
import React, { useState } from 'react';
import { AlertTriangle, CheckCircle, X } from 'lucide-react';

// Types for the form and demo result
interface FormValues {
  customerId: string;
  purchaseCount: string; // keep as string for easy input handling
  totalSpend: string;
  avgOrderValue: string;
  daysSinceLast: string;
  customerType: 'existing' | 'new';
}

interface DemoResult {
  clv: number;
  purchaseProb: number; // 0‑1
  transactionCount: number;
  orderValue: number;
}

const initialForm: FormValues = {
  customerId: '',
  purchaseCount: '',
  totalSpend: '',
  avgOrderValue: '',
  daysSinceLast: '',
  customerType: 'existing',
};

const CLVPrediction: React.FC = () => {
  const [form, setForm] = useState<FormValues>(initialForm);
  const [errors, setErrors] = useState<Partial<Record<keyof FormValues, string>>>({});
  const [isLoading, setIsLoading] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);
  const [realResult, setRealResult] = useState<DemoResult | null>(null);
  const [demoResult, setDemoResult] = useState<DemoResult | null>(null);

  // Simple client‑side validation
  const validate = (): boolean => {
    const newErrors: Partial<Record<keyof FormValues, string>> = {};
    const num = (value: string) => Number(value);
    if (form.purchaseCount && (isNaN(num(form.purchaseCount)) || num(form.purchaseCount) < 0)) {
      newErrors.purchaseCount = 'Must be a non‑negative integer';
    }
    if (form.totalSpend && (isNaN(num(form.totalSpend)) || num(form.totalSpend) < 0)) {
      newErrors.totalSpend = 'Must be a non‑negative number';
    }
    if (form.avgOrderValue && (isNaN(num(form.avgOrderValue)) || num(form.avgOrderValue) <= 0)) {
      newErrors.avgOrderValue = 'Must be a positive number';
    }
    if (form.daysSinceLast && (isNaN(num(form.daysSinceLast)) || num(form.daysSinceLast) < 0)) {
      newErrors.daysSinceLast = 'Must be a non‑negative integer';
    }
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setForm(prev => ({ ...prev, [name]: value }));
  };

  const handleClear = () => {
    setForm(initialForm);
    setErrors({});
    setDemoResult(null);
  };

  const handleDemo = () => {
    if (!validate()) return;
    // Sample static result – clearly marked as demo data
    const sample: DemoResult = {
      clv: 15800,
      purchaseProb: 0.73,
      transactionCount: 12,
      orderValue: 1320,
    };
    setDemoResult(sample);
  };

  const handlePredict = async () => {
  if (!validate()) return;
  // Reset previous state
  setApiError(null);
  setRealResult(null);
  setIsLoading(true);

  const payload = {
    recency: parseFloat(form.daysSinceLast) || 0,
    frequency: parseInt(form.purchaseCount) || 0,
    T: 365,
    avg_order_value: parseFloat(form.avgOrderValue) || 0,
    monetary_std: 0,
    purchase_velocity: 0,
    interpurchase_time_mean: 0,
    interpurchase_time_std: 0,
    category_diversity: 0,
    category_missing: 0,
    tenure_bucket: form.customerType === 'new' ? 'new' : 'established',
    last_order_recency_ratio: 1,
    is_cold_start: form.customerType === 'new',
  };

  try {
    const resp = await fetch('http://127.0.0.1:8001/predict', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!resp.ok) {
      const err = await resp.json();
      throw new Error(err.detail || 'Unexpected error');
    }
    const data = await resp.json();
    const result: DemoResult = {
      clv: data.predicted_clv_90d,
      purchaseProb: data.prob_purchase,
      transactionCount: data.expected_transactions,
      orderValue: data.expected_value_per_txn,
    };
    setRealResult(result);
  } catch (e: any) {
    console.error(e);
    setApiError(e.message || 'Prediction failed');
  } finally {
    setIsLoading(false);
  }
};

return (
    <div className="space-y-6">
      {/* Header */}
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold text-gray-800">Customer Lifetime Value Prediction</h1>
        <p className="text-gray-600">
          Estimate the future value of a customer based on historical activity and selected attributes.
        </p>
      </header>

      {/* Input Form */}
      <div className="bg-white rounded-lg shadow p-6">
        <form className="grid grid-cols-1 md:grid-cols-2 gap-4" onSubmit={e => e.preventDefault()}>
          {/* Customer ID (optional) */}
          <div className="col-span-2">
            <label className="block text-sm font-medium text-gray-700">Customer ID (optional)</label>
            <input
              type="text"
              name="customerId"
              value={form.customerId}
              onChange={handleChange}
              className="mt-1 block w-full rounded border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
              placeholder="e.g., C12345"
            />
          </div>

          {/* Purchase count */}
          <div>
            <label className="block text-sm font-medium text-gray-700">Historical purchase count</label>
            <input
              type="number"
              name="purchaseCount"
              value={form.purchaseCount}
              onChange={handleChange}
              className="mt-1 block w-full rounded border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
              min={0}
            />
            {errors.purchaseCount && (
              <p className="mt-1 text-sm text-red-600 flex items-center">
                <AlertTriangle className="w-4 h-4 mr-1" /> {errors.purchaseCount}
              </p>
            )}
          </div>

          {/* Total spend */}
          <div>
            <label className="block text-sm font-medium text-gray-700">Historical total spend (USD)</label>
            <input
              type="number"
              name="totalSpend"
              value={form.totalSpend}
              onChange={handleChange}
              className="mt-1 block w-full rounded border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
              min={0}
              step="0.01"
            />
            {errors.totalSpend && (
              <p className="mt-1 text-sm text-red-600 flex items-center">
                <AlertTriangle className="w-4 h-4 mr-1" /> {errors.totalSpend}
              </p>
            )}
          </div>

          {/* Average order value */}
          <div>
            <label className="block text-sm font-medium text-gray-700">Average order value (USD)</label>
            <input
              type="number"
              name="avgOrderValue"
              value={form.avgOrderValue}
              onChange={handleChange}
              className="mt-1 block w-full rounded border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
              min={0.01}
              step="0.01"
            />
            {errors.avgOrderValue && (
              <p className="mt-1 text-sm text-red-600 flex items-center">
                <AlertTriangle className="w-4 h-4 mr-1" /> {errors.avgOrderValue}
              </p>
            )}
          </div>

          {/* Days since last purchase */}
          <div>
            <label className="block text-sm font-medium text-gray-700">Days since last purchase</label>
            <input
              type="number"
              name="daysSinceLast"
              value={form.daysSinceLast}
              onChange={handleChange}
              className="mt-1 block w-full rounded border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
              min={0}
            />
            {errors.daysSinceLast && (
              <p className="mt-1 text-sm text-red-600 flex items-center">
                <AlertTriangle className="w-4 h-4 mr-1" /> {errors.daysSinceLast}
              </p>
            )}
          </div>

          {/* Customer type */}
          <div className="col-span-2">
            <label className="block text-sm font-medium text-gray-700">Customer type</label>
            <select
              name="customerType"
              value={form.customerType}
              onChange={handleChange}
              className="mt-1 block w-full rounded border-gray-300 bg-white py-2 pl-3 pr-10 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-indigo-500 sm:text-sm"
            >
              <option value="existing">Existing customer</option>
              <option value="new">New customer</option>
            </select>
          </div>

          {/* Action buttons */}
          <div className="col-span-2 flex space-x-4 pt-4">
            <button
              type="button"
              onClick={handleDemo}
              className="px-4 py-2 bg-indigo-600 text-white rounded hover:bg-indigo-700 flex items-center"
            >
              Demo Preview
            </button>
            <button
              type="button"
              onClick={handleClear}
              className="px-4 py-2 bg-gray-300 text-gray-800 rounded hover:bg-gray-400"
            >
              Clear Form
            </button>
            <button
              type="button"
              onClick={handlePredict}
              disabled={!validate() || isLoading}
              className="px-4 py-2 bg-indigo-600 text-white rounded hover:bg-indigo-700 flex items-center disabled:bg-gray-300 disabled:text-gray-600"
            >
              {isLoading ? (
                <>
                  <svg className="animate-spin h-4 w-4 mr-2" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"></path>
                  </svg>
                  Running…
                </>
              ) : (
                "Run Prediction"
              )}
            </button>
          </div>
        </form>
      </div>

      {/* Result Card – only shown after Demo Preview */}
      {demoResult && (
        <div className="bg-white rounded-lg shadow p-6 border-l-4 border-indigo-500">
          <p className="text-xs font-medium text-indigo-600 mb-2">SAMPLE / DEMO ONLY</p>
          <h2 className="text-lg font-semibold mb-4">Prediction Result</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-gray-500">Estimated CLV</label>
              <p className="text-2xl font-bold text-gray-800">${demoResult.clv.toLocaleString()}</p>
            </div>
            <div>
              <label className="block text-sm text-gray-500">Purchase probability</label>
              <p className="text-2xl font-bold text-gray-800">{(demoResult.purchaseProb * 100).toFixed(1)}%</p>
            </div>
            <div>
              <label className="block text-sm text-gray-500">Expected transactions</label>
              <p className="text-2xl font-bold text-gray-800">{demoResult.transactionCount}</p>
            </div>
            <div>
              <label className="block text-sm text-gray-500">Expected order value</label>
              <p className="text-2xl font-bold text-gray-800">${demoResult.orderValue.toLocaleString()}</p>
            </div>
          </div>
          <p className="mt-4 text-gray-600">These numbers are illustrative only and do not reflect a real model output.</p>
        </div>
      )}
      {realResult && (
        <div className="bg-white rounded-lg shadow p-6 border-l-4 border-green-600 mt-6">
          <p className="text-xs font-medium text-green-600 mb-2">REAL PREDICTION</p>
          <h2 className="text-lg font-semibold mb-4">Prediction Result</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-gray-500">Estimated CLV</label>
              <p className="text-2xl font-bold text-gray-800">${realResult.clv.toLocaleString()}</p>
            </div>
            <div>
              <label className="block text-sm text-gray-500">Purchase probability</label>
              <p className="text-2xl font-bold text-gray-800">{(realResult.purchaseProb * 100).toFixed(1)}%</p>
            </div>
            <div>
              <label className="block text-sm text-gray-500">Expected transactions</label>
              <p className="text-2xl font-bold text-gray-800">{realResult.transactionCount}</p>
            </div>
            <div>
              <label className="block text-sm text-gray-500">Expected order value</label>
              <p className="text-2xl font-bold text-gray-800">${realResult.orderValue.toLocaleString()}</p>
            </div>
          </div>
        </div>
      )}
      {apiError && (
        <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded">
          <p className="text-sm text-red-700 flex items-center"><AlertTriangle className="w-4 h-4 mr-1"/> {apiError}</p>
        </div>
      )}
    </div>
  );
};

export default CLVPrediction;
