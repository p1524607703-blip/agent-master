<template>
  <div class="trend-page">
    <!-- Aurora background -->
    <div class="aurora-bg">
      <div class="aurora aurora-1" />
      <div class="aurora aurora-2" />
      <div class="aurora aurora-3" />
    </div>

    <div class="page-header">
      <div>
        <h1 class="page-title">趋势发现</h1>
        <p class="page-sub">多平台实时趋势监控</p>
      </div>
      <div class="platform-tabs">
        <button
          v-for="p in platforms"
          :key="p.key"
          class="platform-tab"
          :class="{ active: selectedPlatform === p.key }"
          @click="selectPlatform(p.key)"
        >
          <span>{{ p.icon }}</span> {{ p.label }}
        </button>
      </div>
    </div>

    <!-- Platform summary cards -->
    <div class="platform-grid">
      <GlassCard
        v-for="p in platformSummary"
        :key="p.platform"
        :hoverable="true"
        class="platform-card"
        :class="{ 'platform-card--active': selectedPlatform === p.platform }"
        @click="selectPlatform(p.platform)"
      >
        <div class="platform-card-inner">
          <div class="platform-icon">{{ platformIcon(p.platform) }}</div>
          <div>
            <div class="platform-name">{{ platformLabel(p.platform) }}</div>
            <div class="platform-count">{{ p.count.toLocaleString() }} 条数据</div>
          </div>
          <div class="platform-pulse" :class="`pulse--${p.platform}`" />
        </div>
      </GlassCard>
    </div>

    <!-- Trend list + detail -->
    <div class="trend-main">
      <GlassCard class="trend-list-card">
        <template #header>
          <div class="card-title">
            {{ selectedPlatform ? platformLabel(selectedPlatform) : '全部' }} 趋势热点
            <el-button size="small" @click="fetchTrends" :loading="loading">刷新</el-button>
          </div>
        </template>
        <div class="trend-list" v-loading="loading">
          <div
            v-for="(item, idx) in trends"
            :key="item.id"
            class="trend-item"
            :class="{ 'trend-item--selected': selectedTrend?.id === item.id }"
            @click="selectedTrend = item"
          >
            <div class="trend-rank" :class="idx < 3 ? `rank--top${idx + 1}` : ''">{{ idx + 1 }}</div>
            <div class="trend-info">
              <div class="trend-name">{{ item.product?.name || '未知商品' }}</div>
              <div class="trend-meta">{{ platformLabel(item.platform) }} · {{ item.metric }}</div>
            </div>
            <div class="trend-delta" :class="item.deltaPercent >= 0 ? 'delta--up' : 'delta--down'">
              {{ item.deltaPercent >= 0 ? '↑' : '↓' }} {{ Math.abs(item.deltaPercent).toFixed(1) }}%
            </div>
          </div>
          <div v-if="!trends.length && !loading" class="empty-state">暂无趋势数据</div>
        </div>
      </GlassCard>

      <GlassCard class="trend-detail-card" v-if="selectedTrend">
        <template #header>
          <div class="card-title">{{ selectedTrend.product?.name || '商品详情' }}</div>
        </template>
        <div class="detail-content">
          <div class="detail-badge">{{ platformLabel(selectedTrend.platform) }}</div>
          <div class="detail-metric">
            <span class="metric-label">{{ selectedTrend.metric }}</span>
            <span class="metric-value">{{ selectedTrend.value.toLocaleString() }}</span>
          </div>
          <div class="detail-delta" :class="selectedTrend.deltaPercent >= 0 ? 'delta--up' : 'delta--down'">
            较上期 {{ selectedTrend.deltaPercent >= 0 ? '+' : '' }}{{ selectedTrend.deltaPercent.toFixed(1) }}%
          </div>
          <!-- Aurora orb effect -->
          <div class="aurora-orb" />
          <v-chart class="detail-chart" :option="detailChartOption" autoresize />
        </div>
      </GlassCard>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'
import GlassCard from '@/components/GlassCard.vue'

