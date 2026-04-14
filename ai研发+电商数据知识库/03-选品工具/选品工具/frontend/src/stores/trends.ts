import { defineStore } from 'pinia'
import axios from 'axios'

interface TrendItem {
  id: string
  productId: string
  platform: 'tiktok' | 'reddit' | 'google' | 'facebook'
  metric: string
  value: number
  deltaPercent: number
  recordedAt: string
  product?: { id: string; name: string }
}

interface PlatformSummary {
  platform: string
  count: number
  latestAt: string | null
}

interface TrendsState {
  trending: TrendItem[]
  platforms: PlatformSummary[]
  selectedPlatform: string
  loading: boolean
}

export const useTrendsStore = defineStore('trends', {
  state: (): TrendsState => ({
    trending: [],
    platforms: [],
    selectedPlatform: '',
    loading: false,
  }),

  getters: {
    filteredTrending: (state) =>
      state.selectedPlatform
        ? state.trending.filter((t) => t.platform === state.selectedPlatform)
        : state.trending,
  },

  actions: {
    async fetchTopTrending(platform?: string) {
      this.loading = true
      try {
        const { data } = await axios.get('/api/trends', {
          params: { platform, limit: 20 },
        })
        this.trending = data
      } finally {
        this.loading = false
      }
    },

    async fetchPlatformSummary() {
      const { data } = await axios.get('/api/trends/platforms')
      this.platforms = data
    },

    setSelectedPlatform(platform: string) {
      this.selectedPlatform = platform
    },
  },
})
