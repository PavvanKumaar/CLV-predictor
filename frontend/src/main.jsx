import React, {useEffect, useState} from 'react';
import {createRoot} from 'react-dom/client';
import {BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer} from 'recharts';
import './index.css';

async function read(path) {
  const response = await fetch(`/api${path}`);
  if (!response.ok) {
    if (response.status === 404) {
      const err = new Error('No stage-one model has been trained yet.');
      err.code = 404;
      throw err;
    }
    throw new Error('Could not load results. Check that the API is running.');
  }
  return response.json();
}

function App() {
  const [report, setReport] = useState(null);
  const [rows, setRows] = useState([]);
  const [error, setError] = useState('');
  const [errorCode, setErrorCode] = useState(null);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [demoRunning, setDemoRunning] = useState(false);
  const [demoSuccess, setDemoSuccess] = useState(null);

  function loadData() {
    setLoading(true);
    setError('');
    setErrorCode(null);
    let active = true;
    read('/model/status').then(async model => {
      const predictions = await read(`/stage1/predictions?model_version=${encodeURIComponent(model.model_version)}&limit=50&offset=${offset}`);
      if (active) { setReport(model); setRows(predictions); }
    }).catch(e => {
      if (active) { setError(e.message); setErrorCode(e.code || null); }
    }).finally(() => {
      if (active) setLoading(false);
    });
    return () => { active = false; };
  }

  useEffect(loadData, [offset]);

  async function handleRunDemo() {
    setDemoRunning(true);
    setDemoSuccess(null);
    setError('');
    setErrorCode(null);
    try {
      const resp = await fetch('/api/stage1/demo', { method: 'POST' });
      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}));
        throw new Error(body.detail || `Demo failed with status ${resp.status}`);
      }
      const result = await resp.json();
      setDemoSuccess(result);
      // Reload the dashboard data after the demo completes
      setOffset(0);
      loadData();
    } catch (e) {
      setError(e.message);
      setErrorCode(null);
    } finally {
      setDemoRunning(false);
    }
  }

  const comparisons = report ? Object.entries(report.validation).map(([name, value]) => ({name, brier: value.brier})) : [];

  return <main>
    <header>
      <span className="eyebrow">CUSTOMER INTELLIGENCE / DEVELOPMENT</span>
      <h1>Purchase propensity</h1>
      <p>Stage 1 · Probability of a purchase in the next 90 days</p>
    </header>

    <aside>Synthetic demo results validate the workflow. Business accuracy requires your real purchase history.</aside>

    {/* Demo success banner */}
    {demoSuccess && <div className="success-banner">
      <strong>✓ Stage 1 demo completed</strong>
      <p>Model <code>{demoSuccess.model_version?.slice(0, 12)}</code> trained · Winner: <strong>{demoSuccess.winner?.replaceAll('_', ' ')}</strong> · Test ROC-AUC: <strong>{demoSuccess.test?.roc_auc?.toFixed(3) ?? 'N/A'}</strong></p>
    </div>}

    {/* 404 → show Run Demo button */}
    {errorCode === 404 && !demoRunning && <div className="demo-prompt">
      <h2>No model found</h2>
      <p>Run the Stage 1 demo to generate synthetic data, train a classifier, and produce purchase predictions.</p>
      <button className="demo-button" onClick={handleRunDemo}>
        Run Stage 1 Demo
      </button>
    </div>}

    {/* Demo running indicator */}
    {demoRunning && <div className="demo-running">
      <div className="spinner"></div>
      <div>
        <strong>Running Stage 1 demo…</strong>
        <p>Generating data, training classifiers, and scoring customers. This may take 30–60 seconds.</p>
      </div>
    </div>}

    {/* Non-404 errors */}
    {error && errorCode !== 404 && !demoRunning && <p role="alert">{error}</p>}

    {loading && !demoRunning && !error && <p role="status">Loading results…</p>}

    {report && !error && <>
      <section className="cards">
        <article><label>Selected classifier</label><strong>{report.winner.replaceAll('_', ' ')}</strong></article>
        <article><label>Test ROC-AUC</label><strong>{report.test.roc_auc?.toFixed(3) ?? 'Unavailable'}</strong></article>
        <article><label>Test Brier score</label><strong>{report.test.brier.toFixed(3)}</strong></article>
        <article><label>Top-decile lift</label><strong>{report.test.top_decile_lift?.toFixed(2) ?? 'Unavailable'}×</strong></article>
      </section>

      <section className="panel">
        <h2>Validation comparison</h2>
        <p>Lower Brier score means better probability predictions. Selection uses validation data only.</p>
        <div style={{height: 260}}>
          <ResponsiveContainer>
            <BarChart data={comparisons}>
              <XAxis dataKey="name"/>
              <YAxis domain={[0, 'auto']}/>
              <Tooltip/>
              <Bar dataKey="brier" fill="#6366f1" radius={[5,5,0,0]}/>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </section>

      <section className="panel">
        <h2>Customer probabilities</h2>
        <p>Run {report.model_version.slice(0,12)} · Test cutoff {report.cutoffs[2].slice(0,10)} · Ranked by purchase probability</p>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Customer</th><th>Purchase probability</th><th>History path</th></tr></thead>
            <tbody>{rows.map(r => <tr key={r.customer_id}><td>{r.customer_id}</td><td>{(r.prob_purchase*100).toFixed(1)}%</td><td>{r.is_cold_start ? 'Cohort fallback' : 'Classifier'}</td></tr>)}</tbody>
          </table>
        </div>
        <nav>
          <button disabled={offset === 0 || loading} onClick={() => setOffset(Math.max(0,offset-50))}>Previous</button>
          <span>Rows {rows.length ? offset+1 : 0}–{offset+rows.length}</span>
          <button disabled={rows.length < 50 || loading} onClick={() => setOffset(offset+50)}>Next</button>
        </nav>
      </section>
    </>}
  </main>;
}

createRoot(document.getElementById('root')).render(<App/>);
