import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AppShell } from './shared/layout/AppShell';
import { DashboardPage } from './features/dashboard/DashboardPage';
import { TasksPage } from './features/tasks/TasksPage';
import { FlowsPage } from './features/flows/FlowsPage';
import { CostsPage } from './features/costs/CostsPage';
import { AgentsPage } from './features/agents/AgentsPage';
import { RootAgentsPage } from './features/root-agents/RootAgentsPage';
import { ToolsPage } from './features/tools/ToolsPage';
import { SessionsPage } from './features/sessions/SessionsPage';
import { useSSE } from './shared/hooks/useSSE';

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
        <Route path="/tools" element={<ToolsPage />} />
        <Route path="/sessions" element={<SessionsPage />} />
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
