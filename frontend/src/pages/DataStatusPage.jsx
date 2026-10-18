import { useEffect, useState } from 'react';
import { Activity, Database, ShieldCheck } from 'lucide-react';
import { api } from '../api/client.js';
import ErrorState from '../components/ErrorState.jsx';
import PageHeader from '../components/PageHeader.jsx';
export default function DataStatusPage() {
  const [health, setHealth] = useState(null); const [range, setRange] = useState(null); const [error, setError] = useState('');
  useEffect(() => { Promise.all([api('/health'), api('/dashboard/date-range')]).then(([h, d]) => { setHealth(h); setRange(d); }).catch((e) => setError(e.message)); }, []);
  return <><PageHeader title="Data status" subtitle="API health, source and available dashboard date range." />{error && <ErrorState message={error} />}<div className="status-grid"><article className="status-card"><Activity /><span>Flask API</span><strong>{health?.status || 'Checking…'}</strong></article><article className="status-card"><Database /><span>Analytics source</span><strong>Amazon Athena · swiggy_gold</strong></article><article className="status-card"><ShieldCheck /><span>Query access</span><strong>Validated read-only SQL</strong></article></div><section className="panel status-range"><h2>Dashboard data range</h2><p>{range?.first_date || '—'} <span>to</span> {range?.last_date || '—'}</p><small>Dashboard summary, sales trend and city or cuisine breakdowns use the selected range. Restaurant, customer and delivery models provide all-time aggregates.</small></section></>;
}
