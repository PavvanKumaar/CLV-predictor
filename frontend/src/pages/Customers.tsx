import React, { useEffect, useMemo, useState } from 'react';
import { Search, X, RefreshCw } from 'lucide-react';

interface CLVPrediction {
  customer_id: string;
  model_version: string;
  prob_purchase: number;
  expected_transactions: number;
  expected_value_per_txn: number;
  predicted_clv_90d: number;
  segment: string;
  is_cold_start: boolean;
  predicted_at?: string | null;
}

interface CustomerRow {
  id: string;
  prediction: CLVPrediction;
}

type SegmentFilter = 'All' | 'VIP' | 'Growth' | 'Other' | 'Unassigned';

const currency = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  maximumFractionDigits: 2,
});

const number = new Intl.NumberFormat('en-IN', {
  maximumFractionDigits: 2,
});

async function fetchJSON<T>(path: string): Promise<T> {
  const response = await fetch(`/api${path}`);

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(
      body.detail || `Request failed: ${response.status} ${response.statusText}`
    );
  }

  return response.json() as Promise<T>;
}

const SummaryCard: React.FC<{
  label: string;
  value: React.ReactNode;
}> = ({ label, value }) => (
  <div className="rounded-lg bg-white p-4 shadow">
    <div className="text-sm text-gray-500">{label}</div>
    <div className="text-2xl font-semibold text-gray-800">{value}</div>
  </div>
);

