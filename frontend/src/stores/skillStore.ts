import { create } from 'zustand'
import type { SkillInfo } from '../api/skills'
import * as api from '../api/skills'

interface SkillState {
  items: SkillInfo[]
  total: number
  page: number
  pageSize: number
  search: string
  typeFilter: string
  loading: boolean
  error: string | null
  fetch: (opts?: { page?: number; pageSize?: number; search?: string; type?: string }) => Promise<void>
  create: (payload: api.SkillCreatePayload) => Promise<SkillInfo>
  update: (id: string, payload: api.SkillUpdatePayload) => Promise<void>
  remove: (id: string) => Promise<void>
  toggleEnabled: (id: string, enabled: boolean) => Promise<void>
  setSearch: (s: string) => void
  setTypeFilter: (t: string) => void
  setPage: (p: number) => void
}

export const useSkillStore = create<SkillState>((set, get) => ({
  items: [],
  total: 0,
  page: 1,
  pageSize: 20,
  search: '',
  typeFilter: '',
  loading: false,
  error: null,

  fetch: async (opts) => {
    const { page, pageSize, search, typeFilter } = { ...get(), ...opts }
    set({ loading: true, error: null })
    try {
      const params: Record<string, string | number> = { page: opts?.page ?? page, page_size: opts?.pageSize ?? pageSize }
      const qs = opts?.search ?? search
      const qt = opts?.type ?? typeFilter
      if (qs) params.search = qs
      if (qt) params.type = qt
      const res = await api.listSkills(params)
      set({ items: res.items, total: res.total, page: params.page as number, pageSize: params.page_size as number, loading: false })
    } catch (e: any) {
      set({ loading: false, error: e?.response?.data?.detail || e?.message || '获取列表失败' })
    }
  },

  create: async (payload) => {
    const skill = await api.createSkill(payload)
    get().fetch()
    return skill
  },

  update: async (id, payload) => {
    await api.updateSkill(id, payload)
    get().fetch()
  },

  remove: async (id) => {
    await api.deleteSkill(id)
    get().fetch()
  },

  toggleEnabled: async (id, enabled) => {
    await api.toggleSkill(id, enabled)
    const updated = get().items.map((s) => (s.id === id ? { ...s, enabled } : s))
    set({ items: updated })
  },

  setSearch: (search) => { set({ search, page: 1 }); get().fetch({ search, page: 1 }) },
  setTypeFilter: (type) => { set({ typeFilter: type, page: 1 }); get().fetch({ type, page: 1 }) },
  setPage: (page) => { set({ page }); get().fetch({ page }) },
}))
