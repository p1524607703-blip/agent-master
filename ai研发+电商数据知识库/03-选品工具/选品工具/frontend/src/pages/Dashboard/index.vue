<template>
  <div class="dashboard">
    <!-- Background orbs -->
    <div class="bg-orbs">
      <div class="orb orb-1" />
      <div class="orb orb-2" />
      <div class="orb orb-3" />
    </div>

    <!-- Header -->
    <div class="page-header">
      <div>
        <h1 class="page-title">数据仪表盘</h1>
        <p class="page-sub">实时监控选品数据与趋势动态</p>
      </div>
      <div class="header-actions">
        <el-button type="primary" @click="refresh" :loading="loading">
          <el-icon><Refresh /></el-icon> 刷新
        </el-button>
      </div>
    </div>

    <!-- Stat cards -->
    <div class="stats-grid">
      <StatCard label="监控商品" :value="stats.total" icon="Box" color="#0891b2" :delta="8" />
      <StatCard label="今日推荐" :value="stats.recommended" icon="StarFilled" color="#10b981" :delta="12" />
      <StatCard label="观察中" :value="stats.watching" icon="View" color="#f59e0b" />
      <StatCard label="已淘汰" :value="stats.dropped" icon="CircleCloseFilled" color="#f43f5e" />
    </div>

    <!-- Main content -->
    <div class="content-grid">
      <!-- Trend chart -->
      <GlassCard class="chart-card">
        <template #header>
          <div class="card-title">趋势走势 <span class="badge">近30天</span></div>
        </template>
        <v-chart class="chart" :option="trendChartOption" autoresize />
      </GlassCard>

      <!-- Alerts -->
      <GlassCard class="alerts-card">
        <template #header>
          <div class="card-title">实时预警 <span class="badge badge--red">{{ alertCount }}</span></div>
        </template>
        <div class="alert-list">
          <div v-for="alert in recentAlerts" :key="alert.id" class="alert-item" :class="`alert-item--${alert.severity}`">
            <div class="alert-icon">{{ severityIcon(alert.severity) }}</div>
            <div class="alert-content">
              <div class="alert-msg">{{ alert.message }}</div>
              <div class="alert-time">{{ formatTime(alert.triggeredAt) }}</div>
            </div>
          </div>
          <div v-if="!recentAlerts.length" class="empty-state">暂无预警</div>
        </div>
      </GlassCard>
    </div>

    <!-- Top products table -->
    <GlassCard class="table-card">
      <template #header>
        <div class="card-title">热门商品 TOP 10</div>
      </template>
      <el-table :data="topProducts" style="background: transparent" class="glass-table">
        <el-table-column prop="name" label="商品名称" min-width="200" />
        <el-table-column prop="category" label="分类" width="120" />
        <el-table-column prop="score" label="评分" width="100">
          <template #default="{ row }">
            <el-progress :percentage="row.score" :stroke-width="6" :color="scoreColor(row.score)" />
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
      </el-table>
    </GlassCard>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'
import GlassCard from '@/components/GlassCard.vue'
import StatCard from '@/components/StatCard.vue'

const loading = ref(false)
const stats = ref({ total: 0, recommended: 0, watching: 0, dropped: 0 })
const topProducts = ref<any[]>([])
const recentAlerts = ref<any[]>([])
const alertCount = computed(() => recentAlerts.value.filter(a => !a.isRead).length)

const trendChartOption = computed(() => ({
  tooltip: { trigger: 'axis' },
  grid: { left: 20, right: 20, top: 20, bottom: 20, containLabel: true },
  xAxis: { type: 'category', data: ['1月', '2月', '3月', '4月', '5月', '6月'], axisLine: { lineStyle: { color: '#94a3b8' } } },
  yAxis: { type: 'value', axisLine: { show: false }, splitLine: { lineStyle: { color: 'rgba(148,163,184,0.2)' } } },
  series: [
    { name: 'TikTok', type: 'line', smooth: true, data: [120, 180, 150, 220, 280, 350], itemStyle: { color: '#0891b2' }, areaStyle: { color: 'rgba(8,145,178,0.08)' } },
    { name: 'Reddit', type: 'line', smooth: true, data: [80, 95, 110, 130, 160, 200], itemStyle: { color: '#06b6d4' }, areaStyle: { color: 'rgba(6,182,212,0.06)' } },
  ],
}))

