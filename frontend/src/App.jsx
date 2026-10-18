import { useMemo, useState } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import { AppStateContext } from './context/AppState.jsx';
import AppLayout from './layouts/AppLayout.jsx';
import DashboardPage from './pages/DashboardPage.jsx';
import AssistantPage from './pages/AssistantPage.jsx';
import DataStatusPage from './pages/DataStatusPage.jsx';
import NotFoundPage from './pages/NotFoundPage.jsx';

export default function App() {
  const [messages, setMessages] = useState([]);
  const [dateRange, setDateRange] = useState(null);
  const [refreshVersion, setRefreshVersion] = useState(0);
  const value = useMemo(() => ({
    messages, setMessages, dateRange, setDateRange,
    refreshVersion, bumpRefresh: () => setRefreshVersion((v) => v + 1),
  }), [messages, dateRange, refreshVersion]);

  return (
    <AppStateContext.Provider value={value}>
      <Routes>
        <Route element={<AppLayout />}>
          <Route index element={<DashboardPage />} />
          <Route path="assistant" element={<AssistantPage />} />
          <Route path="data-status" element={<DataStatusPage />} />
          <Route path="not-found" element={<NotFoundPage />} />
          <Route path="*" element={<Navigate to="/not-found" replace />} />
        </Route>
      </Routes>
    </AppStateContext.Provider>
  );
}
