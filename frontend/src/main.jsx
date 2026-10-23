import React, {useEffect, useState} from 'react';
import {createRoot} from 'react-dom/client';
import {BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer} from 'recharts';
import './style.css';

async function read(path) {
  const response = await fetch(`/api${path}`);
  if (!response.ok) throw new Error(response.status === 404 ? 'Run the stage 1 demo to create a model and predictions.' : 'Could not load results. Check that the API is running.');
  return response.json();
}
function App() {
  const [report, setReport] = useState(null), [rows, setRows] = useState([]), [error, setError] = useState(''), [offset, setOffset] = useState(0), [loading, setLoading] = useState(true);
  useEffect(() => {let active = true; setLoading(true); setError(''); read('/model/status').then(async model => {
    const predictions = await read(`/stage1/predictions?model_version=${encodeURIComponent(model.model_version)}&limit=50&offset=${offset}`);
    if (active) {setReport(model); setRows(predictions);}
  }).catch(e => {if (active) setError(e.message);}).finally(() => {if (active) setLoading(false);}); return () => {active = false;};}, [offset]);
  const comparisons = report ? Object.entries(report.validation).map(([name, value]) => ({name, brier: value.brier})) : [];
  return <main><header><span className="eyebrow">CUSTOMER INTELLIGENCE / DEVELOPMENT</span><h1>Purchase propensity</h1><p>Stage 1 · Probability of a purchase in the next 90 days</p></header>
    <aside>Synthetic demo results validate the workflow. Business accuracy requires your real purchase history.</aside>
    {error && <p role="alert" className="error">{error}</p>}{loading && <p role="status">Loading results…</p>}
    {report && !error && <><section className="cards"><article><label>Selected classifier</label><strong>{report.winner.replaceAll('_', ' ')}</strong></article><article><label>Test ROC-AUC</label><strong>{report.test.roc_auc?.toFixed(3) ?? 'Unavailable'}</strong></article><article><label>Test Brier score</label><strong>{report.test.brier.toFixed(3)}</strong></article><article><label>Top-decile lift</label><strong>{report.test.top_decile_lift?.toFixed(2) ?? 'Unavailable'}×</strong></article></section>
    <section className="panel"><h2>Validation comparison</h2><p>Lower Brier score means better probability predictions. Selection uses validation data only.</p><div style={{height: 260}}><ResponsiveContainer><BarChart data={comparisons}><XAxis dataKey="name"/><YAxis domain={[0, 'auto']}/><Tooltip/><Bar dataKey="brier" fill="#17685e" radius={[5,5,0,0]}/></BarChart></ResponsiveContainer></div></section>
    <section className="panel"><h2>Customer probabilities</h2><p>Run {report.model_version.slice(0,12)} · Test cutoff {report.cutoffs[2].slice(0,10)} · Ranked by purchase probability</p><div className="table-wrap"><table><thead><tr><th>Customer</th><th>Purchase probability</th><th>History path</th></tr></thead><tbody>{rows.map(r => <tr key={r.customer_id}><td>{r.customer_id}</td><td>{(r.prob_purchase*100).toFixed(1)}%</td><td>{r.is_cold_start ? 'Cohort fallback' : 'Classifier'}</td></tr>)}</tbody></table></div><nav><button disabled={offset === 0 || loading} onClick={() => setOffset(Math.max(0,offset-50))}>Previous</button><span>Rows {rows.length ? offset+1 : 0}–{offset+rows.length}</span><button disabled={rows.length < 50 || loading} onClick={() => setOffset(offset+50)}>Next</button></nav></section></>}
  </main>;
}
createRoot(document.getElementById('root')).render(<App/>);