async function refresh() {
  loading.value = true
  try {
    const [statsRes, productsRes, alertsRes] = await Promise.all([
      axios.get('/api/products/stats'),
      axios.get('/api/products?pageSize=10'),
      axios.get('/api/alerts?unreadOnly=false'),
    ])
    stats.value = statsRes.data
    topProducts.value = productsRes.data.items || []
    recentAlerts.value = (alertsRes.data || []).slice(0, 6)
  } catch {
    // Use mock data when API not available
    stats.value = { total: 248, recommended: 32, watching: 156, dropped: 60 }
  } finally {
    loading.value = false
  }
}

function severityIcon(s: string) {
  return { critical: '🔴', warning: '🟡', info: '🔵' }[s] || '⚪'
}

function formatTime(t: string) {
  return t ? new Date(t).toLocaleString('zh-CN') : ''
}

function scoreColor(s: number) {
  if (s >= 80) return '#10b981'
  if (s >= 60) return '#f59e0b'
  return '#f43f5e'
}

function statusType(s: string) {
  return { recommended: 'success', watching: 'warning', dropped: 'danger' }[s] || 'info'
}

function statusLabel(s: string) {
  return { recommended: '已推荐', watching: '观察中', dropped: '已淘汰' }[s] || s
}

onMounted(refresh)
</script>

<style scoped>
.dashboard { position: relative; z-index: 1; }

.bg-orbs { position: fixed; inset: 0; pointer-events: none; z-index: 0; overflow: hidden; }
.orb { position: absolute; border-radius: 50%; filter: blur(80px); animation: float 8s ease-in-out infinite; }
.orb-1 { width: 500px; height: 500px; background: radial-gradient(circle, rgba(6,182,212,0.15) 0%, transparent 70%); top: -100px; right: 10%; }
.orb-2 { width: 350px; height: 350px; background: radial-gradient(circle, rgba(8,145,178,0.10) 0%, transparent 70%); bottom: -80px; left: 15%; animation-delay: 3s; }
.orb-3 { width: 250px; height: 250px; background: radial-gradient(circle, rgba(34,211,238,0.08) 0%, transparent 70%); top: 45%; right: 40%; animation-delay: 5s; }
@keyframes float { 0%,100% { transform: translateY(0); } 50% { transform: translateY(-20px); } }

.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 24px; }
.page-title { font-size: 24px; font-weight: 700; color: #0c2340; }
.page-sub { font-size: 14px; color: #3d6b8a; margin-top: 4px; }

.stats-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px; }

.content-grid { display: grid; grid-template-columns: 2fr 1fr; gap: 20px; margin-bottom: 20px; }

.chart-card, .table-card { min-height: 280px; }
.chart { height: 240px; width: 100%; }

.card-title { font-size: 15px; font-weight: 600; color: #0c2340; display: flex; align-items: center; gap: 8px; }
.badge { background: rgba(8,145,178,0.12); color: #0891b2; font-size: 11px; padding: 2px 8px; border-radius: 20px; font-weight: 500; }
.badge--red { background: rgba(244,63,94,0.12); color: #f43f5e; }

.alert-list { display: flex; flex-direction: column; gap: 8px; }
.alert-item { display: flex; gap: 10px; padding: 10px; border-radius: 10px; }
.alert-item--critical { background: rgba(244,63,94,0.08); }
.alert-item--warning { background: rgba(245,158,11,0.08); }
.alert-item--info { background: rgba(8,145,178,0.06); }
.alert-msg { font-size: 13px; color: #0c2340; }
.alert-time { font-size: 11px; color: #94a3b8; margin-top: 2px; }
.empty-state { text-align: center; color: #94a3b8; padding: 20px; font-size: 13px; }

:deep(.el-table) { background: transparent !important; --el-table-bg-color: transparent; --el-table-header-bg-color: transparent; }
:deep(.el-table tr) { background: transparent !important; }
:deep(.el-table th) { background: rgba(8,145,178,0.04) !important; }
</style>
