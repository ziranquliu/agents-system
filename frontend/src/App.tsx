import { Routes, Route, Navigate } from 'react-router-dom'
import MainLayout from './components/MainLayout'
import Dashboard from './pages/Dashboard'
import Agents from './pages/Agents'
import AgentDetail from './pages/AgentDetail'
import Conversations from './pages/Conversations'
import ConversationDetail from './pages/ConversationDetail'
import Models from './pages/Models'
import Skills from './pages/Skills'
import MCPServers from './pages/MCPServers'
import Users from './pages/Users'
import Workspaces from './pages/Workspaces'
import OperationLogs from './pages/OperationLogs'
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
        <Route path="mcp" element={<MCPServers />} />
        <Route path="workspaces" element={<Workspaces />} />
        <Route path="users" element={<Users />} />
        <Route path="operation-logs" element={<OperationLogs />} />
      </Route>
      <Route path="*" element={<NotFound />} />
    </Routes>
  )
}

export default App