const loading = ref(false)
const selectedPlatform = ref('')
const selectedTrend = ref<any>(null)
const trends = ref<any[]>([])
const platformSummary = ref<any[]>([
  { platform: 'tiktok', count: 0 },
  { platform: 'reddit', count: 0 },
  { platform: 'google', count: 0 },
  { platform: 'facebook', count: 0 },
])

const platforms = [
  { key: '', label: '全部', icon: '🌐' },
  { key: 'tiktok', label: 'TikTok', icon: '🎵' },
  { key: 'reddit', label: 'Reddit', icon: '👽' },
  { key: 'google', label: 'Google', icon: '🔍' },
  { key: 'facebook', label: 'Facebook', icon: '👥' },
]

function platformLabel(p: string) {
  return { tiktok: 'TikTok', reddit: 'Reddit', google: 'Google', facebook: 'Facebook' }[p] || p
}

function platformIcon(p: string) {
  return { tiktok: '🎵', reddit: '👽', google: '🔍', facebook: '👥' }[p] || '📊'
}

function selectPlatform(p: string) {
  selectedPlatform.value = p
  fetchTrends()
}

const detailChartOption = computed(() => ({
  tooltip: { trigger: 'axis' },
  grid: { left: 10, right: 10, top: 10, bottom: 10, containLabel: true },
  xAxis: { type: 'category', data: ['周一', '周二', '周三', '周四', '周五', '周六', '周日'], show: false },
  yAxis: { type: 'value', show: false },
  series: [{
    type: 'line', smooth: true, symbol: 'none',
    data: [40, 55, 48, 70, 65, 90, selectedTrend.value?.value ?? 100],
    lineStyle: { color: '#0891b2', width: 2 },
    areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: 'rgba(8,145,178,0.25)' }, { offset: 1, color: 'transparent' }] } },
  }],
}))

async function fetchTrends() {
  loading.value = true
  try {
    const { data } = await axios.get('/api/trends', {
      params: { platform: selectedPlatform.value || undefined, limit: 20 },
    })
    trends.value = data
  } catch {
    // mock
    trends.value = Array.from({ length: 8 }, (_, i) => ({
      id: `mock-${i}`,
      platform: platforms[1 + (i % 4)].key,
      metric: 'views',
      value: Math.floor(10000 + Math.random() * 90000),
      deltaPercent: (Math.random() - 0.3) * 40,
      product: { name: `示例商品 ${i + 1}` },
    }))
  } finally {
    loading.value = false
  }
}

async function fetchPlatformSummary() {
  try {
    const { data } = await axios.get('/api/trends/platforms')
    platformSummary.value = data
  } catch {
    platformSummary.value = [
      { platform: 'tiktok', count: 1842 },
      { platform: 'reddit', count: 967 },
      { platform: 'google', count: 2341 },
      { platform: 'facebook', count: 754 },
    ]
  }
}

onMounted(() => {
  fetchPlatformSummary()
  fetchTrends()
})
</script>

<style scoped>
.trend-page { position: relative; z-index: 1; }

.aurora-bg { position: fixed; inset: 0; pointer-events: none; z-index: 0; overflow: hidden; }
.aurora { position: absolute; border-radius: 50%; filter: blur(100px); animation: drift 12s ease-in-out infinite; }
.aurora-1 { width: 600px; height: 300px; background: linear-gradient(135deg, rgba(6,182,212,0.15), transparent); top: -50px; left: 20%; }
.aurora-2 { width: 500px; height: 200px; background: linear-gradient(135deg, rgba(8,145,178,0.10), transparent); bottom: 10%; right: 10%; animation-delay: 4s; }
.aurora-3 { width: 400px; height: 250px; background: linear-gradient(135deg, rgba(34,211,238,0.08), transparent); top: 40%; left: -5%; animation-delay: 8s; }
@keyframes drift { 0%,100% { transform: translate(0, 0) rotate(0deg); } 33% { transform: translate(30px, -20px) rotate(5deg); } 66% { transform: translate(-20px, 15px) rotate(-3deg); } }

