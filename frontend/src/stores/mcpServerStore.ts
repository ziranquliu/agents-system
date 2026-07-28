import { create } from 'zustand'
import type { MCPServerInfo } from '../api/mcps'
import * as api from '../api/mcps'

interface MCPServerState {
  items: MCPServerInfo[]
  total: number
  page: number
  pageSize: number
  search: string
  statusFilter: string
  loading: boolean
  error: string | null

  fetch: (opts?: { page?: number; pageSize?: number; search?: string; status?: string }) => Promise<void>
  create: (payload: api.MCPServerCreatePayload) => Promise<MCPServerInfo>
  update: (id: string, payload: api.MCPServerUpdatePayload) => Promise<void>
  remove: (id: string) => Promise<void>
  healthCheck: (id: string) => Promise<void>
  setSearch: (s: string) => void
  setStatusFilter: (s: string) => void
  setPage: (p: number) => void
}

export const useMCPServerStore = create<MCPServerState>((set, get) => ({
  items: [],
  total: 0,
  page: 1,
  pageSize: 20,
  search: '',
  statusFilter: '',
  loading: false,
  error: null,

  fetch: async (opts) => {
    const { page, pageSize, search, statusFilter } = { ...get(), ...opts }
    set({ loading: true, error: null })
    try {
      const params: Record<string, string | number> = {
        page: opts?.page ?? page,
        page_size: opts?.pageSize ?? pageSize,
      }
      const qs = opts?.search ?? search
      const qst = opts?.status ?? statusFilter
      if (qs) params.search = qs
      if (qst) params.status = qst
      const res = await api.listMCPServers(params)
      set({ items: res.items, total: res.total, page: params.page as number, pageSize: params.page_size as number, loading: false })
    } catch (e: any) {
      set({ loading: false, error: e?.response?.data?.detail || e?.message || '获取 MCP 服务列表失败' })
    }
  },

  create: async (payload) => {
    const srv = await api.createMCPServer(payload)
    get().fetch()
    return srv
  },

  update: async (id, payload) => {
    await api.updateMCPServer(id, payload)
    get().fetch()
  },

  remove: async (id) => {
    await api.deleteMCPServer(id)
    get().fetch()
  },

  healthCheck: async (id) => {
    try {
      const updated = await api.checkMCPHealth(id)
      const items = get().items.map((s) => (s.id === id ? { ...s, ...updated } : s))
      set({ items })
    } catch {
      // ignore health check errors in UI
    }
  },

  setSearch: (search) => { set({ search, page: 1 }); get().fetch({ search, page: 1 }) },
  setStatusFilter: (status) => { set({ statusFilter: status, page: 1 }); get().fetch({ status, page: 1 }) },
  setPage: (page) => { set({ page }); get().fetch({ page }) },
}))
