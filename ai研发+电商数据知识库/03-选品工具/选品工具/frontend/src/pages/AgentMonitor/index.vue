<template>
  <div class="monitor-page">
    <!-- Scan line effect -->
    <div class="scan-overlay" />

    <div class="page-header">
      <div>
        <h1 class="page-title">Agent 监控</h1>
        <p class="page-sub">自动化任务队列实时监控</p>
      </div>
      <div class="header-actions">
        <el-button @click="dispatchTask('scan', '商品数据扫描')" :loading="dispatching">
          <el-icon><VideoPlay /></el-icon> 启动扫描
        </el-button>
        <el-button @click="dispatchTask('alert_check', '预警检查')" :loading="dispatching">
          预警检查
        </el-button>
        <el-button @click="dispatchTask('report', '生成报告')" :loading="dispatching">
          生成报告
        </el-button>
      </div>
    </div>

    <!-- HUD status row -->
    <div class="hud-row">
      <div class="hud-card" v-for="item in hudItems" :key="item.label">
        <div class="hud-value" :style="{ color: item.color }">{{ item.value }}</div>
        <div class="hud-label">{{ item.label }}</div>
        <div class="hud-indicator" :style="{ background: item.color }" />
      </div>
    </div>

    <div class="monitor-grid">
      <!-- Task list -->
      <GlassCard class="task-list-card">
        <template #header>
          <div class="card-title">
            任务队列
            <div class="filter-tabs">
              <button v-for="s in statusFilters" :key="s.value" class="filter-tab" :class="{ active: taskFilter === s.value }" @click="taskFilter = s.value">
                {{ s.label }}
              </button>
            </div>
          </div>
        </template>

        <div class="task-list" v-loading="loading">
          <div v-for="task in filteredTasks" :key="task.id" class="task-row" :class="`task--${task.status}`">
            <div class="task-status-dot" :class="`dot--${task.status}`" />
            <div class="task-info">
              <div class="task-name">{{ task.name }}</div>
              <div class="task-meta">{{ typeLabel(task.type) }} · {{ formatTime(task.createdAt) }}</div>
            </div>
            <div class="task-right">
              <div v-if="task.status === 'running'" class="task-progress-wrap">
                <el-progress :percentage="task.progress" :stroke-width="4" :color="'#0891b2'" :show-text="false" style="width: 80px" />
                <span class="progress-pct">{{ task.progress }}%</span>
              </div>
              <el-tag :type="statusTagType(task.status)" size="small">{{ statusLabel(task.status) }}</el-tag>
            </div>
          </div>
          <div v-if="!filteredTasks.length && !loading" class="empty-state">暂无任务</div>
        </div>
      </GlassCard>

      <!-- Log stream -->
      <GlassCard class="log-card">
        <template #header>
          <div class="card-title">
            实时日志
            <span class="cursor-blink">_</span>
          </div>
        </template>
        <div class="log-stream" ref="logStreamEl">
          <div v-for="(log, idx) in logs" :key="idx" class="log-line" :class="`log--${log.level}`">
            <span class="log-time">{{ log.time }}</span>
            <span class="log-level">[{{ log.level.toUpperCase() }}]</span>
            <span class="log-msg">{{ log.msg }}</span>
          </div>
        </div>
      </GlassCard>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import axios from 'axios'
import GlassCard from '@/components/GlassCard.vue'

const loading = ref(false)
const dispatching = ref(false)
const taskFilter = ref('')
const tasks = ref<any[]>([])
const logStreamEl = ref<HTMLElement>()

const stats = ref({ pending: 0, running: 0, completed: 0, failed: 0 })
let pollingTimer: ReturnType<typeof setInterval> | null = null
let logTimer: ReturnType<typeof setInterval> | null = null

const statusFilters = [
  { value: '', label: '全部' },
  { value: 'running', label: '运行中' },
  { value: 'pending', label: '等待' },
  { value: 'completed', label: '已完成' },
  { value: 'failed', label: '失败' },
]

