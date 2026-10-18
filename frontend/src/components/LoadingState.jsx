export default function LoadingState({ label = 'Loading analytics…' }) {
  return <div className="loading-state" role="status"><span className="spinner" />{label}</div>;
}
