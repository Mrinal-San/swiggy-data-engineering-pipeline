import { api } from './client.js';

export const askAssistant = (question) => api('/assistant/ask', {
  method: 'POST',
  body: JSON.stringify({ question }),
});