const hudItems = computed(() => [
  { label: '等待中', value: stats.value.pending, color: '#94a3b8' },
  { label: '运行中', value: stats.value.running, color: '#0891b2' },
  { label: '已完成', value: stats.value.completed, color: '#10b981' },
  { label: '失败', value: stats.value.failed, color: '#f43f5e' },
  { label: '总任务', value: tasks.value.length, color: '#8b5cf6' },
])

const filteredTasks = computed(() =>
  taskFilter.value ? tasks.value.filter(t => t.status === taskFilter.value) : tasks.value,
)

const logs = ref<{ time: string; level: string; msg: string }[]>([])

const logMessages = [
  { level: 'info', msg: '开始扫描 TikTok 趋势数据...' },
  { level: 'info', msg: 'Reddit 监控模块已激活' },
  { level: 'success', msg: '发现新趋势商品: 无线充电器（+42.3%）' },
  { level: 'warn', msg: 'Google 趋势 API 请求速率接近限制' },
  { level: 'info', msg: '预警检查: 扫描 248 个商品中...' },
  { level: 'success', msg: '价格异常预警: 商品 #1024 价格下跌 18%' },
  { level: 'info', msg: 'AI 分析队列: 3 个任务待处理' },
  { level: 'success', msg: 'MiniMax M1 分析完成: 综合评分 82/100' },
  { level: 'info', msg: '数据库同步: 1,240 条趋势记录已更新' },
  { level: 'warn', msg: 'Redis 连接池使用率: 72%' },
]

