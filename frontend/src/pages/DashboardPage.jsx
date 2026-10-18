import { useEffect, useMemo, useState } from 'react';
import { Activity, Box, ShoppingBag, Wallet } from 'lucide-react';
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { getCities, getCuisines, getDateRange, getDeliveryAnalytics, getSalesTrend, getSummary } from '../api/dashboard.js';
import { useAppState } from '../context/AppState.jsx';
import ChartCard from '../components/ChartCard.jsx';
import DateRangeFilter from '../components/DateRangeFilter.jsx';
import ErrorState from '../components/ErrorState.jsx';
import KPICard from '../components/KPICard.jsx';
import LoadingState from '../components/LoadingState.jsx';
import PageHeader from '../components/PageHeader.jsx';

const INR = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 });
function compactINR(value = 0) {
  const n = Number(value) || 0;
  if (Math.abs(n) >= 1e7) return `₹${(n / 1e7).toFixed(1)}Cr`;
  if (Math.abs(n) >= 1e5) return `₹${(n / 1e5).toFixed(1)}L`;
  if (Math.abs(n) >= 1e3) return `₹${(n / 1e3).toFixed(1)}K`;
  return INR.format(n);
}
const count = (value) => new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 }).format(Number(value) || 0);
const STATUS_COLORS = ['#f26322', '#ff9e6a', '#ffd1b8', '#cfd4da'];

function SalesTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return <div className="chart-tooltip"><strong>{label}</strong><span>{INR.format(Number(payload[0].value) || 0)}</span></div>;
}

