import { create } from 'zustand'
import { listMCPServers as apiListMCPServers } from '../api/mcpServers'

export interface MCPServerInfo {
  id: string
  name: string
  endpoint: string
  protocol: 'stdio' | 'sse' | 'streamable-http'
  status: 'online' | 'offline' | 'error'
  healthStatus: 'healthy' | 'degraded' | 'down'
  version: string
  lastChecked: string
}

interface MCPServerState {
  servers: MCPServerInfo[]
  loading: boolean
  error: string | null
  fetchServers: () => Promise<void>
}

export const useMCPServerStore = create<MCPServerState>((set) => ({
  servers: [],
  loading: false,
  error: null,
  fetchServers: async () => {
    set({ loading: true, error: null })
    try {
      const data = await apiListMCPServers()
      set({ servers: data, loading: false })
    } catch (err: any) {
      set({ error: err.message, loading: false })
    }
  },
}))
