<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getJson } from '../api/client'
import { NButton, NDatePicker, NSelect } from 'naive-ui'
import DataSkeleton from '../components/DataSkeleton.vue'

type Period = 'daily'|'weekly'|'monthly'
type PeriodOption = { value:string; label:string; start?:string; end?:string }
type PeriodData = { daily:PeriodOption[]; weekly:PeriodOption[]; monthly:PeriodOption[]; latestDate?:string; weekRule?:string; note?:string }

const route = useRoute()
const router = useRouter()
const operatorAliases: Record<string,string> = {
  AJ:'爱菊', DD:'丹丹', LB:'丽斌', LW:'林文', XH:'鑫华',
  XM:'雪敏', YS:'雨珊', YT:'雅婷', ZF:'珍凤', ZJ:'子娟',
}
const operatorName = computed(() => {
  const raw=String(route.params.operator || '子娟').trim()
  return operatorAliases[raw.toUpperCase().slice(0,2)] || raw
})
const operatorOptions = ['爱菊','丹丹','丽斌','林文','鑫华','雪敏','雨珊','雅婷','珍凤','子娟']
const operatorSelectOptions = operatorOptions.map(value => ({ label:value, value }))
const adTypes = ['SP', 'SB', 'SD', 'STV'] as const
const selectedDate = ref(String(route.query.date || ''))
const period = ref<Period>(['weekly','monthly'].includes(String(route.query.period)) ? route.query.period as Period : 'daily')
const periods = ref<PeriodData>({ daily:[],weekly:[],monthly:[] })
const detail = ref<any>({ operator:operatorName.value, products:[], summary:{}, account_split:false })
const loading = ref(false)
let requestSeq = 0

const reportRangeOptions = [
  { label:'每日', value:'daily' },
  { label:'每周', value:'weekly' },
  { label:'每月', value:'monthly' },
]
const currentRangeOptions = computed(() => periods.value[period.value] || [])
const rangeLabel = computed(() => period.value==='weekly' ? '选择周' : period.value==='monthly' ? '选择月' : '选择日期')
const dailyDateSet = computed(() => new Set((periods.value.daily || []).map(x => x.value)))
const dateKey = (ts:number) => {
  const d=new Date(ts)
  const y=d.getFullYear()
  const m=String(d.getMonth()+1).padStart(2,'0')
  const day=String(d.getDate()).padStart(2,'0')
  return `${y}-${m}-${day}`
}
const isDailyDateDisabled = (ts:number) => !dailyDateSet.value.has(dateKey(ts))

const normalizeSelection = () => {
  const opts=currentRangeOptions.value
  if (!opts.length) return
  const raw=selectedDate.value
  if (opts.some(x=>x.value===raw)) return
  if (raw) {
    const containing=opts.find(x=>x.start && x.end && raw>=x.start && raw<=x.end)
    if (containing) { selectedDate.value=containing.value; return }
  }
  selectedDate.value=opts[0].value
}

const loadPeriods = async () => {
  periods.value = await getJson<PeriodData>('/operator-periods', { daily:[],weekly:[],monthly:[] })
  normalizeSelection()
}

const syncControlsFromRoute = () => {
  const routePeriod = String(route.query.period || '')
  period.value = ['weekly','monthly'].includes(routePeriod) ? routePeriod as Period : 'daily'
  selectedDate.value = String(route.query.date || '')
}

