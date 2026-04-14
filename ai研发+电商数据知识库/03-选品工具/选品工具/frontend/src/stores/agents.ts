import { defineStore } from 'pinia'
import axios from 'axios'

interface AgentTask {
  id: string
  name: string
  type: 'scan' | 'ai_analysis' | 'alert_check' | 'report'
  status: 'pending' | 'running' | 'completed' | 'failed'
  progress: number
  result: any
  error: string | null
  startedAt: string | null
  completedAt: string | null
  createdAt: string
}

interface AgentStats {
  pending: number
  running: number
  completed: number
  failed: number
}

interface AgentsState {
  tasks: AgentTask[]
  stats: AgentStats
  loading: boolean
  pollingTimer: ReturnType<typeof setInterval> | null
}

export const useAgentsStore = defineStore('agents', {
  state: (): AgentsState => ({
    tasks: [],
    stats: { pending: 0, running: 0, completed: 0, failed: 0 },
    loading: false,
    pollingTimer: null,
  }),

  getters: {
    activeTasks: (state) => state.tasks.filter((t) => t.status === 'running'),
    recentCompleted: (state) =>
      state.tasks.filter((t) => t.status === 'completed').slice(0, 10),
  },

  actions: {
    async fetchTasks(status?: string) {
      this.loading = true
      try {
        const { data } = await axios.get('/api/agents', { params: { status } })
        this.tasks = data
      } finally {
        this.loading = false
      }
    },

    async fetchStats() {
      const { data } = await axios.get('/api/agents/stats')
      this.stats = data
    },

    async dispatch(type: AgentTask['type'], name: string, payload?: object) {
      const { data } = await axios.post('/api/agents/dispatch', { type, name, payload })
      this.tasks.unshift(data)
      return data
    },

    startPolling(intervalMs = 3000) {
      this.stopPolling()
      this.pollingTimer = setInterval(() => {
        this.fetchTasks()
        this.fetchStats()
      }, intervalMs)
    },

    stopPolling() {
      if (this.pollingTimer) {
        clearInterval(this.pollingTimer)
        this.pollingTimer = null
      }
    },
  },
})
