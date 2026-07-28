import { create } from 'zustand'
import type { AgentInfo } from '../api/agents'
import * as agentsApi from '../api/agents'

interface AgentState {
  agents: AgentInfo[]
  selectedAgent: AgentInfo | null
  total: number
  page: number
  pageSize: number
  search: string
  statusFilter: string
  loading: boolean
  error: string | null

  fetchAgents: (opts?: {
    page?: number
    pageSize?: number
    search?: string
    status?: string
  }) => Promise<void>
  fetchAgent: (id: string) => Promise<void>
  createAgent: (payload: agentsApi.AgentCreatePayload) => Promise<AgentInfo>
  updateAgent: (id: string, payload: agentsApi.AgentUpdatePayload) => Promise<void>
  deleteAgent: (id: string) => Promise<void>
  updateStatus: (id: string, status: string) => Promise<void>
  setSearch: (search: string) => void
  setStatusFilter: (status: string) => void
  setPage: (page: number) => void
}

export const useAgentStore = create<AgentState>((set, get) => ({
  agents: [],
  selectedAgent: null,
  total: 0,
  page: 1,
  pageSize: 20,
  search: '',
  statusFilter: '',
  loading: false,
  error: null,

  fetchAgents: async (opts) => {
    const { page, pageSize, search, statusFilter } = { ...get(), ...opts }
    set({ loading: true, error: null })
    try {
      const params: Record<string, string | number> = {
        page: opts?.page ?? page,
        page_size: opts?.pageSize ?? pageSize,
      }
      const querySearch = opts?.search ?? search
      const queryStatus = opts?.status ?? statusFilter
      if (querySearch) params.search = querySearch
      if (queryStatus) params.status = queryStatus

      const res = await agentsApi.listAgents(params)
      set({
        agents: res.items,
        total: res.total,
        page: params.page as number,
        pageSize: params.page_size as number,
        loading: false,
      })
    } catch (e: any) {
      set({
        loading: false,
        error: e?.response?.data?.detail || e?.message || 'Failed to fetch agents',
      })
    }
  },

  fetchAgent: async (id: string) => {
    set({ loading: true, error: null })
    try {
      const agent = await agentsApi.getAgent(id)
      set({ selectedAgent: agent, loading: false })
    } catch (e: any) {
      set({
        loading: false,
        error: e?.response?.data?.detail || e?.message || 'Failed to fetch agent',
      })
    }
  },

  createAgent: async (payload) => {
    set({ loading: true, error: null })
    try {
      const agent = await agentsApi.createAgent(payload)
      set({ loading: false })
      return agent
    } catch (e: any) {
      set({
        loading: false,
        error: e?.response?.data?.detail || e?.message || 'Failed to create agent',
      })
      throw e
    }
  },

  updateAgent: async (id, payload) => {
    set({ loading: true, error: null })
    try {
      const agent = await agentsApi.updateAgent(id, payload)
      set({ selectedAgent: agent, loading: false })
    } catch (e: any) {
      set({
        loading: false,
        error: e?.response?.data?.detail || e?.message || 'Failed to update agent',
      })
      throw e
    }
  },

  deleteAgent: async (id) => {
    set({ loading: true, error: null })
    try {
      await agentsApi.deleteAgent(id)
      set({ loading: false })
      // refresh list
      get().fetchAgents()
    } catch (e: any) {
      set({
        loading: false,
        error: e?.response?.data?.detail || e?.message || 'Failed to delete agent',
      })
    }
  },

  updateStatus: async (id, status) => {
    try {
      const agent = await agentsApi.updateAgentStatus(id, status)
      set({ selectedAgent: agent })
      // also update in list
      const updatedAgents = get().agents.map((a) =>
        a.id === id ? { ...a, status: agent.status } : a,
      )
      set({ agents: updatedAgents })
    } catch (e: any) {
      throw e
    }
  },

  setSearch: (search) => {
    set({ search, page: 1 })
    get().fetchAgents({ search, page: 1 })
  },
  setStatusFilter: (status) => {
    set({ statusFilter: status, page: 1 })
    get().fetchAgents({ status, page: 1 })
  },
  setPage: (page) => {
    set({ page })
    get().fetchAgents({ page })
  },
}))