const load = async () => {
  const seq = ++requestSeq
  const targetOperator = operatorName.value
  loading.value = true
  try {
    if (!periods.value.daily.length) await loadPeriods()
    if (seq !== requestSeq) return

    normalizeSelection()
    const targetPeriod = period.value
    const targetDate = selectedDate.value
    const params = new URLSearchParams({ period:targetPeriod })
    if (targetDate) params.set('date', targetDate)

    const result = await getJson(
      `/operators/${encodeURIComponent(targetOperator)}?${params.toString()}`,
      { operator:targetOperator, products:[], summary:{}, account_split:false, period:targetPeriod } as any,
    )
    if (seq !== requestSeq || operatorName.value !== targetOperator) return

    detail.value = result
    if (!selectedDate.value && result.data_date) selectedDate.value = result.data_date

    const canonicalDate = selectedDate.value
    const currentOperator = operatorName.value
    const currentPeriod = period.value
    const routeOperator = String(route.params.operator || '')
    const routePeriod = String(route.query.period || 'daily')
    const routeDate = String(route.query.date || '')
    if (
      currentOperator === targetOperator &&
      (routeOperator !== currentOperator || routePeriod !== currentPeriod || routeDate !== canonicalDate)
    ) {
      await router.replace({
        path:`/operators/${encodeURIComponent(currentOperator)}`,
        query:{ period:currentPeriod, ...(canonicalDate ? { date:canonicalDate } : {}) },
      })
    }
  } finally {
    if (seq === requestSeq) loading.value = false
  }
}

watch(
  () => [String(route.params.operator || ''), String(route.query.period || ''), String(route.query.date || '')],
  async () => {
    syncControlsFromRoute()
    await load()
  },
  { immediate:true },
)

const products = computed<any[]>(() => detail.value.products || [])

