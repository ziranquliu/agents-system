import React, { Suspense, lazy } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { Spin } from 'antd';
import MainLayout from './layouts/MainLayout';

// Lazy load pages
const LoginPage = lazy(() => import('./pages/LoginPage'));
const DashboardPage = lazy(() => import('./pages/DashboardPage'));
const AgentListPage = lazy(() => import('./pages/agent/AgentListPage'));
const AgentDetailPage = lazy(() => import('./pages/agent/AgentDetailPage'));
const ModelListPage = lazy(() => import('./pages/model/ModelListPage'));
const SkillListPage = lazy(() => import('./pages/skill/SkillListPage'));
const MCPListPage = lazy(() => import('./pages/mcp/MCPListPage'));
const SessionListPage = lazy(() => import('./pages/session/SessionListPage'));
const KnowledgePage = lazy(() => import('./pages/knowledge/KnowledgePage'));
const WorkflowPage = lazy(() => import('./pages/workflow/WorkflowPage'));
const BackupPage = lazy(() => import('./pages/system/BackupPage'));
const AuditPage = lazy(() => import('./pages/system/AuditPage'));
const SystemHealthPage = lazy(() => import('./pages/system/SystemHealthPage'));
const SettingsPage = lazy(() => import('./pages/system/SettingsPage'));
const DashboardConfigPage = lazy(() => import('./pages/dashboard/DashboardConfigPage'));
const TokenQuotaPage = lazy(() => import('./pages/budget/TokenQuotaPage'));

const Loading = () => (
  <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
    <Spin size="large" tip="加载中..." />
  </div>
);

const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const token = localStorage.getItem('access_token');
  if (!token) return <Navigate to="/login" replace />;
  return <>{children}</>;
};

const App: React.FC = () => {
  return (
    <Suspense fallback={<Loading />}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <MainLayout />
            </ProtectedRoute>
          }
        >
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<DashboardPage />} />
          <Route path="agents" element={<AgentListPage />} />
          <Route path="agents/:id" element={<AgentDetailPage />} />
          <Route path="models" element={<ModelListPage />} />
          <Route path="skills" element={<SkillListPage />} />
          <Route path="mcp" element={<MCPListPage />} />
          <Route path="sessions" element={<SessionListPage />} />
          <Route path="knowledge" element={<KnowledgePage />} />
          <Route path="workflows" element={<WorkflowPage />} />
          <Route path="backups" element={<BackupPage />} />
          <Route path="audit" element={<AuditPage />} />
          <Route path="health" element={<SystemHealthPage />} />
          <Route path="settings" element={<SettingsPage />} />
          <Route path="dashboards/:id" element={<DashboardConfigPage />} />
          <Route path="budget" element={<TokenQuotaPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  );
};

export default App;
