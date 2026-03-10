import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AppShell } from './components/layout/AppShell';
import { DashboardPage } from './pages/DashboardPage';
import { TasksPage } from './pages/TasksPage';
import { FlowsPage } from './pages/FlowsPage';
import { CostsPage } from './pages/CostsPage';
import { AgentsPage } from './pages/AgentsPage';
import { RootAgentsPage } from './pages/RootAgentsPage';
import { useSSE } from './hooks/useSSE';

function AppContent() {
  useSSE();

  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/tasks" element={<TasksPage />} />
        <Route path="/flows" element={<FlowsPage />} />
        <Route path="/agents" element={<AgentsPage />} />
        <Route path="/root-agents" element={<RootAgentsPage />} />
        <Route path="/costs" element={<CostsPage />} />
      </Routes>
    </AppShell>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AppContent />
    </BrowserRouter>
  );
}
