<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { getJsonStrict } from '../api/client'
import DataSkeleton from '../components/DataSkeleton.vue'

const rows = ref<any[]>([])
const loading = ref(true)
const error = ref('')
const labels: Record<string,string> = { READY: '统计完成', STALE: '待更新', PENDING: '尚未就绪', FAILED: '统计失败' }
async function load() {
  loading.value = true
  error.value = ''
  try {
    rows.value = await getJsonStrict<any[]>('/reports')
  } catch (failure) {
    error.value = failure instanceof Error ? failure.message : '覆盖统计暂时无法读取，请稍后重试。'
  } finally {
    loading.value = false
  }
}
onMounted(load)
function time(value: string | null) { return value ? new Date(value).toLocaleString() : '尚无成功统计' }
function note(row: any) {
  if (row.refresh_state === 'FAILED') return '后台统计失败，保留上次成功结果；系统稍后重试。'
  if (row.refresh_state === 'REFRESHING') return '后台正在更新，当前显示上次成功统计。'
  if (row.status === 'STALE') return '源报表已有更新，当前显示上次成功统计。'
  if (row.status === 'PENDING') return '首次覆盖统计尚未完成，行数和日期范围暂不可用。'
  return row.lineage
}
const reports = computed(() => [...rows.value].sort((a,b) => `${a.account}-${a.type}`.localeCompare(`${b.account}-${b.type}`)))
</script>
<template>
  <section class="page">
    <div class="page-head"><div><h1>报告管理</h1><p>查看后台核对的报表覆盖快照；源数据更新后会自动重新统计。</p></div><button class="btn" :disabled="loading" @click="load">刷新状态</button></div>
    <DataSkeleton v-if="loading" variant="cards" :rows="6" />
    <div v-else-if="error" role="alert" class="card panel"><p>{{error}}</p><button class="btn" @click="load">重新读取</button></div>
    <div v-else class="report-grid">
      <div v-for="r in reports" :key="r.table+':'+r.account_id" class="card report-card">
        <div><span class="eyebrow">{{r.account}}</span><h3>{{r.type}}</h3>
          <p>{{r.min_date && r.date ? `${r.min_date} ~ ${r.date}` : '暂无日期范围'}}</p>
          <p>{{r.rows == null ? '行数待统计' : `${Number(r.rows).toLocaleString()} 行`}} · {{ r.source }}</p>
          <p>上次成功统计：{{time(r.snapshot_at)}}</p><p>{{note(r)}}</p>
        </div>
        <span class="status-badge" :class="r.status === 'READY' ? 'normal' : 'needs_review'">{{labels[r.status] || r.status}}</span>
      </div>
    </div>
  </section>
</template>
