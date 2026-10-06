<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { getJson } from '../api/client'
import { NInput, NSelect } from 'naive-ui'
import DataSkeleton from '../components/DataSkeleton.vue'

type MappingRow = {
  brand: string
  productCode: string
  parentAsin: string
  operatorGroup: string
  status: string
}
type Bucket = { name: string; count: number }
type MappingData = {
  data_source: string
  rows: MappingRow[]
  summary: {
    total: number
    confirmed: number
    missingBusiness: number
    brands: number
    operatorGroups: number
    byBrand: Bucket[]
    byOperatorGroup: Bucket[]
    byStatus: Bucket[]
  }
  filters: { brands: string[]; operatorGroups: string[]; statuses: string[] }
  note: string
}

const fallback: MappingData = {
  data_source: 'offline',
  rows: [],
  summary: {
    total: 0, confirmed: 0, missingBusiness: 0, brands: 0, operatorGroups: 0,
    byBrand: [], byOperatorGroup: [], byStatus: [],
  },
  filters: { brands: [], operatorGroups: [], statuses: [] },
  note: '接口未连接',
}

const data = ref<MappingData>(fallback)
const loading = ref(true)
const search = ref('')
const brand = ref('')
const operatorGroup = ref('')
const status = ref('')

const load = async () => {
  loading.value = true
  try {
    data.value = await getJson<MappingData>('/product-mappings', fallback)
  } finally {
    loading.value = false
  }
}

const filtered = computed(() => {
  const q = search.value.trim().toLowerCase()
  return data.value.rows.filter(row => {
    if (brand.value && row.brand !== brand.value) return false
    if (operatorGroup.value && row.operatorGroup !== operatorGroup.value) return false
    if (status.value && row.status !== status.value) return false
    if (q && ![row.brand, row.productCode, row.parentAsin, row.operatorGroup, row.status]
      .some(value => (value || '').toLowerCase().includes(q))) return false
    return true
  })
})

const opt = (values: string[], all: string) => [
  { label: all, value: '' },
  ...values.map(value => ({ label: value, value })),
]
const brandOptions = computed(() => opt(data.value.filters.brands, '全部品牌'))
const operatorOptions = computed(() => opt(data.value.filters.operatorGroups, '全部运营组'))
const statusOptions = computed(() => opt(data.value.filters.statuses, '全部状态'))
const clearFilters = () => { search.value=''; brand.value=''; operatorGroup.value=''; status.value='' }

const statusLabel = (value:string) => value === 'confirmed_no_business' ? '已确认 · 缺业务报告' : value === 'confirmed' ? '已确认' : value

onMounted(load)
</script>

<template>
  <section class="page mapping-page">
    <div class="page-head mapping-page-head">
      <div>
        <h1>产品映射</h1>
        <p>正式主映射只保留 5 个字段：品牌、产品号、父 ASIN、运营组、状态。</p>
      </div>
      <span class="mapping-badge" :class="{ live: data.data_source !== 'offline' }">
        {{ data.data_source === 'offline' ? '接口未连接' : 'RDS 主映射' }}
      </span>
    </div>

    <DataSkeleton v-if="loading" variant="cards" :rows="8" />

    <div v-if="!loading" class="mapping-summary">
      <div class="mapping-stat"><span>映射总数</span><strong>{{ data.summary.total }}</strong></div>
      <div class="mapping-stat"><span>业务侧可用</span><strong>{{ data.summary.confirmed }}</strong></div>
      <div class="mapping-stat"><span>缺业务报告</span><strong>{{ data.summary.missingBusiness }}</strong></div>
      <div class="mapping-stat"><span>覆盖运营组</span><strong>{{ data.summary.operatorGroups }}</strong></div>
    </div>

    <div v-if="!loading" class="card mapping-filter">
      <NInput v-model:value="search" clearable placeholder="搜索产品号、父 ASIN、运营组" />
      <NSelect v-model:value="brand" :options="brandOptions" />
      <NSelect v-model:value="operatorGroup" :options="operatorOptions" />
      <NSelect v-model:value="status" :options="statusOptions" />
      <button class="btn" @click="clearFilters">清空筛选</button>
    </div>

    <div v-if="!loading" class="mapping-note"><strong>口径：</strong>{{ data.note }}</div>

    <div v-if="!loading" class="card panel mapping-table-card">
      <div class="mapping-table-head">
        <span>当前显示 {{ filtered.length }} / {{ data.summary.total }} 条</span>
      </div>
      <div class="table-wrap mapping-table-wrap">
        <table class="mapping-table">
          <thead>
            <tr>
              <th>品牌</th>
              <th>产品号</th>
              <th>父 ASIN</th>
              <th>运营组</th>
              <th>状态</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in filtered" :key="row.parentAsin">
              <td>{{ row.brand }}</td>
              <td><strong>{{ row.productCode }}</strong></td>
              <td class="asin-cell">{{ row.parentAsin }}</td>
              <td><strong>{{ row.operatorGroup }}</strong></td>
              <td>
                <span class="mapping-status" :class="{ active: row.status==='confirmed', missing: row.status==='confirmed_no_business' }">
                  {{ statusLabel(row.status) }}
                </span>
              </td>
            </tr>
            <tr v-if="!filtered.length"><td colspan="5" class="muted">没有符合当前筛选条件的映射。</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  </section>
</template>

<style scoped>
.mapping-page{min-width:0}.mapping-page-head{align-items:center}.mapping-badge{padding:4px 10px;border-radius:999px;background:#f2f4f7;color:#667085;font-size:12px}.mapping-badge.live{background:#ecf8f1;color:#287a4b}
.mapping-summary{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:14px 0}.mapping-stat{background:#fff;border:1px solid #e7eaf0;border-radius:10px;padding:14px 16px;display:flex;align-items:flex-end;justify-content:space-between}.mapping-stat span{font-size:13px;color:#6b7280}.mapping-stat strong{font-size:24px;color:#111827}
.mapping-filter{display:grid;grid-template-columns:minmax(230px,1.4fr) repeat(3,minmax(150px,.8fr)) auto;gap:10px;padding:12px;margin-bottom:10px;align-items:center}.mapping-note{font-size:13px;color:#596273;background:#f7f9fc;border:1px solid #e7eaf0;border-radius:8px;padding:9px 12px;margin-bottom:8px}
.mapping-table-card{min-width:0;overflow:hidden}.mapping-table-head{display:flex;justify-content:space-between;padding:12px 14px 0;font-size:13px;color:#6b7280}.mapping-table-wrap{overflow:auto;max-height:calc(100vh - 330px)}.mapping-table{min-width:760px}.mapping-table th{position:sticky;top:0;background:#f8fafc;z-index:2}.asin-cell{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px}
.mapping-status{display:inline-block;padding:3px 8px;border-radius:999px;background:#f1f3f7;color:#626b78;white-space:nowrap;font-size:12px}.mapping-status.active{background:#ecf8f1;color:#287a4b}.mapping-status.missing{background:#fff3e6;color:#a45f16}
@media(max-width:900px){.mapping-summary{grid-template-columns:repeat(2,minmax(0,1fr))}.mapping-filter{grid-template-columns:1fr 1fr}}@media(max-width:650px){.mapping-summary,.mapping-filter{grid-template-columns:1fr}}
</style>