.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px; }
.page-title { font-size: 24px; font-weight: 700; color: #0c2340; }
.page-sub { font-size: 14px; color: #3d6b8a; margin-top: 4px; }

.platform-tabs { display: flex; gap: 8px; flex-wrap: wrap; }
.platform-tab { padding: 7px 14px; border-radius: 20px; border: 1px solid rgba(8,145,178,0.2); background: rgba(255,255,255,0.4); cursor: pointer; font-size: 13px; color: #475569; transition: all 0.2s; }
.platform-tab:hover, .platform-tab.active { background: linear-gradient(135deg, rgba(8,145,178,0.15), rgba(6,182,212,0.1)); color: #0891b2; border-color: #0891b2; }

.platform-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 20px; }
.platform-card { cursor: pointer; }
.platform-card--active { border-color: #0891b2 !important; }
.platform-card-inner { display: flex; align-items: center; gap: 12px; position: relative; }
.platform-icon { font-size: 28px; }
.platform-name { font-weight: 600; color: #0c2340; font-size: 14px; }
.platform-count { font-size: 12px; color: #64748b; }
.platform-pulse { position: absolute; top: 0; right: 0; width: 8px; height: 8px; border-radius: 50%; background: #22c55e; animation: pulse 2s infinite; }
@keyframes pulse { 0%,100% { opacity: 1; transform: scale(1); } 50% { opacity: 0.5; transform: scale(1.3); } }

.trend-main { display: grid; grid-template-columns: 1fr 340px; gap: 20px; }
.trend-list-card { min-height: 400px; }
.trend-list { max-height: 480px; overflow-y: auto; }
.trend-item { display: flex; align-items: center; gap: 12px; padding: 10px 12px; border-radius: 10px; cursor: pointer; transition: background 0.15s; }
.trend-item:hover, .trend-item--selected { background: rgba(8,145,178,0.06); }
.trend-rank { width: 28px; height: 28px; border-radius: 8px; background: rgba(8,145,178,0.1); display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 13px; color: #0891b2; flex-shrink: 0; }
.rank--top1 { background: linear-gradient(135deg, #f59e0b, #fbbf24); color: white; }
.rank--top2 { background: linear-gradient(135deg, #94a3b8, #cbd5e1); color: white; }
.rank--top3 { background: linear-gradient(135deg, #f97316, #fb923c); color: white; }
.trend-name { font-weight: 500; font-size: 14px; color: #0c2340; }
.trend-meta { font-size: 12px; color: #64748b; margin-top: 2px; }
.trend-delta { margin-left: auto; font-size: 13px; font-weight: 600; padding: 3px 8px; border-radius: 20px; }
.delta--up { color: #16a34a; background: rgba(34,197,94,0.12); }
.delta--down { color: #dc2626; background: rgba(239,68,68,0.12); }

.detail-content { position: relative; }
.detail-badge { display: inline-block; background: rgba(8,145,178,0.12); color: #0891b2; font-size: 12px; padding: 3px 10px; border-radius: 20px; margin-bottom: 12px; }
.detail-metric { display: flex; flex-direction: column; gap: 4px; }
.metric-label { font-size: 13px; color: #64748b; }
.metric-value { font-size: 36px; font-weight: 800; background: linear-gradient(135deg, #0891b2, #22d3ee); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
.detail-delta { font-size: 14px; font-weight: 600; margin: 8px 0; }
.aurora-orb { position: absolute; top: 20px; right: 20px; width: 80px; height: 80px; border-radius: 50%; background: radial-gradient(circle, rgba(6,182,212,0.3), transparent 70%); filter: blur(20px); animation: pulse 3s ease-in-out infinite; }
.detail-chart { height: 120px; width: 100%; margin-top: 16px; }

.card-title { font-size: 15px; font-weight: 600; color: #0c2340; display: flex; align-items: center; gap: 8px; }
.empty-state { text-align: center; color: #94a3b8; padding: 40px; font-size: 13px; }
</style>
