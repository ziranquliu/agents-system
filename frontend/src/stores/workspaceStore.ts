import { create } from 'zustand'
import type { WorkspaceInfo } from '../api/workspaces'
import * as api from '../api/workspaces'

interface WorkspaceState {
  items: WorkspaceInfo[]
  total: number
  page: number
  pageSize: number
  search: string
  loading: boolean
  error: string | null
  fetch: (opts?: { page?: number; pageSize?: number; search?: string }) => Promise<void>
  create: (payload: api.WorkspaceCreatePayload) => Promise<WorkspaceInfo>
  update: (id: string, payload: api.WorkspaceUpdatePayload) => Promise<void>
  remove: (id: string) => Promise<void>
  setSearch: (s: string) => void
  setPage: (p: number) => void
}

export const useWorkspaceStore = create<WorkspaceState>((set, get) => ({
  items: [],
  total: 0,
  page: 1,
  pageSize: 20,
  search: '',
  loading: false,
  error: null,

  fetch: async (opts) => {
    const { page, pageSize, search } = { ...get(), ...opts }
    set({ loading: true, error: null })
    try {
      const params: Record<string, string | number> = { page: opts?.page ?? page, page_size: opts?.pageSize ?? pageSize }
      const qs = opts?.search ?? search
      if (qs) params.search = qs
      const res = await api.listWorkspaces(params)
      set({ items: res.items, total: res.total, page: params.page as number, pageSize: params.page_size as number, loading: false })
    } catch (e: any) {
      set({ loading: false, error: e?.response?.data?.detail || e?.message || '获取列表失败' })
    }
  },

  create: async (payload) => {
    const ws = await api.createWorkspace(payload)
    get().fetch()
    return ws
  },

  update: async (id, payload) => {
    await api.updateWorkspace(id, payload)
    get().fetch()
  },

  remove: async (id) => {
    await api.deleteWorkspace(id)
    get().fetch()
  },

  setSearch: (search) => { set({ search, page: 1 }); get().fetch({ search, page: 1 }) },
  setPage: (page) => { set({ page }); get().fetch({ page }) },
}))
