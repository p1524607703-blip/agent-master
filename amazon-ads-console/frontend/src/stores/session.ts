import { defineStore } from 'pinia'
import { API_BASE, AUTH_TOKEN_KEY } from '../api/client'
import { tracedFetch } from '../diagnostics/browserTrace'
import { clearBrowserTrace } from '../diagnostics/browserTrace'

export type AuthUser = {
  userId: number
  username: string
  displayName: string
  roleCode: 'super_admin' | 'management' | 'operator' | string
  operatorCode: string | null
}

type LoginResponse = {
  accessToken: string
  tokenType: string
  expiresAt: string
  user: AuthUser
}

export const useSessionStore = defineStore('session', {
  state: () => ({
    token: localStorage.getItem(AUTH_TOKEN_KEY) as string | null,
    user: null as AuthUser | null,
    initialized: false,
  }),
  getters: {
    isAuthenticated: (state) => Boolean(state.token && state.user),
    roleLabel: (state) => {
      if (state.user?.roleCode === 'super_admin') return '超级管理员'
      if (state.user?.roleCode === 'management') return '管理层'
      if (state.user?.roleCode === 'operator') return '运营'
      return '未登录'
    },
  },
  actions: {
    clear() {
      clearBrowserTrace()
      this.token = null
      this.user = null
      this.initialized = true
      localStorage.removeItem(AUTH_TOKEN_KEY)
    },
    async login(username: string, password: string) {
      const response = await tracedFetch(`${API_BASE}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      })
      if (!response.ok) throw new Error('用户名或密码错误')
      const data = await response.json() as LoginResponse
      this.token = data.accessToken
      this.user = data.user
      this.initialized = true
      localStorage.setItem(AUTH_TOKEN_KEY, data.accessToken)
      return data.user
    },
    async ensureUser() {
      if (!this.token) {
        this.clear()
        return false
      }
      if (this.user) return true
      if (this.initialized) return false
      try {
        const response = await tracedFetch(`${API_BASE}/auth/me`, {
          headers: { Authorization: `Bearer ${this.token}` },
        })
        if (!response.ok) {
          this.clear()
          return false
        }
        const data = await response.json() as { user: AuthUser }
        this.user = data.user
        this.initialized = true
        return true
      } catch {
        this.clear()
        return false
      }
    },
    async logout() {
      const token = this.token
      if (token) {
        try {
          await tracedFetch(`${API_BASE}/auth/logout`, {
            method: 'POST',
            headers: { Authorization: `Bearer ${token}` },
          })
        } catch {
          // Local state must still clear if the network is unavailable.
        }
      }
      this.clear()
    },
  },
})
