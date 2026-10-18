import { useState } from 'react';
import { Bot, Send, Sparkles, UserRound } from 'lucide-react';
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { askAssistant } from '../api/assistant.js';
import DataTable from '../components/DataTable.jsx';
import PageHeader from '../components/PageHeader.jsx';
import { useAppState } from '../context/AppState.jsx';

const suggestions = ['Which cities have the highest sales?', 'Show top performing restaurants', 'How many orders are completed?', 'What is the average delivery time by city?'];
export default function AssistantPage() {
  const { messages, setMessages } = useAppState(); const [question, setQuestion] = useState(''); const [busy, setBusy] = useState(false); const [error, setError] = useState('');
  async function send(value = question) {
    const prompt = value.trim(); if (!prompt || busy) return;
    setQuestion(''); setError(''); setMessages((items) => [...items, { role: 'user', text: prompt }]); setBusy(true);
    try { const answer = await askAssistant(prompt); setMessages((items) => [...items, { role: 'assistant', answer }]); }
    catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }
  return <><PageHeader title="AI data assistant" subtitle="Ask questions about Swiggy sales, orders, restaurants and delivery." />
    <section className="assistant-panel"><div className="chat-history" aria-live="polite">
      {!messages.length && <div className="chat-welcome"><span className="welcome-icon"><Sparkles /></span><h2>What would you like to know?</h2><p>Answers use the project's validated, read-only Athena query workflow.</p><div className="suggestions">{suggestions.map((s) => <button key={s} type="button" onClick={() => send(s)}>{s}</button>)}</div></div>}
      {messages.map((m, i) => <article className={`chat-message ${m.role}`} key={`${i}-${m.text || ''}`}><span className="message-avatar">{m.role === 'user' ? <UserRound size={17} /> : <Bot size={17} />}</span><div className="message-body">{m.role === 'user' ? <p>{m.text}</p> : <><p>{m.answer?.answer}</p>{m.answer?.chart?.type === 'bar' && m.answer.rows?.length > 1 && <div className="assistant-chart"><ResponsiveContainer width="100%" height={250}><BarChart data={m.answer.rows.slice(0, 20)}><CartesianGrid strokeDasharray="3 3" vertical={false} /><XAxis dataKey={m.answer.chart.category} tickLine={false} axisLine={false} /><YAxis tickLine={false} axisLine={false} /><Tooltip /><Bar dataKey={m.answer.chart.value} fill="#f26322" radius={[5, 5, 0, 0]} /></BarChart></ResponsiveContainer></div>}{m.answer?.rows?.length > 0 && <DataTable rows={m.answer.rows} columns={m.answer.columns.map((key) => ({ key, label: key.replaceAll('_', ' ') }))} />}{m.answer?.sql && <details className="sql-details"><summary>Validated SQL</summary><pre>{m.answer.sql}</pre></details>}</>}</div></article>)}
      {busy && <div className="chat-typing"><span /><span /><span /> Analyzing data…</div>}
    </div>{error && <div className="inline-error" role="alert">{error}</div>}<form className="chat-composer" onSubmit={(e) => { e.preventDefault(); send(); }}><textarea aria-label="Ask a data question" placeholder="Ask about sales, orders, cities, restaurants…" value={question} onChange={(e) => setQuestion(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } }} rows={2} /><button aria-label="Send question" type="submit" disabled={!question.trim() || busy}><Send size={18} /></button></form><p className="composer-note">Enter to send · Shift + Enter for a new line</p></section>
  </>;
}
