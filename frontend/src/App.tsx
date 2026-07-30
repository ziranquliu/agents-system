import { Routes, Route, Navigate } from 'react-router-dom'
import MainLayout from './components/MainLayout'
import Dashboard from './pages/Dashboard'
import Agents from './pages/Agents'
import AgentDetail from './pages/AgentDetail'
import Conversations from './pages/Conversations'
import ConversationDetail from './pages/ConversationDetail'
import Models from './pages/Models'
import SkillMarket from './pages/SkillMarket'
import AgentMarket from './pages/AgentMarket'
import MCPMarket from './pages/MCPMarket'
import ModelMarket from './pages/ModelMarket'
import Skills from './pages/Skills'
import MCPServers from './pages/MCPServers'
import Users from './pages/Users'
import Workspaces from './pages/Workspaces'
import OperationLogs from './pages/OperationLogs'
import ScannerDashboard from './pages/ScannerDashboard'
import UpdateCenter from './pages/UpdateCenter'
import CollaborationsPage from './pages/CollaborationsPage'
import SkillOptimization from './pages/SkillOptimization'
import MCPOptimization from './pages/MCPOptimization'
import ConversationEnhancement from './pages/ConversationEnhancement'
import KnowledgePage from './pages/KnowledgePage'
import TaskPage from './pages/TaskPage'
import AgentMemoryPage from './pages/AgentMemoryPage'
import ModelTemplatePage from './pages/ModelTemplatePage'
import BatchInstallPage from './pages/BatchInstallPage'
import SkillReusePage from './pages/SkillReusePage'
import SystemMonitorPage from './pages/SystemMonitorPage'
import Login from './pages/Login'
import NotFound from './pages/NotFound'

function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/" element={<MainLayout />}>
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={<Dashboard />} />
        <Route path="agents" element={<Agents />} />
        <Route path="agents/:id" element={<AgentDetail />} />
        <Route path="conversations" element={<Conversations />} />
        <Route path="conversations/:id" element={<ConversationDetail />} />
        <Route path="models" element={<Models />} />
        <Route path="skills" element={<Skills />} />
        <Route path="batch-install" element={<BatchInstallPage />} />
        <Route path="skill-reuse" element={<SkillReusePage />} />
        <Route path="skill-market" element={<SkillMarket />} />
        <Route path="agent-market" element={<AgentMarket />} />
        <Route path="model-market" element={<ModelMarket />} />
        <Route path="model-templates" element={<ModelTemplatePage />} />
        <Route path="mcp" element={<MCPServers />} />
        <Route path="mcp-market" element={<MCPMarket />} />
        <Route path="workspaces" element={<Workspaces />} />
        <Route path="users" element={<Users />} />
        <Route path="operation-logs" element={<OperationLogs />} />
        <Route path="scanner" element={<ScannerDashboard />} />
        <Route path="updates" element={<UpdateCenter />} />
        <Route path="collaborations" element={<CollaborationsPage />} />
        <Route path="skill-optimization" element={<SkillOptimization />} />
        <Route path="mcp-optimization" element={<MCPOptimization />} />
        <Route path="conversation-enhancement" element={<ConversationEnhancement />} />
        <Route path="knowledge" element={<KnowledgePage />} />
        <Route path="tasks" element={<TaskPage />} />
        <Route path="agent-memory" element={<AgentMemoryPage />} />
        <Route path="system-monitor" element={<SystemMonitorPage />} />
      </Route>
      <Route path="*" element={<NotFound />} />
    </Routes>
  )
}

export default App
