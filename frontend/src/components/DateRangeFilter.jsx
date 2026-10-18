export default function DateRangeFilter({ value, onChange, bounds, onApply, loading }) {
  return (
    <form className="date-filter" onSubmit={(event) => { event.preventDefault(); onApply(); }}>
      <label>Start date<input type="date" value={value.start_date || ''} min={bounds.first_date || undefined} max={value.end_date || bounds.last_date || undefined} onChange={(e) => onChange({ ...value, start_date: e.target.value })} /></label>
      <span className="date-separator">to</span>
      <label>End date<input type="date" value={value.end_date || ''} min={value.start_date || bounds.first_date || undefined} max={bounds.last_date || undefined} onChange={(e) => onChange({ ...value, end_date: e.target.value })} /></label>
      <button className="button primary" type="submit" disabled={loading || !value.start_date || !value.end_date}>{loading ? 'Loading…' : 'Apply dates'}</button>
    </form>
  );
}
