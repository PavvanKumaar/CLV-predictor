import React, { useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import {
  BrowserRouter,
  NavLink,
  Routes,
  Route,
  Navigate,
  useLocation
} from 'react-router-dom';
import {
  LayoutDashboard,
  Users,
  Target,
  ChartNoAxesCombined,
  Activity,
  RefreshCw,
  Search,
  Menu,
  X,
  TrendingUp,
  UserRound,
  AlertCircle
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

async function request(path) {
  const response = await fetch(`${API}${path}`);
  const body = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(
      typeof body.detail === 'string'
        ? body.detail
        : `API request failed: ${response.status} ${path}`
    );
  }

  return body;
}

function listFrom(data) {
  if (Array.isArray(data)) return data;
  if (Array.isArray(data?.items)) return data.items;
  if (Array.isArray(data?.results)) return data.results;
  if (Array.isArray(data?.predictions)) return data.predictions;
  if (Array.isArray(data?.customers)) return data.customers;
  return [];
}

function normalizeCustomer(row) {
  return {
    ...row,
    customer_id: row.customer_id ?? row.id ?? row.customerId ?? 'Unknown',
    segment: row.segment ?? 'Unassigned',
    predicted_clv_90d: Number(
      row.predicted_clv_90d ?? row.predicted_clv ?? row.clv ?? 0
    ),
    prob_purchase: Number(row.prob_purchase ?? row.purchase_probability ?? 0),
    expected_transactions: Number(row.expected_transactions ?? 0),
    is_cold_start: Boolean(row.is_cold_start)
  };
}

function useData() {
  const [data, setData] = useState({
    customers: [],
    predictions: [],
    summary: null,
    model: null
  });
  const [loading, setLoading] = useState(true);
  const [errors, setErrors] = useState([]);

  async function refresh() {
    setLoading(true);
    const results = await Promise.allSettled([
      request('/customers?limit=500'),
      request('/clv/predictions?limit=500'),
      request('/clv/summary'),
      request('/model/status')
    ]);

    const next = { customers: [], predictions: [], summary: null, model: null };
    const messages = [];

    results.forEach((result, index) => {
      const keys = ['customers', 'predictions', 'summary', 'model'];

      if (result.status === 'fulfilled') {
        if (index === 0 || index === 1) {
          next[keys[index]] = listFrom(result.value).map(normalizeCustomer);
        } else {
          next[keys[index]] = result.value;
        }
      } else {
        messages.push(`${keys[index]}: ${result.reason?.message || 'Request failed'}`);
      }
    });

    setData(next);
    setErrors(messages);
    setLoading(false);
  }

  useEffect(() => {
    refresh();
  }, []);

  return { ...data, loading, errors, refresh };
}

const navItems = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/customers', label: 'Customers', icon: Users },
  { to: '/clv-prediction', label: 'CLV Prediction', icon: Target },
  { to: '/analytics', label: 'Analytics', icon: ChartNoAxesCombined },
  { to: '/model-performance', label: 'Model Performance', icon: Activity }
];

function Sidebar({ open, onClose }) {
  return (
    <>
      {open && <div className="mobile-overlay" onClick={onClose} />}
      <aside className={`sidebar ${open ? 'sidebar-open' : ''}`}>
        <div className="brand">
          <div className="brand-icon">CLV</div>
          <div>
            <strong>CLV Predictor</strong>
            <span>Customer Intelligence</span>
          </div>
          <button className="close-menu" onClick={onClose} aria-label="Close menu">
            <X size={20} />
          </button>
        </div>

        <div className="nav-label">WORKSPACE</div>

        <nav className="side-nav">
          {navItems.map(item => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                onClick={onClose}
                className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
              >
                <Icon size={19} />
                <span>{item.label}</span>
              </NavLink>
            );
          })}
        </nav>

        <div className="sidebar-footer">
          <div className="status-dot" />
          <div>
            <strong>API integration</strong>
            <span>FastAPI · Port 8000</span>
          </div>
        </div>
      </aside>
    </>
  );
}

function Header({ onMenu, onRefresh, loading }) {
  const location = useLocation();
  const current = navItems.find(item =>
    item.end ? location.pathname === item.to : location.pathname === item.to
  );

  return (
    <header className="topbar">
      <button className="menu-button" onClick={onMenu} aria-label="Open menu">
        <Menu size={22} />
      </button>
      <div>
        <span className="topbar-eyebrow">CUSTOMER INTELLIGENCE</span>
        <h2>{current?.label || 'Dashboard'}</h2>
      </div>
      <button className="refresh-button" onClick={onRefresh} disabled={loading}>
        <RefreshCw size={16} className={loading ? 'spin' : ''} />
        <span>{loading ? 'Loading' : 'Refresh data'}</span>
      </button>
    </header>
  );
}

