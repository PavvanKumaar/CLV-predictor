import React, { useCallback, useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import {
  LayoutDashboard,
  Users,
  Target,
  ChartNoAxesCombined,
  Activity,
  RefreshCw,
  Search,
  AlertCircle,
  CheckCircle2,
  Database,
  TrendingUp,
  UserRound,
  Menu,
  X
} from 'lucide-react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  PieChart,
  Pie,
  Cell
} from 'recharts';
import './index.css';

const API = '/api';

const COLORS = ['#6c5ce7', '#10b981', '#f59e0b', '#3b82f6', '#ec4899'];

const money = value =>
  new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0
  }).format(Number(value) || 0);

const number = value =>
  new Intl.NumberFormat('en-IN').format(Number(value) || 0);

const percent = value =>
  `${((Number(value) || 0) * 100).toFixed(1)}%`;

function unwrap(value) {
  if (Array.isArray(value)) return value;
  if (Array.isArray(value?.value)) return value.value;
  if (Array.isArray(value?.items)) return value.items;
  if (Array.isArray(value?.results)) return value.results;
  return [];
}

async function request(path) {
  let response;

  try {
    response = await fetch(`${API}${path}`);
  } catch {
    throw new Error(
      'Cannot connect to FastAPI. Make sure the backend is running on port 8000.'
    );
  }

  if (!response.ok) {
    let message = `Request failed with HTTP ${response.status}.`;

    try {
      const body = await response.json();
      if (body.detail) {
        message =
          typeof body.detail === 'string'
            ? body.detail
            : JSON.stringify(body.detail);
      }
    } catch {
      // Keep the default error message.
    }

    throw new Error(message);
  }

  return response.json();
}

async function loadAllData() {
  const results = await Promise.allSettled([
    request('/customers?limit=500&offset=0'),
    request('/clv/predictions?limit=500&offset=0'),
    request('/clv/summary'),
    request('/model/status'),
    request('/stage1/predictions?limit=500&offset=0')
  ]);

  const [customersResult, predictionsResult, summaryResult, modelResult, stage1Result] =
    results;

  return {
    customers: customersResult.status === 'fulfilled'
      ? unwrap(customersResult.value)
      : [],

    predictions: predictionsResult.status === 'fulfilled'
      ? unwrap(predictionsResult.value)
      : [],

    summary: summaryResult.status === 'fulfilled'
      ? summaryResult.value
      : null,

    model: modelResult.status === 'fulfilled'
      ? modelResult.value
      : null,

    stage1: stage1Result.status === 'fulfilled'
      ? unwrap(stage1Result.value)
      : [],

    errors: results
      .map((result, index) => ({
        result,
        label: [
          'Customers',
          'CLV predictions',
          'CLV summary',
          'Model status',
          'Purchase predictions'
        ][index]
      }))
      .filter(item => item.result.status === 'rejected')
      .map(item => `${item.label}: ${item.result.reason?.message || 'Unable to load data'}`)
  };
}

function PageTitle({ title, description }) {
  return (
    <header className="page-heading">
      <h1>{title}</h1>
      <p>{description}</p>
    </header>
  );
}

function ErrorNotice({ errors = [] }) {
  if (!errors.length) return null;

  return (
    <div className="notice error-notice" role="alert">
      <AlertCircle size={18} />
      <div>
        <strong>Some data could not be loaded.</strong>
        {errors.map((error, index) => (
          <p key={`${error}-${index}`}>{error}</p>
        ))}
      </div>
    </div>
  );
}

function MetricCard({ icon: Icon, label, value, description, color = 'purple' }) {
  return (
    <article className="metric-card">
      <div className={`metric-icon ${color}`}>
        <Icon size={21} />
      </div>
      <span className="metric-label">{label}</span>
      <strong className="metric-value">{value}</strong>
      {description && <small>{description}</small>}
    </article>
  );
}

function Panel({ title, subtitle, children }) {
  return (
    <section className="panel">
      <div className="panel-heading">
        <h2>{title}</h2>
        {subtitle && <p>{subtitle}</p>}
      </div>
      {children}
    </section>
  );
}

function EmptyState({ loading, message = 'No records are available.' }) {
  return (
    <div className="empty-state">
      {loading ? 'Loading data…' : message}
    </div>
  );
}

