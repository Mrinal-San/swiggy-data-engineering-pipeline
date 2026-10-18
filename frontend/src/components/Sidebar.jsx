import { NavLink, useLocation } from 'react-router-dom';
import { BarChart3, Bot, Database, LayoutDashboard, RefreshCw } from 'lucide-react';
import { useState } from 'react';
import { refreshData } from '../api/dashboard.js';
import { useAppState } from '../context/AppState.jsx';
import ErrorState from './ErrorState.jsx';

const links = [
  { to: '/', label: 'Dashboard', Icon: LayoutDashboard, end: true },
  { to: '/assistant', label: 'AI Data Assistant', Icon: Bot },
];

export default function Sidebar() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const { bumpRefresh } = useAppState();
  const location = useLocation();
  const navOpen = location.pathname === '/data-status';

  async function refresh() {
    setBusy(true); setError('');
    try { await refreshData(); bumpRefresh(); }
    catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  return (
    <aside className="sidebar">
      <NavLink to="/" className="brand">
        <img src="/assets/swiggy_mark.svg" alt="" />
        <span><strong>Swiggy BI</strong><small>Business intelligence</small></span>
      </NavLink>
      <div className="nav-label">Workspace</div>
      <nav className="primary-nav" aria-label="Main navigation">
        {links.map(({ to, label, Icon, end }) => (
          <NavLink key={to} to={to} end={end} className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>
            <Icon size={18} strokeWidth={1.8} /><span>{label}</span>
          </NavLink>
        ))}
      </nav>
      <div className="sidebar-spacer" />
      <div className="source-card">
        <span className="source-indicator" />
        <span><strong>Amazon Athena</strong><small>Gold · ap-southeast-2</small></span>
      </div>
      <NavLink to="/data-status" className={`nav-link utility-link${navOpen ? ' active' : ''}`}>
        <Database size={18} strokeWidth={1.8} /><span>Data status</span>
      </NavLink>
      <button className="nav-link refresh-link" type="button" onClick={refresh} disabled={busy}>
        <RefreshCw size={17} className={busy ? 'spin' : ''} /><span>{busy ? 'Refreshing…' : 'Refresh data'}</span>
      </button>
      {error && <ErrorState message={error} compact />}
      <div className="sidebar-footer"><BarChart3 size={15} /> Read-only analytics</div>
    </aside>
  );
}