function PageTitle({ title, description, action }) {
  return (
    <div className="page-title">
      <div>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {action}
    </div>
  );
}

function StatCard({ title, value, subtitle, icon: Icon, color = 'purple' }) {
  return (
    <article className="stat-card">
      <div className={`stat-icon ${color}`}><Icon size={21} /></div>
      <div className="stat-label">{title}</div>
      <div className="stat-value">{value}</div>
      <div className="stat-subtitle">{subtitle}</div>
    </article>
  );
}

function ErrorNotice({ errors }) {
  if (!errors.length) return null;

  return (
    <div className="error-notice">
      <AlertCircle size={19} />
      <div>
        <strong>Some data could not be loaded</strong>
        <ul>{errors.map((error, i) => <li key={i}>{error}</li>)}</ul>
        <span>Check that the backend is running and the API endpoints are available.</span>
      </div>
    </div>
  );
}

function EmptyState({ loading, message = 'No records returned by the API.' }) {
  return (
    <div className="empty-state">
      {loading ? <RefreshCw className="spin" size={24} /> : <Target size={26} />}
      <strong>{loading ? 'Loading data…' : message}</strong>
      {!loading && <span>Check the backend data and prediction pipeline.</span>}
    </div>
  );
}

function SegmentChart({ predictions }) {
  const chartData = useMemo(() => {
    const groups = {};

    predictions.forEach(row => {
      const key = row.segment || 'Unassigned';
      if (!groups[key]) groups[key] = { segment: key, customers: 0, clv: 0 };
      groups[key].customers += 1;
      groups[key].clv += row.predicted_clv_90d;
    });

    return Object.values(groups);
  }, [predictions]);

  return (
    <div className="chart-box">
      {chartData.length ? (
        <ResponsiveContainer width="100%" height={290}>
          <BarChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="segment" tick={{ fontSize: 12 }} />
            <YAxis allowDecimals={false} />
            <Tooltip />
            <Bar dataKey="customers" name="Customers" fill="#6d5ce8" radius={[5, 5, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      ) : <EmptyState message="No segment data available." />}
    </div>
  );
}

function Dashboard({ data, loading }) {
  const { customers, predictions, summary, model } = data;

  const customerCount = summary?.count ?? predictions.length;
  const totalCLV = summary?.total_predicted_clv ??
    predictions.reduce((total, row) => total + row.predicted_clv_90d, 0);
  const averageCLV = summary?.average_predicted_clv ??
    (predictions.length ? totalCLV / predictions.length : 0);
  const averageProbability = summary?.average_purchase_probability;

  return (
    <>
      <PageTitle
        title="Dashboard"
        description="Monitor customer lifetime value and purchase prediction data."
      />

      <div className="stats-grid">
        <StatCard title="Customers loaded" value={number(customers.length)}
          subtitle="Records returned by customers API" icon={Users} color="purple" />
        <StatCard title="CLV predictions" value={number(customerCount)}
          subtitle="Predictions returned by backend" icon={Target} color="blue" />
        <StatCard title="Total predicted CLV" value={money(totalCLV)}
          subtitle="Sum of returned predictions" icon={TrendingUp} color="green" />
        <StatCard title="Average predicted CLV" value={money(averageCLV)}
          subtitle="Average per prediction" icon={UserRound} color="orange" />
      </div>

      <ErrorNotice errors={data.errors || []} />

      <div className="dashboard-grid">
        <section className="panel">
          <div className="panel-heading">
            <div>
              <h3>Customers by segment</h3>
              <p>Distribution from the returned CLV predictions.</p>
            </div>
          </div>
          <SegmentChart predictions={predictions} />
        </section>

        <section className="panel model-panel">
          <div className="panel-heading">
            <div>
              <h3>Model status</h3>
              <p>Current backend response</p>
            </div>
            <Activity size={20} />
          </div>
          {model ? (
            <div className="model-details">
              <div><span>Model version</span><strong>{model.model_version || 'Not reported'}</strong></div>
              <div><span>Status</span><strong>{model.status || 'Response received'}</strong></div>
              <div><span>Purchase probability average</span><strong>
                {averageProbability == null ? 'Not available' : percent(averageProbability)}
              </strong></div>
              <div><span>Cold-start customers</span><strong>{number(summary?.cold_start_count ?? 0)}</strong></div>
            </div>
          ) : <EmptyState loading={loading} message="Model status unavailable." />}
          <p className="footnote">Evaluation scores are not inferred from prediction data.</p>
        </section>
      </div>

      <section className="panel">
        <div className="panel-heading">
          <div>
            <h3>Recent CLV predictions</h3>
            <p>Latest records returned by the prediction endpoint.</p>
          </div>
        </div>
        <PredictionTable rows={predictions.slice(0, 8)} loading={loading} />
      </section>
    </>
  );
}

function PredictionTable({ rows, loading }) {
  if (!rows.length) return <EmptyState loading={loading} />;

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
          {rows.map((row, i) => (
            <tr key={`${row.customer_id}-${i}`}>
              <td><strong>{row.customer_id}</strong></td>
              <td><span className="segment-badge">{row.segment}</span></td>
              <td>{percent(row.prob_purchase)}</td>
              <td>{row.expected_transactions.toFixed(2)}</td>
              <td className="money-cell">{money(row.predicted_clv_90d)}</td>
              <td>{row.is_cold_start ? 'Cold start' : 'Existing history'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function CustomersPage({ data, loading }) {
  const [query, setQuery] = useState('');
  const [segment, setSegment] = useState('All');

  // Always use saved CLV prediction records for the Customers table.
  const customerRows = data.predictions;

  const segments = [
    ...new Set(customerRows.map(row => row.segment || 'Unassigned'))
  ];

  const rows = customerRows.filter(row => {
    const matchesQuery = String(row.customer_id ?? '')
      .toLowerCase()
      .includes(query.toLowerCase());

    const rowSegment = row.segment || 'Unassigned';
    const matchesSegment = segment === 'All' || rowSegment === segment;

    return matchesQuery && matchesSegment;
  });

  return (
    <>
      <PageTitle
        title="Customers"
        description="Search and inspect customer predictions returned by the backend."
      />
      <ErrorNotice errors={data.errors || []} />
      <section className="panel">
        <div className="toolbar">
          <div className="search-box">
            <Search size={17} />
            <input
              value={query}
              onChange={event => setQuery(event.target.value)}
              placeholder="Search customer ID..."
            />
          </div>

          <select
            value={segment}
            onChange={event => setSegment(event.target.value)}
          >
            <option value="All">All segments</option>
            {segments.map(name => (
              <option key={name} value={name}>{name}</option>
            ))}
          </select>

          <span className="result-count">{number(rows.length)} records</span>
        </div>

        <PredictionTable rows={rows} loading={loading} />
      </section>
    </>
  );
}

function CLVPage({ data, loading }) {
  const [query, setQuery] = useState('');
  const rows = data.predictions.filter(row =>
    String(row.customer_id).toLowerCase().includes(query.toLowerCase())
  );

  return (
    <>
      <PageTitle title="CLV Prediction" description="Review predicted customer lifetime value for the next 90 days." />
      <ErrorNotice errors={data.errors || []} />
      <div className="stats-grid compact-grid">
        <StatCard title="Predictions" value={number(data.summary?.count ?? data.predictions.length)}
          subtitle="Backend prediction count" icon={Target} />
        <StatCard title="Total predicted CLV" value={money(data.summary?.total_predicted_clv ??
          data.predictions.reduce((sum, row) => sum + row.predicted_clv_90d, 0))}
          subtitle="Returned predictions" icon={TrendingUp} color="green" />
        <StatCard title="Average purchase probability"
          value={data.summary?.average_purchase_probability == null
            ? 'N/A' : percent(data.summary.average_purchase_probability)}
          subtitle="Reported by backend" icon={Activity} color="blue" />
        <StatCard title="Cold-start share"
          value={data.summary?.cold_start_share == null
            ? 'N/A' : percent(data.summary.cold_start_share)}
          subtitle="Reported by backend" icon={Users} color="orange" />
      </div>
      <section className="panel">
        <div className="toolbar">
          <div className="search-box">
            <Search size={17} />
            <input value={query} onChange={e => setQuery(e.target.value)}
              placeholder="Search customer ID…" />
          </div>
          <span className="result-count">{number(rows.length)} predictions</span>
        </div>
        <PredictionTable rows={rows} loading={loading} />
      </section>
    </>
  );
}

function AnalyticsPage({ data, loading }) {
  const segments = data.summary?.segments || {};
  const segmentData = Object.entries(segments).map(([name, value]) => ({
    name,
    customers: Number(value)
  }));

  const colors = ['#6d5ce8', '#17a673', '#e99a36', '#3987e6', '#d75a72'];

  return (
    <>
      <PageTitle title="Analytics" description="Explore customer segments and available CLV prediction data." />
      <ErrorNotice errors={data.errors || []} />
      <div className="stats-grid">
        <StatCard title="Predictions analyzed" value={number(data.predictions.length)}
          subtitle="Records returned by API" icon={Target} />
        <StatCard title="Total predicted CLV"
          value={money(data.summary?.total_predicted_clv ??
            data.predictions.reduce((sum, row) => sum + row.predicted_clv_90d, 0))}
          subtitle="Predicted value" icon={TrendingUp} color="green" />
      </div>
      <div className="dashboard-grid">
        <section className="panel">
          <h3>Predictions by segment</h3>
          <p>Segment counts supplied by the CLV summary endpoint.</p>
          {segmentData.length ? (
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie data={segmentData} dataKey="customers" nameKey="name"
                  cx="50%" cy="50%" outerRadius={100} label>
                  {segmentData.map((entry, i) =>
                    <Cell key={entry.name} fill={colors[i % colors.length]} />
                  )}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          ) : <EmptyState loading={loading} message="Segment summary unavailable." />}
        </section>
        <section className="panel">
          <h3>CLV by segment</h3>
          <p>Sum of predicted 90-day CLV grouped by segment.</p>
          <SegmentChart predictions={data.predictions} />
        </section>
      </div>
      <p className="footnote">
        These charts describe the data returned by the API. Historical revenue trends
        and actual-versus-predicted comparisons require corresponding source data.
      </p>
    </>
  );
}

function ModelPerformancePage({ data, loading }) {
  const model = data.model || {};
  const summary = data.summary || {};

  return (
    <>
      <PageTitle title="Model Performance"
        description="Inspect available model metadata and prediction coverage." />
      <ErrorNotice errors={data.errors || []} />
      <section className="panel">
        <h3>Model information</h3>
        {loading ? <EmptyState loading /> : (
          <div className="model-details">
            <div><span>Model version</span><strong>{model.model_version || 'Not reported'}</strong></div>
            <div><span>Model status</span><strong>{model.status || 'Not reported'}</strong></div>
            <div><span>Trained at</span><strong>{model.trained_at || 'Not reported'}</strong></div>
            <div><span>Prediction count</span><strong>{number(summary.count ?? data.predictions.length)}</strong></div>
            <div><span>Average predicted CLV</span><strong>
              {summary.average_predicted_clv == null
                ? 'Not available' : money(summary.average_predicted_clv)}
            </strong></div>
          </div>
        )}
      </section>
      <section className="panel">
        <h3>Evaluation metrics</h3>
        <p>
          This frontend does not assume model accuracy. ROC-AUC, Brier score, MAE,
          RMSE, and other evaluation metrics will appear here only when the backend
          exposes verified evaluation results.
        </p>
        <div className="info-banner">
          Prediction volume and predicted CLV are operational metrics, not measures of model accuracy.
        </div>
      </section>
    </>
  );
}

function App() {
  const data = useData();
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <div className="app-shell">
      <Sidebar open={menuOpen} onClose={() => setMenuOpen(false)} />
      <div className="main-area">
        <Header
          onMenu={() => setMenuOpen(true)}
          onRefresh={data.refresh}
          loading={data.loading}
        />
        <main className="content">
          <Routes>
            <Route path="/" element={<Dashboard data={data} loading={data.loading} />} />
            <Route path="/customers" element={<CustomersPage data={data} loading={data.loading} />} />
            <Route path="/clv-prediction" element={<CLVPage data={data} loading={data.loading} />} />
            <Route path="/analytics" element={<AnalyticsPage data={data} loading={data.loading} />} />
            <Route path="/model-performance" element={<ModelPerformancePage data={data} loading={data.loading} />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
          <footer className="app-footer">
            CLV Predictor · Values are based on backend responses, not fabricated demo metrics.
          </footer>
        </main>
      </div>
    </div>
  );
}

createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>
);