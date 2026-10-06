<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { getJson } from '../api/client'
import StatusBadge from '../components/StatusBadge.vue'
import DataSkeleton from '../components/DataSkeleton.vue'

const rows = ref<any[]>([])
const loading = ref(true)
onMounted(async () => {
  loading.value = true
  try {
    rows.value = await getJson('/reports', [])
  } finally {
    loading.value = false
  }
})
const reports = computed(() => [...rows.value].sort((a,b) => `${a.account}-${a.type}`.localeCompare(`${b.account}-${b.type}`)))
</script>
<template>
  <section class="page">
    <div class="page-head"><div><h1>报告管理</h1><p>直接查看 RDS 当前已覆盖的数据源、账户、日期范围和行数。</p></div></div>
    <DataSkeleton v-if="loading" variant="cards" :rows="6" />
    <div v-else class="report-grid">
      <div v-for="r in reports" :key="r.account_id+r.type" class="card report-card">
        <div><span class="eyebrow">{{r.account}}</span><h3>{{r.type}}</h3><p>{{r.min_date}} ~ {{r.date}}</p><p>{{ Number(r.rows || 0).toLocaleString() }} 行 · {{ r.source }}</p></div>
        <StatusBadge :status="r.status"/>
      </div>
    </div>
  </section>
</template>
