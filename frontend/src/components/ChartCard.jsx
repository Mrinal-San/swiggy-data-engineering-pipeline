export default function ChartCard({ title, subtitle, children, className = '' }) {
  return (
    <section className={`panel chart-card ${className}`}>
      <div className="panel-heading"><div><h2>{title}</h2>{subtitle && <p>{subtitle}</p>}</div></div>
      {children}
    </section>
  );
}
