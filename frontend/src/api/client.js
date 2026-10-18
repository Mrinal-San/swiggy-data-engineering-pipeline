const API_BASE = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '');

export class APIError extends Error {
  constructor(message, status, code, requestId) {
    super(message);
    this.name = 'APIError';
    this.status = status;
    this.code = code;
    this.requestId = requestId;
  }
}

export async function api(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { ...(options.body ? { 'Content-Type': 'application/json' } : {}), ...options.headers },
  });
  let payload;
  try { payload = await response.json(); }
  catch { throw new APIError('The server returned an unreadable response.', response.status); }
  if (!response.ok) {
    const detail = payload?.error || {};
    throw new APIError(detail.message || 'The request could not be completed.', response.status, detail.code, payload?.request_id);
  }
  return payload;
}

export const queryString = (params) => new URLSearchParams(
  Object.entries(params).filter(([, value]) => value !== undefined && value !== null && value !== ''),
).toString();
