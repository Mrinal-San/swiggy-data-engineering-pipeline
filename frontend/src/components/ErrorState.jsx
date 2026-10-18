import { AlertCircle } from 'lucide-react';

export default function ErrorState({ message, requestId, compact = false }) {
  if (!message) return null;
  return (
    <div className={`error-state${compact ? ' compact' : ''}`} role="alert">
      <AlertCircle size={17} />
      <div><strong>Something went wrong</strong><span>{message}</span>{requestId && <small>Request ID: {requestId}</small>}</div>
    </div>
  );
}