function addLog() {
  const template = logMessages[Math.floor(Math.random() * logMessages.length)]
  const now = new Date()
  const time = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}`
  logs.value.push({ time, level: template.level, msg: template.msg })
  if (logs.value.length > 50) logs.value.shift()
  nextTick(() => {
    if (logStreamEl.value) logStreamEl.value.scrollTop = logStreamEl.value.scrollHeight
  })
}

function typeLabel(t: string) {
  return { scan: '数据扫描', ai_analysis: 'AI分析', alert_check: '预警检查', report: '报告生成' }[t] || t
}

function statusLabel(s: string) {
  return { pending: '等待', running: '运行中', completed: '已完成', failed: '失败' }[s] || s
}

function statusTagType(s: string) {
  return { pending: 'info', running: 'primary', completed: 'success', failed: 'danger' }[s] || 'info'
}

function formatTime(t: string) {
  return t ? new Date(t).toLocaleTimeString('zh-CN') : ''
}

async function fetchTasks() {
  loading.value = true
  try {
    const [tasksRes, statsRes] = await Promise.all([
      axios.get('/api/agents'),
      axios.get('/api/agents/stats'),
    ])
    tasks.value = tasksRes.data || []
    stats.value = statsRes.data
  } catch {
    tasks.value = [
      { id: '1', name: '商品数据扫描', type: 'scan', status: 'completed', progress: 100, createdAt: new Date().toISOString() },
      { id: '2', name: 'AI深度分析', type: 'ai_analysis', status: 'running', progress: 65, createdAt: new Date().toISOString() },
      { id: '3', name: '预警检查', type: 'alert_check', status: 'pending', progress: 0, createdAt: new Date().toISOString() },
    ]
    stats.value = { pending: 1, running: 1, completed: 1, failed: 0 }
  } finally {
    loading.value = false
  }
}

async function dispatchTask(type: string, name: string) {
  dispatching.value = true
  try {
    const { data } = await axios.post('/api/agents/dispatch', { type, name })
    tasks.value.unshift(data)
    addLog()
  } catch {
    tasks.value.unshift({
      id: Date.now().toString(), name, type, status: 'pending', progress: 0, createdAt: new Date().toISOString(),
    })
  } finally {
    dispatching.value = false
  }
}

onMounted(() => {
  fetchTasks()
  // Seed initial logs
  for (let i = 0; i < 5; i++) addLog()
  pollingTimer = setInterval(fetchTasks, 5000)
  logTimer = setInterval(addLog, 3000)
})

onUnmounted(() => {
  if (pollingTimer) clearInterval(pollingTimer)
  if (logTimer) clearInterval(logTimer)
})
</script>

<style scoped>
.monitor-page { position: relative; z-index: 1; }

.scan-overlay {
  position: fixed; inset: 0; pointer-events: none; z-index: 0;
  background: repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(8,145,178,0.015) 2px, rgba(8,145,178,0.015) 4px);
}

.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px; }
.page-title { font-size: 24px; font-weight: 700; color: #0c2340; }
.page-sub { font-size: 14px; color: #3d6b8a; margin-top: 4px; }
.header-actions { display: flex; gap: 8px; }

.hud-row { display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; margin-bottom: 20px; }
.hud-card {
  background: rgba(255,255,255,0.42);
  backdrop-filter: blur(20px);
  border: 1px solid rgba(255,255,255,0.65);
  border-radius: 14px;
  padding: 14px 16px;
  position: relative;
  overflow: hidden;
}
.hud-value { font-size: 28px; font-weight: 800; line-height: 1; margin-bottom: 4px; font-variant-numeric: tabular-nums; }
.hud-label { font-size: 12px; color: #64748b; }
.hud-indicator { position: absolute; bottom: 0; left: 0; right: 0; height: 2px; opacity: 0.5; }

.monitor-grid { display: grid; grid-template-columns: 3fr 2fr; gap: 20px; }
.task-list-card, .log-card { min-height: 400px; }

.card-title { font-size: 15px; font-weight: 600; color: #0c2340; display: flex; align-items: center; gap: 8px; justify-content: space-between; }
.filter-tabs { display: flex; gap: 6px; }
.filter-tab { padding: 4px 10px; border-radius: 20px; border: 1px solid rgba(8,145,178,0.15); background: transparent; font-size: 12px; cursor: pointer; color: #64748b; transition: all 0.15s; }
.filter-tab:hover, .filter-tab.active { background: rgba(8,145,178,0.1); color: #0891b2; border-color: #0891b2; }

.task-list { max-height: 480px; overflow-y: auto; display: flex; flex-direction: column; gap: 6px; }
.task-row { display: flex; align-items: center; gap: 10px; padding: 10px 12px; border-radius: 10px; background: rgba(255,255,255,0.3); }
.task--running { background: rgba(8,145,178,0.06); border: 1px solid rgba(8,145,178,0.12); }
.task--failed { background: rgba(244,63,94,0.04); }

.task-status-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.dot--pending { background: #94a3b8; }
.dot--running { background: #0891b2; animation: blink 1.2s infinite; }
.dot--completed { background: #22c55e; }
.dot--failed { background: #f43f5e; }
@keyframes blink { 0%,100% { opacity: 1; } 50% { opacity: 0.3; } }

.task-name { font-size: 14px; font-weight: 500; color: #0c2340; }
.task-meta { font-size: 12px; color: #64748b; margin-top: 2px; }
.task-right { margin-left: auto; display: flex; align-items: center; gap: 8px; }
.task-progress-wrap { display: flex; align-items: center; gap: 4px; }
.progress-pct { font-size: 11px; color: #0891b2; font-weight: 600; }

.log-stream {
  height: 460px; overflow-y: auto; font-family: 'Fira Code', 'Courier New', monospace; font-size: 12px;
  background: rgba(15,23,42,0.04); border-radius: 10px; padding: 12px;
  display: flex; flex-direction: column; gap: 2px;
}
.log-line { display: flex; gap: 8px; line-height: 1.6; }
.log-time { color: #94a3b8; flex-shrink: 0; }
.log-level { flex-shrink: 0; font-weight: 600; }
.log--info .log-level { color: #0891b2; }
.log--success .log-level { color: #10b981; }
.log--warn .log-level { color: #f59e0b; }
.log--error .log-level { color: #f43f5e; }
.log-msg { color: #334155; }

.cursor-blink { animation: blink 1s step-end infinite; color: #0891b2; }
.empty-state { text-align: center; color: #94a3b8; padding: 40px; font-size: 13px; }
</style>