const money = (v: any) => v == null ? '—' : `$${Number(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
const num = (v: any) => v == null ? '—' : Number(v).toLocaleString(undefined, { maximumFractionDigits: 2 })
const ratio = (v: any, suffix = '') => v == null ? '—' : `${Number(v).toFixed(2)}${suffix}`
const typeValue = (product: any, field: 'adTypeSpend' | 'adTypeOrders', type: string) => product?.[field]?.[type] ?? null

const typeTotal = (field: 'adTypeSpend' | 'adTypeOrders', type: string) => {
  const values = products.value.map(p => p?.[field]?.[type]).filter((v: any) => v != null)
  if (!values.length) return null
  return values.reduce((sum: number, v: any) => sum + Number(v || 0), 0)
}

const onOperatorChange = async (name:string) => {
  if (!name || name === operatorName.value) return
  // Show the detail skeleton immediately instead of leaving stale operator data visible
  loading.value = true
  await router.push({
    path:`/operators/${encodeURIComponent(name)}`,
    query:{ period:period.value, ...(selectedDate.value ? { date:selectedDate.value } : {}) },
  })
}
const changePeriod = async (value:Period) => {
  if (period.value === value) return
  loading.value = true
  period.value = value
  selectedDate.value = ''
  normalizeSelection()
  await router.replace({
    path:`/operators/${encodeURIComponent(operatorName.value)}`,
    query:{ period:value, ...(selectedDate.value ? { date:selectedDate.value } : {}) },
  })
}
const changeRange = async (value:string) => {
  const nextDate = value || ''
  if (!nextDate || nextDate === selectedDate.value) return
  loading.value = true
  selectedDate.value = nextDate
  await router.replace({
    path:`/operators/${encodeURIComponent(operatorName.value)}`,
    query:{ period:period.value, date:nextDate },
  })
}
const backToList = () => router.push({ path:'/operator-cpo', query:{period:period.value,...(selectedDate.value ? {date:selectedDate.value} : {})} })
const displayPeriod = computed(() => period.value === 'weekly'
  ? `${detail.value.period_start || ''} ~ ${detail.value.period_end || ''}`
  : period.value === 'monthly'
    ? `${(detail.value.period_start || selectedDate.value).slice(0,7)}`
    : (detail.value.data_date || selectedDate.value))
const tablePeriod = computed(() => period.value === 'weekly'
  ? `${(detail.value.period_start || '').slice(5).replace('-', '/')}~${(detail.value.period_end || '').slice(5).replace('-', '/')}`
  : period.value === 'monthly'
    ? `${(detail.value.period_start || selectedDate.value).slice(0,7)}`
    : ((detail.value.data_date || selectedDate.value).slice(5).replace('-', '/')))
</script>

<template>
  <section class="page operator-simple-page">
    <div class="operator-breadcrumb">
      <button class="back-link" @click="backToList">← 返回运营单双情况</button>
    </div>

    <div class="page-head simple-page-head">
      <div>
        <h1>{{ detail.operator }} 运营广告明细</h1>
        <p>按固定报告范围查看该运营在全部业务账户与 AMS 汇总后的产品广告结构与经营指标。</p>
      </div>
      <div class="simple-filters">
        <label>
          <span>运营</span>
          <NSelect :value="operatorName" :options="operatorSelectOptions" style="width:120px" @update:value="onOperatorChange" />
        </label>
        <label>
          <span>报告范围</span>
          <NSelect :value="period" :options="reportRangeOptions" style="width:112px" @update:value="changePeriod" />
        </label>
        <label>
          <span>{{ rangeLabel }}</span>
          <NDatePicker
            v-if="period === 'daily'"
            :formatted-value="selectedDate || null"
            value-format="yyyy-MM-dd"
            type="date"
            :is-date-disabled="isDailyDateDisabled"
            style="width:180px"
            @update:formatted-value="v => changeRange(v || '')"
          />
          <NSelect v-else :value="selectedDate || null" :options="currentRangeOptions" :placeholder="rangeLabel" style="width:280px" @update:value="changeRange" />
        </label>
        <NButton type="primary" :disabled="loading || !selectedDate" @click="load">应用</NButton>
      </div>
    </div>

    <DataSkeleton v-if="loading" variant="detail" :rows="8" />

    <div v-if="!loading" class="simple-data-note">
      <strong>{{ displayPeriod }}</strong>
      <span>{{ detail.summary?.dataProducts ?? 0 }} / {{ detail.summary?.products ?? products.length }} {{ period === 'weekly' ? '周内命中' : period === 'monthly' ? '月内命中' : '有数据' }}</span>
      <span v-if="period !== 'daily'">覆盖 {{ detail.coverageDays ?? 0 }}/{{ detail.expectedDays ?? (period==='weekly' ? 7 : 0) }} 天</span>
      <span>全部账户合并</span>
      <span>{{ detail.final_cpo === false ? '跨账户归属预览' : '正式口径' }}</span>
      <span>DSP 暂无可并入口径时显示 —</span>
    </div>

    <div v-if="!loading" class="card ad-detail-card">
      <div class="ad-detail-title">
        <div>
          <h2>广告类型明细</h2>
          <p>广告费用与广告单按类型展开；总费用、全部订单、CPO、ROAS、TACOS 保留在同一行。</p>
        </div>
      </div>

      <div class="ad-detail-table-wrap">
        <table class="operator-ad-table">
          <thead>
            <tr class="group-head">
              <th rowspan="2" class="sticky-product">产品</th>
              <th rowspan="2" class="sticky-date">{{ period === 'weekly' ? '周区间' : period === 'monthly' ? '月份' : '日期' }}</th>
              <th rowspan="2" class="data-status-col">数据状态</th>
              <th colspan="4" class="group-divider">广告费用</th>
              <th colspan="4" class="group-divider">广告单</th>
              <th rowspan="2" class="metric-start">总费用</th>
              <th rowspan="2">总广告单</th>
              <th rowspan="2">全部订单</th>
              <th rowspan="2">综合 CPO</th>
              <th rowspan="2">ROAS</th>
              <th rowspan="2">TACOS</th>
            </tr>
            <tr class="sub-head">
              <th v-for="type in adTypes" :key="`spend-${type}`">{{ type }}</th>
              <th v-for="type in adTypes" :key="`orders-${type}`">{{ type }}</th>
            </tr>
          </thead>

          <tbody>
            <tr class="summary-first-row">
              <td class="sticky-product product-cell"><strong>综合情况</strong></td>
              <td class="sticky-date date-cell">{{ tablePeriod }}</td>
              <td class="data-status-col">
                <span class="data-status-pill" :class="{ partial: detail.final_cpo === false }">
                  {{ detail.final_cpo === false ? '非完整口径' : '完整口径' }}
                </span>
              </td>
              <td v-for="type in adTypes" :key="`sum-s-${type}`">{{ money(typeTotal('adTypeSpend', type)) }}</td>
              <td v-for="type in adTypes" :key="`sum-o-${type}`">{{ num(typeTotal('adTypeOrders', type)) }}</td>
              <td class="metric-start"><strong>{{ money(detail.summary?.spend) }}</strong></td>
              <td>{{ num(detail.summary?.adOrders) }}</td>
              <td>{{ num(detail.summary?.totalOrders) }}</td>
              <td><strong>{{ money(detail.summary?.cpo) }}</strong></td>
              <td>{{ ratio(detail.summary?.roas) }}</td>
              <td>{{ ratio(detail.summary?.tacos, '%') }}</td>
            </tr>
            <tr v-for="product in products" :key="`${product.code}-${product.parentAsin || ''}`">
              <td class="sticky-product product-cell"><strong>{{ product.code }}</strong></td>
              <td class="sticky-date date-cell">{{ tablePeriod }}</td>
              <td class="data-status-col"><span class="data-status-pill" :class="{ missing: product.dataStatus==='缺当日数据' || product.dataStatus==='缺周数据' || product.dataStatus==='缺月数据', partial: product.dataStatus==='仅广告数据' || product.dataStatus==='仅业务数据' || product.dataStatus==='缺广告侧' || product.dataStatus==='缺业务侧' || product.dataStatus==='缺业务报告' }">{{ product.dataStatus || '有数据' }}</span></td>

              <td v-for="type in adTypes" :key="`s-${product.code}-${type}`">
                {{ money(typeValue(product, 'adTypeSpend', type)) }}
              </td>
              <td v-for="type in adTypes" :key="`o-${product.code}-${type}`">
                {{ num(typeValue(product, 'adTypeOrders', type)) }}
              </td>

              <td class="metric-start"><strong>{{ money(product.spend) }}</strong></td>
              <td>{{ num(product.adOrders) }}</td>
              <td>{{ num(product.totalOrders) }}</td>
              <td><strong>{{ money(product.cpo) }}</strong></td>
              <td>{{ ratio(product.roas) }}</td>
              <td>{{ ratio(product.tacos, '%') }}</td>
            </tr>

            <tr v-if="!products.length">
              <td colspan="17" class="empty-row">该日期没有可用于该运营产品级 CPO 的完整数据。</td>
            </tr>
          </tbody>

        </table>
      </div>

      <div class="table-footnote">
        当前页面按“报告周期 × 运营姓名 × 产品”汇总，不展示账户拆分；自然单暂不倒算。AMS 已回卷到运营本人，特殊 Campaign 全部确认后再切换为最终 CPO。
      </div>
    </div>
  </section>
</template>

<style scoped>
.operator-simple-page { min-width: 0; }
.operator-breadcrumb { margin-bottom: 8px; }
.back-link { border: 0; background: transparent; padding: 0; color: #667085; font-size: 12px; cursor: pointer; }
.back-link:hover { color: var(--blue); }

.simple-page-head { align-items: flex-end; gap: 18px; }
.simple-page-head p { margin-bottom: 0; }
.simple-filters { display: flex; align-items: flex-end; gap: 8px; flex-wrap: wrap; justify-content: flex-end; }
.simple-filters label { display: flex; flex-direction: column; gap: 5px; font-size: 10px; color: #7b8495; }
.simple-filters select,
.simple-filters input { height: 34px; min-width: 118px; border: 1px solid var(--line); border-radius: 7px; background: #fff; color: #344054; padding: 0 9px; outline: none; font-size: 12px; }
.simple-filters input { min-width: 142px; }

.simple-data-note { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin: 2px 0 10px; font-size: 11px; color: #667085; }
.simple-data-note > span,
.simple-data-note > strong { padding: 4px 8px; border-radius: 6px; background: #f6f8fb; border: 1px solid #edf0f4; }
.simple-data-note strong { color: #344054; }

.ad-detail-card { overflow: hidden; }
.ad-detail-title { padding: 16px 18px 12px; border-bottom: 1px solid #e8ebf0; }
.ad-detail-title h2 { margin: 0 0 5px; font-size: 16px; color: #2f3a4d; }
.ad-detail-title p { margin: 0; color: #8a93a2; font-size: 11px; }

.ad-detail-table-wrap { overflow-x: auto; overflow-y: clip; max-width: 100%; position: relative; isolation: isolate; }
.operator-ad-table { width: 100%; min-width: 1660px; border-collapse: separate; border-spacing: 0; table-layout: fixed; position: relative; z-index: 0; }
.operator-ad-table th,
.operator-ad-table td { height: 48px; padding: 0 10px; border-right: 1px solid #e9edf3; border-bottom: 1px solid #e9edf3; text-align: right; white-space: nowrap; font-size: 12px; color: #344054; background: #fff; }
.operator-ad-table th { font-weight: 700; color: #667085; background: #f8f9fb; }
.operator-ad-table thead .group-head th { height: 54px; font-size: 13px; color: #344054; text-align: center; }
.operator-ad-table thead .sub-head th { height: 42px; text-align: center; font-size: 11px; }
.operator-ad-table thead .group-divider { border-left: 1px solid #dfe5ed; }
.operator-ad-table tbody tr:hover td { background: #fafcff; }
.operator-ad-table tbody tr:hover .sticky-product,
.operator-ad-table tbody tr:hover .sticky-date { background: #fafcff; }
.operator-ad-table td strong { color: #273244; }
.operator-ad-table .product-cell { text-align: left; font-size: 13px; }
.operator-ad-table .date-cell { text-align: center; color: #667085; }
.operator-ad-table .dsp { color: #3268f3; }
.operator-ad-table .data-status-col { width: 92px; min-width: 92px; text-align: center; }
.data-status-pill { display:inline-flex;align-items:center;justify-content:center;padding:3px 7px;border-radius:999px;background:#edf8f1;color:#287a4b;font-size:10px; }
.data-status-pill.missing { background:#f2f4f7;color:#667085; }
.data-status-pill.partial { background:#fff3e6;color:#a45f16; }
.operator-ad-table .metric-start { border-left: 2px solid #dfe5ed; }

.sticky-product { position: sticky; left: 0; width: 130px; min-width: 130px; z-index: 1; text-align: left !important; }
.sticky-date { position: sticky; left: 130px; width: 82px; min-width: 82px; z-index: 1; text-align: center !important; box-shadow: 1px 0 0 #e9edf3; }
thead .sticky-product,
thead .sticky-date { z-index: 2; background: #f8f9fb !important; }

.operator-ad-table tfoot td { background: #f8fafc; font-weight: 650; border-bottom: 0; }
.operator-ad-table tfoot .sticky-product,
.operator-ad-table tfoot .sticky-date { background: #f8fafc; }
.total-label { color: #273244 !important; }
.empty-row { text-align: center !important; color: #98a2b3 !important; height: 110px !important; }
.table-footnote { padding: 10px 18px 12px; border-top: 1px solid #edf0f4; color: #8a93a2; font-size: 10px; line-height: 1.6; background: #fbfcfd; }

@media (max-width: 900px) {
  .simple-page-head { align-items: flex-start; flex-direction: column; }
  .simple-filters { justify-content: flex-start; width: 100%; }
}

.simple-filters{flex-wrap:nowrap!important}.simple-filters label{display:flex;flex-direction:column;gap:5px;flex:0 0 auto}
</style>

<style scoped>
.summary-first-row td{background:#f8fafc!important;font-weight:650;border-bottom:2px solid #dfe5ed!important}.summary-first-row .sticky-product,.summary-first-row .sticky-date{background:#f8fafc!important}
</style>
