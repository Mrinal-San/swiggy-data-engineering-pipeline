import { useMemo, useState } from 'react';
import { ArrowDown, ArrowUp, ArrowUpDown } from 'lucide-react';

function display(value, key) {
  if (value === null || value === undefined || value === '') return '—';
  const number = Number(value);
  if (Number.isFinite(number) && typeof value !== 'boolean') {
    if (/sales|revenue|amount|spend/i.test(key)) return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(number);
    if (/rating/i.test(key)) return number.toFixed(2);
    if (/minute|delivery_time/i.test(key)) return `${number.toFixed(1)} min`;
    return new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 }).format(number);
  }
  return String(value);
}

export default function DataTable({ rows = [], columns, emptyText = 'No records are available.' }) {
  const [sort, setSort] = useState({ key: '', direction: 'asc' });
  const keys = (columns || (rows[0] ? Object.keys(rows[0]).map((key) => ({ key, label: key.replaceAll('_', ' ') })) : []))
    .map((column) => typeof column === 'string' ? ({ key: column, label: column.replaceAll('_', ' ') }) : column);
  const sorted = useMemo(() => {
    if (!sort.key) return rows;
    return [...rows].sort((a, b) => {
      const av = a[sort.key] ?? '';
      const bv = b[sort.key] ?? '';
      const an = Number(av), bn = Number(bv);
      const result = Number.isFinite(an) && Number.isFinite(bn) ? an - bn : String(av).localeCompare(String(bv));
      return sort.direction === 'asc' ? result : -result;
    });
  }, [rows, sort]);

  function toggle(key) {
    setSort((prev) => ({ key, direction: prev.key === key && prev.direction === 'asc' ? 'desc' : 'asc' }));
  }

  if (!rows.length) return <div className="empty-state small">{emptyText}</div>;
  return (
    <div className="table-scroll">
      <table className="data-table">
        <thead><tr>{keys.map(({ key, label }) => (
          <th key={key}><button type="button" onClick={() => toggle(key)}>{label}<span>{sort.key === key ? (sort.direction === 'asc' ? <ArrowUp size={13} /> : <ArrowDown size={13} />) : <ArrowUpDown size={13} />}</span></button></th>
        ))}</tr></thead>
        <tbody>{sorted.map((row, index) => <tr key={`${index}-${row[keys[0]?.key] || ''}`}>
          {keys.map(({ key }) => <td key={key}>{display(row[key], key)}</td>)}
        </tr>)}</tbody>
      </table>
    </div>
  );
}