const Customers: React.FC = () => {
  const [predictions, setPredictions] = useState<CLVPrediction[]>([]);
  const [search, setSearch] = useState('');
  const [segment, setSegment] = useState<SegmentFilter>('All');
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [modelVersion, setModelVersion] = useState<string | null>(null);

  const itemsPerPage = 10;

  async function loadData() {
    setLoading(true);
    setError('');

    try {
      // The API defaults to one model version. Fetch all pages for that version.
      const pageSize = 500;
      const allPredictions: CLVPrediction[] = [];
      let offset = 0;
      let selectedModelVersion: string | null = null;

      while (true) {
        const pageData = await fetchJSON<CLVPrediction[]>(
          `/clv/predictions?limit=${pageSize}&offset=${offset}`
        );

        if (pageData.length > 0 && selectedModelVersion === null) {
          selectedModelVersion = pageData[0].model_version;
        }

        // Guard against an API response accidentally mixing model versions.
        const consistentPage = selectedModelVersion
          ? pageData.filter(item => item.model_version === selectedModelVersion)
          : pageData;

        allPredictions.push(...consistentPage);

        if (pageData.length < pageSize) break;
        offset += pageSize;
      }

      setPredictions(allPredictions);
      setModelVersion(selectedModelVersion);
      setPage(1);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Unable to load customer predictions.'
      );
      setPredictions([]);
      setModelVersion(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadData();
  }, []);

  // One prediction per customer is expected after the API filters to one model.
  const rows: CustomerRow[] = useMemo(() => {
    const byCustomer = new Map<string, CLVPrediction>();

    for (const prediction of predictions) {
      byCustomer.set(prediction.customer_id, prediction);
    }

    return Array.from(byCustomer.values())
      .sort((a, b) => a.predicted_clv_90d === b.predicted_clv_90d
        ? a.customer_id.localeCompare(b.customer_id)
        : b.predicted_clv_90d - a.predicted_clv_90d)
      .map(prediction => ({
        id: prediction.customer_id,
        prediction,
      }));
  }, [predictions]);

  const filtered = useMemo(() => {
    const term = search.trim().toLowerCase();

    return rows.filter(row => {
      const matchesId = row.id.toLowerCase().includes(term);
      const value = row.prediction;
      let matchesSegment = true;

      if (segment === 'Unassigned') {
        matchesSegment = !value.segment;
      } else if (segment === 'VIP' || segment === 'Growth') {
        matchesSegment = value.segment === segment;
      } else if (segment === 'Other') {
        matchesSegment =
          !!value.segment &&
          value.segment !== 'VIP' &&
          value.segment !== 'Growth';
      }

      return matchesId && matchesSegment;
    });
  }, [rows, search, segment]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / itemsPerPage));
  const currentPage = Math.min(page, totalPages);
  const paginated = filtered.slice(
    (currentPage - 1) * itemsPerPage,
    currentPage * itemsPerPage
  );

  const totalPredictedCLV = rows.reduce(
    (sum, row) => sum + row.prediction.predicted_clv_90d,
    0
  );
  const averagePredictedCLV = rows.length > 0 ? totalPredictedCLV / rows.length : 0;

  const clearFilters = () => {
    setSearch('');
    setSegment('All');
    setPage(1);
  };

  return (
    <div className="space-y-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold text-gray-800">Customers</h1>
        <p className="text-gray-600">
          Customer purchase probabilities and predicted lifetime value from the latest model.
        </p>
        <p className="text-sm text-gray-500">
          Showing {filtered.length} of {rows.length} customers
          {modelVersion ? ` · Model ${modelVersion}` : ''}
        </p>
      </header>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <SummaryCard label="Customers with predictions" value={number.format(rows.length)} />
        <SummaryCard label="Model version" value={modelVersion ? modelVersion.slice(0, 12) : 'N/A'} />
        <SummaryCard
          label="Average predicted CLV"
          value={rows.length > 0 ? currency.format(averagePredictedCLV) : 'N/A'}
        />
      </div>

      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div className="flex items-center overflow-hidden rounded border bg-white">
          <Search className="mx-2 h-5 w-5 text-gray-400" />
          <input
            type="text"
            placeholder="Search customer ID..."
            className="px-2 py-2 focus:outline-none"
            value={search}
            onChange={event => {
              setSearch(event.target.value);
              setPage(1);
            }}
          />
        </div>

        <select
          value={segment}
          onChange={event => {
            setSegment(event.target.value as SegmentFilter);
            setPage(1);
          }}
          className="rounded border bg-white px-3 py-2"
        >
          <option value="All">All segments</option>
          <option value="VIP">VIP</option>
          <option value="Growth">Growth</option>
          <option value="Other">Other assigned segments</option>
          <option value="Unassigned">Unassigned segment</option>
        </select>

        <div className="flex gap-3">
          <button
            onClick={clearFilters}
            className="flex items-center gap-1 text-sm text-gray-600 hover:text-gray-800"
          >
            <X className="h-4 w-4" />
            Clear filters
          </button>
          <button
            onClick={() => void loadData()}
            disabled={loading}
            className="flex items-center gap-2 rounded border bg-white px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 disabled:opacity-50"
          >
            <RefreshCw className="h-4 w-4" />
            {loading ? 'Loading...' : 'Refresh data'}
          </button>
        </div>
      </div>

      {error && (
        <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-4 text-red-700">
          <p className="font-semibold">Unable to load customer predictions</p>
          <p className="mt-1 text-sm">{error}</p>
          <p className="mt-2 text-sm">Confirm the FastAPI backend is running on port 8000.</p>
        </div>
      )}

      {!error && !loading && rows.length === 0 && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-amber-800">
          No saved CLV predictions were returned by the API. This page does not create
          sample predictions. Check the model run and saved prediction records.
        </div>
      )}

      <div className="overflow-auto rounded-lg bg-white shadow">
        {loading ? (
          <div className="p-8 text-center text-gray-500">Loading customer predictions...</div>
        ) : !error && paginated.length === 0 ? (
          <div className="p-8 text-center text-gray-500">No customers match the current filters.</div>
        ) : !error ? (
          <table className="w-full table-auto">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-sm font-medium text-gray-600">Customer ID</th>
                <th className="px-4 py-3 text-left text-sm font-medium text-gray-600">Segment</th>
                <th className="px-4 py-3 text-left text-sm font-medium text-gray-600">Purchase probability</th>
                <th className="px-4 py-3 text-left text-sm font-medium text-gray-600">Expected transactions</th>
                <th className="px-4 py-3 text-left text-sm font-medium text-gray-600">Predicted CLV (90d)</th>
                <th className="px-4 py-3 text-left text-sm font-medium text-gray-600">History</th>
              </tr>
            </thead>
            <tbody>
              {paginated.map(row => {
                const prediction = row.prediction;
                return (
                  <tr key={`${prediction.model_version}-${row.id}`} className="border-t">
                    <td className="px-4 py-3 font-medium text-gray-800">{row.id}</td>
                    <td className="px-4 py-3">
                      <span className="rounded bg-violet-100 px-2 py-1 text-xs font-medium text-violet-700">
                        {prediction.segment || 'Unassigned'}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      {(prediction.prob_purchase * 100).toFixed(1)}%
                    </td>
                    <td className="px-4 py-3">{number.format(prediction.expected_transactions)}</td>
                    <td className="px-4 py-3 font-semibold text-emerald-600">
                      {currency.format(prediction.predicted_clv_90d)}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600">
                      {prediction.is_cold_start ? 'Cold-start estimate' : 'Prediction available'}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        ) : null}
      </div>

      {!loading && !error && totalPages > 1 && (
        <div className="mt-4 flex items-center justify-center gap-4">
          <button
            onClick={() => setPage(current => Math.max(current - 1, 1))}
            disabled={currentPage === 1}
            className="rounded bg-gray-200 px-3 py-1 disabled:opacity-50"
          >
            Previous
          </button>
          <span className="text-sm text-gray-700">Page {currentPage} of {totalPages}</span>
          <button
            onClick={() => setPage(current => Math.min(current + 1, totalPages))}
            disabled={currentPage === totalPages}
            className="rounded bg-gray-200 px-3 py-1 disabled:opacity-50"
          >
            Next
          </button>
        </div>
      )}

      <p className="text-xs text-gray-500">
        Customer IDs and metrics are sourced from saved predictions for one model version.
        Predicted CLV is an estimate, not realized revenue.
      </p>
    </div>
  );
};

export default Customers;
