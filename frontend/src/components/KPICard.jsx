export default function KPICard({ label, value, delta, description, Icon, accent = false }) {
  return (
    <article className={`kpi-card${accent ? ' kpi-accent' : ''}`}>
      <div className="kpi-top">
        <span className="kpi-label">{label}</span>
        {Icon && <span className="kpi-icon"><Icon size={17} /></span>}
      </div>
      <div className="kpi-value">{value}</div>
      <div className="kpi-foot">
        {delta !== undefined && delta !== null
          ? <span className={`kpi-delta ${delta >= 0 ? 'positive' : 'negative'}`}>{delta >= 0 ? '↗' : '↘'} {Math.abs(delta).toFixed(1)}%</span>
          : <span className="kpi-neutral">—</span>}
        <span>{description}</span>
      </div>
    </article>
  );
}