export default function DashboardPage() {
  const { dateRange, setDateRange, refreshVersion } = useAppState();
  const [bounds, setBounds] = useState({ first_date: '', last_date: '' });
  const [draft, setDraft] = useState({ start_date: '', end_date: '' });
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastRefreshed, setLastRefreshed] = useState(null);

  useEffect(() => {
    let live = true;
    getDateRange().then((range) => {
      if (!live) return;
      setBounds(range);
      if (!dateRange && range.first_date && range.last_date) {
        const end = new Date(`${range.last_date}T00:00:00Z`);
        const start = new Date(end);
        start.setUTCDate(start.getUTCDate() - 29);
        const minimum = new Date(`${range.first_date}T00:00:00Z`);
        if (start < minimum) start.setTime(minimum.getTime());
        const initial = { start_date: start.toISOString().slice(0, 10), end_date: range.last_date };
        setDateRange(initial); setDraft(initial);
      } else if (dateRange) setDraft(dateRange);
    }).catch((err) => live && setError(err)).finally(() => live && setLoading(false));
    return () => { live = false; };
  // The initial range comes from the API and must be based on available data, not system time.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshVersion]);

  useEffect(() => {
    if (!dateRange?.start_date || !dateRange?.end_date) return undefined;
    let live = true;
    setLoading(true); setError(null);
    Promise.all([
      getSummary(dateRange), getSalesTrend(dateRange), getCities(dateRange),
      getCuisines(dateRange), getDeliveryAnalytics(),
    ]).then(([summary, trend, cities, cuisines, delivery]) => {
      if (live) {
        setData({ summary, trend: trend.data || [], cities: cities.data || [], cuisines: cuisines.data || [], delivery: delivery.order_status || [] });
        setLastRefreshed(new Date());
      }
    }).catch((err) => live && setError(err)).finally(() => live && setLoading(false));
    return () => { live = false; };
  }, [dateRange, refreshVersion]);

  const selectedLabel = useMemo(() => {
    if (!dateRange) return 'Loading available dates';
    return `${dateRange.start_date} — ${dateRange.end_date} · INR`;
  }, [dateRange]);

  function applyDates() {
    if (!draft.start_date || !draft.end_date || draft.start_date > draft.end_date) {
      setError(new Error('Choose a valid start and end date.'));
      return;
    }
    setDateRange({ ...draft });
  }

  const summary = data?.summary;
  const previous = summary?.previous_period;
  const comparisonDays = dateRange?.start_date && dateRange?.end_date
    ? Math.max(1, Math.round((Date.parse(`${dateRange.end_date}T00:00:00Z`) - Date.parse(`${dateRange.start_date}T00:00:00Z`)) / 86400000) + 1)
    : 1;

  return (
    <div className="page-content">
      <PageHeader
        eyebrow="Swiggy · Business intelligence"
        title="Dashboard Overview"
        subtitle="Monitor sales, orders, and delivery performance."
        action={lastRefreshed && <span className="refresh-time"><Activity size={14} /> Refreshed {lastRefreshed.toLocaleTimeString()}</span>}
      />
      <section className="filter-panel">
        <div><strong>Order date range</strong><small>{selectedLabel}</small></div>
        <DateRangeFilter value={draft} onChange={setDraft} bounds={bounds} onApply={applyDates} loading={loading} />
      </section>
      <ErrorState message={error?.message} requestId={error?.requestId} />
      {loading && !data ? <LoadingState /> : summary && (
        <>
          <section className="kpi-grid" aria-label="Key performance indicators">
            <KPICard label="Recorded Sales" value={compactINR(summary.recorded_sales)} delta={previous?.recorded_sales_change_pct} description="All recorded order statuses" Icon={Wallet} accent />
            <KPICard label="Total Orders" value={count(summary.total_orders)} delta={previous?.total_orders_change_pct} description="Daily Gold aggregates" Icon={ShoppingBag} />
            <KPICard label="Average Order Value" value={compactINR(summary.average_order_value)} description="Recorded sales per recorded order" Icon={Activity} />
            <KPICard label="Items Sold" value={count(summary.items_sold)} description="Item lines, not quantity units" Icon={Box} />
          </section>
          <p className="comparison-note">Previous-period comparisons use the immediately preceding {comparisonDays}-day period when prior data is available.</p>

          <div className="dashboard-grid primary-charts">
            <ChartCard title="Weekly sales trend" subtitle="Recorded sales · selected date range" className="wide-chart">
              {data.trend.length ? <ResponsiveContainer width="100%" height={300}>
                <AreaChart data={data.trend.map((row) => ({ ...row, recorded_sales: Number(row.recorded_sales) || 0 }))} margin={{ top: 12, right: 10, left: 12, bottom: 0 }}>
                  <defs><linearGradient id="salesFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#FC8019" stopOpacity={0.2} /><stop offset="95%" stopColor="#FC8019" stopOpacity={0.01} /></linearGradient></defs>
                  <CartesianGrid vertical={false} stroke="#ECEDEF" />
                  <XAxis dataKey="period_start" tickLine={false} axisLine={false} tick={{ fill: '#777B82', fontSize: 11 }} tickFormatter={(d) => new Date(`${d}T00:00:00Z`).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', timeZone: 'UTC' })} />
                  <YAxis tickLine={false} axisLine={false} width={58} tick={{ fill: '#777B82', fontSize: 11 }} tickFormatter={compactINR} />
                  <Tooltip content={<SalesTooltip />} />
                  <Area type="monotone" dataKey="recorded_sales" stroke="#FC8019" strokeWidth={2.4} fill="url(#salesFill)" activeDot={{ r: 4 }} />
                </AreaChart>
              </ResponsiveContainer> : <div className="empty-state">No sales found in this period.</div>}
            </ChartCard>
            <ChartCard title="Sales by city" subtitle="Top 10 · selected date range">
              {data.cities.length ? <ResponsiveContainer width="100%" height={300}>
                <BarChart data={data.cities.map((row) => ({ ...row, recorded_sales: Number(row.recorded_sales) || 0 }))} margin={{ top: 8, right: 10, left: 0, bottom: 35 }}>
                  <CartesianGrid vertical={false} stroke="#ECEDEF" />
                  <XAxis dataKey="city" angle={-25} textAnchor="end" interval={0} tickLine={false} axisLine={false} tick={{ fill: '#555B62', fontSize: 10 }} />
                  <YAxis tickLine={false} axisLine={false} tick={{ fill: '#777B82', fontSize: 10 }} tickFormatter={compactINR} />
                  <Tooltip formatter={(value) => INR.format(Number(value) || 0)} />
                  <Bar dataKey="recorded_sales" fill="#FC8019" radius={[5, 5, 0, 0]} barSize={25} />
                </BarChart>
              </ResponsiveContainer> : <div className="empty-state">No city sales found.</div>}
            </ChartCard>
          </div>

          <div className="dashboard-grid secondary-charts">
            <ChartCard title="Sales by cuisine" subtitle="Top 10 · selected date range">
              {data.cuisines.length ? <ResponsiveContainer width="100%" height={270}>
                <BarChart data={[...data.cuisines].reverse().map((row) => ({ ...row, recorded_sales: Number(row.recorded_sales) || 0 }))} layout="vertical" margin={{ top: 4, right: 12, left: 8, bottom: 4 }}>
                  <CartesianGrid horizontal={false} stroke="#ECEDEF" />
                  <XAxis type="number" tickLine={false} axisLine={false} tick={{ fill: '#777B82', fontSize: 10 }} tickFormatter={compactINR} />
                  <YAxis type="category" dataKey="cuisine" width={95} tickLine={false} axisLine={false} tick={{ fill: '#555B62', fontSize: 11 }} />
                  <Tooltip formatter={(value) => INR.format(Number(value) || 0)} />
                  <Bar dataKey="recorded_sales" fill="#FC8019" radius={[0, 5, 5, 0]} barSize={17} />
                </BarChart>
              </ResponsiveContainer> : <div className="empty-state">No cuisine sales found.</div>}
            </ChartCard>
            <ChartCard title="Delivery order status" subtitle="All time · order-status Gold aggregates">
              {data.delivery.length ? <>
                <ResponsiveContainer width="100%" height={230}>
                  <PieChart>
                    <Pie data={data.delivery.map((row) => ({ ...row, total_orders: Number(row.total_orders) || 0 }))} dataKey="total_orders" nameKey="order_status" innerRadius={55} outerRadius={88} paddingAngle={3}>
                      {data.delivery.map((row, index) => <Cell key={row.order_status} fill={STATUS_COLORS[index % STATUS_COLORS.length]} />)}
                    </Pie>
                    <Tooltip formatter={(value, name) => [count(value), name]} />
                  </PieChart>
                </ResponsiveContainer>
                <div className="chart-legend">{data.delivery.map((row, index) => <span key={row.order_status}><i style={{ background: STATUS_COLORS[index % STATUS_COLORS.length] }} />{row.order_status} <b>{count(row.total_orders)}</b></span>)}</div>
              </> : <div className="empty-state">No delivery status data is available.</div>}
            </ChartCard>
          </div>
          <p className="footnote">Recorded sales include all statuses and are not a settled-payment measure. Delivery order-status totals are all time.</p>
        </>
      )}
    </div>
  );
}
