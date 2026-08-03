import { create } from 'zustand'
import type { UserInfo, RegisterPayload } from '../api/auth'
import * as authApi from '../api/auth'

interface AuthState {
  user: UserInfo | null
  token: string | null
  loading: boolean
  initialized: boolean

  login: (username: string, password: string) => Promise<void>
  register: (payload: RegisterPayload) => Promise<void>
  logout: () => Promise<void>
  checkAuth: () => Promise<void>
}

export const useAuthStore = create<AuthState>((set) => ({
  user: JSON.parse(localStorage.getItem('user') || 'null'),
  token: localStorage.getItem('token'),
  loading: false,
  initialized: false,

  login: async (username: string, password: string) => {
    set({ loading: true })
    try {
      const res = await authApi.login(username, password)
      localStorage.setItem('token', res.access_token)
      localStorage.setItem('user', JSON.stringify(res.user))
      set({ user: res.user, token: res.access_token, loading: false })
    } catch (e) {
      set({ loading: false })
      throw e
    }
  },

  register: async (payload: RegisterPayload) => {
    set({ loading: true })
    try {
      const res = await authApi.register(payload)
      localStorage.setItem('token', res.access_token)
      localStorage.setItem('user', JSON.stringify(res.user))
      set({ user: res.user, token: res.access_token, loading: false })
    } catch (e) {
      set({ loading: false })
      throw e
    }
  },

  logout: async () => {
    try {
      await authApi.logout()
    } catch {
      // ignore network errors on logout
    }
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    set({ user: null, token: null })
  },

  checkAuth: async () => {
    const token = localStorage.getItem('token')
    if (!token) {
      set({ initialized: true })
      return
    }
    try {
      const user = await authApi.getMe()
      localStorage.setItem('user', JSON.stringify(user))
      set({ user, token, initialized: true })
    } catch {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      set({ user: null, token: null, initialized: true })
    }
  },
}))