function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;

  return (
    <div className="chart-tooltip">
      <strong>{label || payload[0].name}</strong>
      {payload.map((item, index) => (
        <p key={`${item.name}-${index}`}>
          {item.name}: {
            typeof item.value === 'number'
              ? number(item.value)
              : item.value
          }
        </p>
      ))}
    </div>
  );
}

function App() {
  const [data, setData] = useState({
    customers: [],
    predictions: [],
    summary: null,
    model: null,
    stage1: [],
    errors: []
  });

  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [page, setPage] = useState('Dashboard');
  const [mobileMenu, setMobileMenu] = useState(false);

  const refresh = useCallback(async () => {
    setRefreshing(true);

    try {
      const nextData = await loadAllData();
      setData(nextData);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const navigation = [
    { name: 'Dashboard', icon: LayoutDashboard },
    { name: 'Customers', icon: Users },
    { name: 'CLV Prediction', icon: Target },
    { name: 'Analytics', icon: ChartNoAxesCombined },
    { name: 'Model Performance', icon: Activity }
  ];

  function navigate(name) {
    setPage(name);
    setMobileMenu(false);
  }

  return (
    <div className="app-shell">
      {mobileMenu && (
        <button
          className="mobile-overlay"
          aria-label="Close navigation"
          onClick={() => setMobileMenu(false)}
        />
      )}

      <aside className={`sidebar ${mobileMenu ? 'sidebar-open' : ''}`}>
        <div className="brand">
          <div className="brand-logo">CLV</div>
          <div>
            <strong>CLV Predictor</strong>
            <span>Customer Intelligence</span>
          </div>
          <button
            className="mobile-close"
            onClick={() => setMobileMenu(false)}
            aria-label="Close navigation"
          >
            <X size={19} />
          </button>
        </div>

        <div className="nav-label">WORKSPACE</div>

        <nav className="navigation">
          {navigation.map(({ name, icon: Icon }) => (
            <button
              key={name}
              className={`nav-item ${page === name ? 'active' : ''}`}
              onClick={() => navigate(name)}
            >
              <Icon size={19} />
              <span>{name}</span>
            </button>
          ))}
        </nav>

        <div className="sidebar-footer">
          <span className="status-dot" />
          <div>
            <strong>API integration</strong>
            <span>FastAPI · Port 8000</span>
          </div>
        </div>
      </aside>

      <div className="main-shell">
        <div className="topbar">
          <button
            className="mobile-menu-button"
            aria-label="Open navigation"
            onClick={() => setMobileMenu(true)}
          >
            <Menu size={21} />
          </button>

          <div className="topbar-title">
            <span>CUSTOMER INTELLIGENCE</span>
            <strong>{page}</strong>
          </div>

          <button
            className="refresh-button"
            onClick={refresh}
            disabled={refreshing}
          >
            <RefreshCw
              size={16}
              className={refreshing ? 'spin' : ''}
            />
            <span>{refreshing ? 'Refreshing…' : 'Refresh data'}</span>
          </button>
        </div>

        <main className="page-content">
          <ErrorNotice errors={data.errors} />

          {page === 'Dashboard' && (
            <DashboardPage data={data} loading={loading} />
          )}

          {page === 'Customers' && (
            <CustomersPage data={data} loading={loading} />
          )}

          {page === 'CLV Prediction' && (
            <CLVPredictionPage data={data} loading={loading} />
          )}

          {page === 'Analytics' && (
            <AnalyticsPage data={data} loading={loading} />
          )}

          {page === 'Model Performance' && (
            <ModelPerformancePage data={data} loading={loading} />
          )}

          <footer className="app-footer">
            CLV Predictor · Values are based on backend responses, not fabricated demo metrics.
          </footer>
        </main>
      </div>
    </div>
  );
}

function DashboardPage({ data, loading }) {
  const summary = data.summary || {};
  const customers = data.customers;
  const predictions = data.predictions;

  const totalCLV = Number(summary.total_predicted_clv) ||
    predictions.reduce((sum, row) => sum + (Number(row.predicted_clv_90d) || 0), 0);

  const averageCLV = Number(summary.average_predicted_clv) ||
    (predictions.length ? totalCLV / predictions.length : 0);

  const segmentCounts = Object.entries(summary.segments || {}).map(
    ([name, count]) => ({ name, customers: Number(count) || 0 })
  );

  const derivedSegments = Object.values(
    predictions.reduce((acc, row) => {
      const name = row.segment || 'Unassigned';

      if (!acc[name]) {
        acc[name] = { name, customers: 0 };
      }

      acc[name].customers += 1;
      return acc;
    }, {})
  );

  const chartData = segmentCounts.length ? segmentCounts : derivedSegments;

  return (
    <>
      <PageTitle
        title="Dashboard"
        description="Monitor customer lifetime value and purchase prediction data."
      />

      <section className="metric-grid">
        <MetricCard
          icon={Users}
          label="Customers loaded"
          value={number(customers.length)}
          description="Records returned by customers API"
          color="purple"
        />
        <MetricCard
          icon={Target}
          label="CLV predictions"
          value={number(summary.count ?? predictions.length)}
          description="Predictions reported by backend"
          color="blue"
        />
        <MetricCard
          icon={TrendingUp}
          label="Total predicted CLV"
          value={money(totalCLV)}
          description="Sum of available predictions"
          color="green"
        />
        <MetricCard
          icon={UserRound}
          label="Average predicted CLV"
          value={money(averageCLV)}
          description="Average per prediction"
          color="orange"
        />
      </section>

      <div className="two-column-grid">
        <Panel
          title="Customers by segment"
          subtitle="Distribution from the available CLV prediction data."
        >
          {chartData.length ? (
            <div className="chart-container">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="name" />
                  <YAxis />
                  <Tooltip content={<ChartTooltip />} />
                  <Bar
                    dataKey="customers"
                    name="Customers"
                    fill="#6c5ce7"
                    radius={[5, 5, 0, 0]}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <EmptyState loading={loading} message="No segment data available." />
          )}
        </Panel>

        <Panel
          title="Model status"
          subtitle="Current backend response"
        >
          <div className="detail-list">
            <DetailRow
              label="Model version"
              value={data.model?.model_version || 'Unavailable'}
            />
            <DetailRow
              label="Status"
              value={data.model?.status || 'Unavailable'}
            />
            <DetailRow
              label="Purchase probability average"
              value={
                summary.average_purchase_probability != null
                  ? percent(summary.average_purchase_probability)
                  : 'Unavailable'
              }
            />
            <DetailRow
              label="Cold-start customers"
              value={
                summary.cold_start_count != null
                  ? number(summary.cold_start_count)
                  : 'Unavailable'
              }
            />
          </div>

          <p className="muted-note">
            Prediction coverage and model evaluation scores are different metrics.
          </p>
        </Panel>
      </div>

      <RecentPredictions predictions={predictions} loading={loading} />
    </>
  );
}

function DetailRow({ label, value }) {
  return (
    <div className="detail-row">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function RecentPredictions({ predictions, loading }) {
  return (
    <Panel
      title="Recent CLV predictions"
      subtitle="Records returned by the prediction endpoint."
    >
      <PredictionTable predictions={predictions.slice(0, 10)} loading={loading} />
    </Panel>
  );
}

function CustomersPage({ data, loading }) {
  const [query, setQuery] = useState('');
  const [segment, setSegment] = useState('All');

  const predictionMap = new Map();

  data.predictions.forEach(prediction => {
    const id = String(prediction.customer_id);
    const existing = predictionMap.get(id);

    if (!existing) {
      predictionMap.set(id, prediction);
    }
  });

  const customerRows = data.customers.map(customer => {
    const id = String(customer.customer_id);
    const prediction = predictionMap.get(id);

    return {
      ...customer,
      ...(prediction || {}),
      customer_id: id,
      segment: prediction?.segment ?? customer.segment ?? 'Unassigned',
      prob_purchase: prediction?.prob_purchase ?? customer.prob_purchase,
      expected_transactions:
        prediction?.expected_transactions ?? customer.expected_transactions,
      predicted_clv_90d:
        prediction?.predicted_clv_90d ?? customer.predicted_clv_90d,
      is_cold_start:
        prediction?.is_cold_start ?? customer.is_cold_start ?? false,
      hasPrediction: Boolean(prediction)
    };
  });

  const segments = [...new Set(customerRows.map(row => row.segment))];

  const rows = customerRows.filter(row => {
    const matchesQuery = String(row.customer_id)
      .toLowerCase()
      .includes(query.toLowerCase());

    const matchesSegment =
      segment === 'All' || row.segment === segment;

    return matchesQuery && matchesSegment;
  });

  return (
    <>
      <PageTitle
        title="Customers"
        description="Search customer records and inspect their available CLV predictions."
      />

      <Panel title="Customer records">
        <div className="toolbar">
          <div className="search-box">
            <Search size={17} />
            <input
              value={query}
              onChange={event => setQuery(event.target.value)}
              placeholder="Search customer ID…"
            />
          </div>

          <select
            value={segment}
            onChange={event => setSegment(event.target.value)}
          >
            <option value="All">All segments</option>
            {segments.map(value => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>

          <span className="result-count">
            {number(rows.length)} records
          </span>
        </div>

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Customer ID</th>
                <th>Segment</th>
                <th>Purchase probability</th>
                <th>Expected transactions</th>
                <th>Predicted CLV (90d)</th>
                <th>History</th>
              </tr>
            </thead>

            <tbody>
              {rows.map((row, index) => (
                <tr key={`${row.customer_id}-${index}`}>
                  <td><strong>{row.customer_id}</strong></td>
                  <td>
                    <span className="segment-badge">{row.segment}</span>
                  </td>
                  <td>
                    {row.prob_purchase == null
                      ? 'Not available'
                      : percent(row.prob_purchase)}
                  </td>
                  <td>
                    {row.expected_transactions == null
                      ? 'Not available'
                      : Number(row.expected_transactions).toFixed(2)}
                  </td>
                  <td className="money-cell">
                    {row.predicted_clv_90d == null
                      ? 'Not available'
                      : money(row.predicted_clv_90d)}
                  </td>
                  <td>
                    {row.hasPrediction
                      ? row.is_cold_start
                        ? 'Cold start'
                        : 'Prediction available'
                      : 'No matching prediction'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {!rows.length && (
            <EmptyState loading={loading} message="No matching customers found." />
          )}
        </div>
      </Panel>
    </>
  );
}

function PredictionTable({ predictions, loading }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Customer ID</th>
            <th>Segment</th>
            <th>Purchase probability</th>
            <th>Expected transactions</th>
            <th>Predicted CLV (90d)</th>
            <th>History</th>
          </tr>
        </thead>

        <tbody>
          {predictions.map((row, index) => (
            <tr key={`${row.customer_id}-${row.snapshot_id || index}`}>
              <td><strong>{row.customer_id}</strong></td>
              <td>
                <span className="segment-badge">
                  {row.segment || 'Unassigned'}
                </span>
              </td>
              <td>
                {row.prob_purchase == null
                  ? 'Not available'
                  : percent(row.prob_purchase)}
              </td>
              <td>
                {row.expected_transactions == null
                  ? 'Not available'
                  : Number(row.expected_transactions).toFixed(2)}
              </td>
              <td className="money-cell">
                {row.predicted_clv_90d == null
                  ? 'Not available'
                  : money(row.predicted_clv_90d)}
              </td>
              <td>
                {row.is_cold_start ? 'Cold start' : 'Existing history'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {!predictions.length && (
        <EmptyState loading={loading} message="No CLV predictions available." />
      )}
    </div>
  );
}

function CLVPredictionPage({ data, loading }) {
  const [query, setQuery] = useState('');

  const summary = data.summary || {};
  const predictions = data.predictions.filter(row =>
    String(row.customer_id)
      .toLowerCase()
      .includes(query.toLowerCase())
  );

  return (
    <>
      <PageTitle
        title="CLV Prediction"
        description="Review predicted customer lifetime value for the next 90 days."
      />

      <section className="metric-grid">
        <MetricCard
          icon={Target}
          label="Predictions reported"
          value={number(summary.count ?? data.predictions.length)}
          description="Count reported by the backend"
          color="purple"
        />
        <MetricCard
          icon={TrendingUp}
          label="Total predicted CLV"
          value={money(
            summary.total_predicted_clv ??
            data.predictions.reduce(
              (sum, row) => sum + (Number(row.predicted_clv_90d) || 0),
              0
            )
          )}
          description="Available predicted value"
          color="green"
        />
        <MetricCard
          icon={Activity}
          label="Average purchase probability"
          value={
            summary.average_purchase_probability == null
              ? 'Unavailable'
              : percent(summary.average_purchase_probability)
          }
          description="Reported by the backend"
          color="blue"
        />
        <MetricCard
          icon={Users}
          label="Cold-start share"
          value={
            summary.cold_start_share == null
              ? 'Unavailable'
              : percent(summary.cold_start_share)
          }
          description="Reported by the backend"
          color="orange"
        />
      </section>

      <Panel
        title="Customer CLV predictions"
        subtitle="Search available prediction records by customer ID."
      >
        <div className="toolbar">
          <div className="search-box">
            <Search size={17} />
            <input
              value={query}
              onChange={event => setQuery(event.target.value)}
              placeholder="Search customer ID…"
            />
          </div>

          <span className="result-count">
            {number(predictions.length)} loaded records
          </span>
        </div>

        <PredictionTable predictions={predictions} loading={loading} />

        <p className="muted-note">
          The table displays records returned by the API. Its loaded record
          count may be smaller than the total prediction count reported by the
          summary endpoint.
        </p>
      </Panel>
    </>
  );
}

function AnalyticsPage({ data, loading }) {
  const predictions = data.predictions;
  const summary = data.summary || {};

  const segments = Object.values(
    predictions.reduce((acc, row) => {
      const name = row.segment || 'Unassigned';

      if (!acc[name]) {
        acc[name] = {
          name,
          customers: 0,
          totalCLV: 0,
          probabilityTotal: 0,
          probabilityCount: 0
        };
      }

      acc[name].customers += 1;
      acc[name].totalCLV += Number(row.predicted_clv_90d) || 0;

      if (row.prob_purchase != null) {
        acc[name].probabilityTotal += Number(row.prob_purchase) || 0;
        acc[name].probabilityCount += 1;
      }

      return acc;
    }, {})
  ).map(segment => ({
    ...segment,
    averageCLV: segment.customers
      ? segment.totalCLV / segment.customers
      : 0,
    averageProbability: segment.probabilityCount
      ? segment.probabilityTotal / segment.probabilityCount
      : null
  }));

  const pieData = segments.map(segment => ({
    name: segment.name,
    value: segment.customers
  }));

  return (
    <>
      <PageTitle
        title="Analytics"
        description="Explore customer segments and available CLV prediction data."
      />

      <section className="metric-grid metric-grid-two">
        <MetricCard
          icon={Target}
          label="Predictions loaded"
          value={number(predictions.length)}
          description="Records loaded into the page"
          color="purple"
        />
        <MetricCard
          icon={TrendingUp}
          label="Total predicted CLV"
          value={money(
            summary.total_predicted_clv ??
            predictions.reduce(
              (sum, row) => sum + (Number(row.predicted_clv_90d) || 0),
              0
            )
          )}
          description="Available predicted value"
          color="green"
        />
      </section>

      <div className="two-column-grid">
        <Panel
          title="Predictions by segment"
          subtitle="Count of loaded predictions grouped by segment."
        >
          {pieData.length ? (
            <div className="chart-container">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={pieData}
                    dataKey="value"
                    nameKey="name"
                    cx="50%"
                    cy="50%"
                    outerRadius={105}
                    label={({ name, value }) => `${name}: ${value}`}
                  >
                    {pieData.map((entry, index) => (
                      <Cell
                        key={entry.name}
                        fill={COLORS[index % COLORS.length]}
                      />
                    ))}
                  </Pie>
                  <Tooltip content={<ChartTooltip />} />
                </PieChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <EmptyState loading={loading} message="No segment data available." />
          )}
        </Panel>

        <Panel
          title="Total predicted CLV by segment"
          subtitle="Sum of loaded 90-day predictions, in INR."
        >
          {segments.length ? (
            <div className="chart-container">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={segments}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="name" />
                  <YAxis />
                  <Tooltip
                    formatter={value => money(value)}
                  />
                  <Bar
                    dataKey="totalCLV"
                    name="Total predicted CLV"
                    fill="#6c5ce7"
                    radius={[5, 5, 0, 0]}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <EmptyState loading={loading} message="No CLV data available." />
          )}
        </Panel>
      </div>

      <Panel
        title="Segment summary"
        subtitle="Metrics calculated from the prediction records loaded by this page."
      >
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Segment</th>
                <th>Customers</th>
                <th>Total predicted CLV</th>
                <th>Average predicted CLV</th>
                <th>Average purchase probability</th>
              </tr>
            </thead>

            <tbody>
              {segments.map(segment => (
                <tr key={segment.name}>
                  <td>
                    <span className="segment-badge">{segment.name}</span>
                  </td>
                  <td>{number(segment.customers)}</td>
                  <td className="money-cell">{money(segment.totalCLV)}</td>
                  <td className="money-cell">{money(segment.averageCLV)}</td>
                  <td>
                    {segment.averageProbability == null
                      ? 'Unavailable'
                      : percent(segment.averageProbability)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {!segments.length && (
            <EmptyState loading={loading} message="No segment metrics available." />
          )}
        </div>
      </Panel>

      <p className="muted-note">
        Charts describe the records loaded from the API. They do not represent
        the complete population unless the backend returns every prediction.
      </p>
    </>
  );
}

function ModelPerformancePage({ data, loading }) {
  const model = data.model || {};
  const summary = data.summary || {};
  const validation = model.validation || {};

  const validationRows = Object.entries(validation).map(([name, metrics]) => ({
    name,
    brier: Number(metrics?.brier),
    roc_auc: Number(metrics?.roc_auc),
    pr_auc: Number(metrics?.pr_auc),
    top_decile_lift: Number(metrics?.top_decile_lift)
  })).filter(row =>
    Number.isFinite(row.brier) ||
    Number.isFinite(row.roc_auc)
  );

  const test = model.test || model.stage1_raw_test || {};

  return (
    <>
      <PageTitle
        title="Model Performance"
        description="Inspect available model metadata and prediction coverage."
      />

      <Panel title="Model information">
        <div className="detail-list">
          <DetailRow
            label="Model version"
            value={model.model_version || 'Unavailable'}
          />
          <DetailRow
            label="Model status"
            value={model.status || 'Unavailable'}
          />
          <DetailRow
            label="Selected classifier"
            value={model.winner || 'Unavailable'}
          />
          <DetailRow
            label="Trained at"
            value={model.trained_at || 'Not supplied by API'}
          />
          <DetailRow
            label="Prediction count"
            value={summary.count == null
              ? number(data.predictions.length)
              : number(summary.count)}
          />
          <DetailRow
            label="Average predicted CLV"
            value={summary.average_predicted_clv == null
              ? 'Unavailable'
              : money(summary.average_predicted_clv)}
          />
        </div>
      </Panel>

      <Panel
        title="Evaluation metrics"
        subtitle="Metrics are displayed only when the backend provides evaluation results."
      >
        {Object.keys(test).length > 0 && (
          <div className="metric-grid">
            <MetricCard
              icon={Activity}
              label="Test ROC-AUC"
              value={test.roc_auc == null
                ? 'Unavailable'
                : Number(test.roc_auc).toFixed(3)}
              color="blue"
            />
            <MetricCard
              icon={TrendingUp}
              label="Test Brier score"
              value={test.brier == null
                ? 'Unavailable'
                : Number(test.brier).toFixed(4)}
              color="purple"
            />
            <MetricCard
              icon={Target}
              label="Top-decile lift"
              value={test.top_decile_lift == null
                ? 'Unavailable'
                : `${Number(test.top_decile_lift).toFixed(2)}×`}
              color="green"
            />
          </div>
        )}

        {validationRows.length ? (
          <div className="chart-container">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={validationRows}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="name" />
                <YAxis />
                <Tooltip />
                <Bar
                  dataKey="brier"
                  name="Validation Brier score"
                  fill="#6c5ce7"
                  radius={[5, 5, 0, 0]}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <div className="notice">
            <Database size={18} />
            <span>
              {loading
                ? 'Loading evaluation data…'
                : 'The API does not expose validation metrics in its current response.'}
            </span>
          </div>
        )}

        <p className="muted-note">
          Prediction count and predicted CLV measure operational output, not
          model accuracy. Evaluation scores require verified test-set results.
        </p>
      </Panel>

      <Panel title="Purchase propensity model">
        <div className="detail-list">
          <DetailRow
            label="Purchase predictions loaded"
            value={number(data.stage1.length)}
          />
          <DetailRow
            label="CLV predictions loaded"
            value={number(data.predictions.length)}
          />
          <DetailRow
            label="Cold-start CLV predictions"
            value={summary.cold_start_count == null
              ? 'Unavailable'
              : number(summary.cold_start_count)}
          />
        </div>
      </Panel>
    </>
  );
}

createRoot(document.getElementById('root')).render(<App />);