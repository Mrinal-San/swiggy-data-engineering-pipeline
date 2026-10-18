import { Outlet } from 'react-router-dom';
import Sidebar from '../components/Sidebar.jsx';

export default function AppLayout() {
  return (
    <div className="app-shell">
      <Sidebar />
      <main className="main-area"><Outlet /></main>
    </div>
  );
}
