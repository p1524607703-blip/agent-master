<script setup lang="ts">
import { computed, onActivated, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getJson } from '../api/client'
import { useSessionStore } from '../stores/session'
import { NButton, NDatePicker, NSelect } from 'naive-ui'
import DataSkeleton from '../components/DataSkeleton.vue'

type Period = 'daily'|'weekly'|'monthly'
type PeriodOption = { value:string; label:string; start?:string; end?:string }
type PeriodData = { daily:PeriodOption[]; weekly:PeriodOption[]; monthly:PeriodOption[]; latestDate?:string; weekRule?:string; note?:string }

const router = useRouter()
const route = useRoute()
const session = useSessionStore()
const period = ref<Period>(['weekly','monthly'].includes(String(route.query.period)) ? route.query.period as Period : 'daily')
const selectedDate = ref(String(route.query.date || ''))
const loading = ref(true)
const data = ref<any>({ data_date:'', account_split:false, operators:[], products:[], detailSummary:{}, note:'', me:null })
const periods = ref<PeriodData>({ daily:[], weekly:[], monthly:[] })
const baseAdTypes = ['SP','SB','SD','STV'] as const
const showDsp = ref(false)
const visibleAdTypes = computed(() => showDsp.value ? [...baseAdTypes,'DSP'] : [...baseAdTypes])
const typeGroupColspan = computed(() => visibleAdTypes.value.length)
const detailColumnCount = computed(() => 9 + visibleAdTypes.value.length * 2)

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
const myName = computed(() => data.value?.me?.name || session.user?.displayName || '本人')
const products = computed<any[]>(() => data.value?.products || [])
const detailSummary = computed(() => data.value?.detailSummary || {})

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

const load = async (showLoading=true) => {
  if (showLoading) loading.value = true
  const params = new URLSearchParams({ period:period.value })
  if (selectedDate.value) params.set('date', selectedDate.value)
  const fallback = data.value?.operators?.length
    ? data.value
    : { data_date:selectedDate.value, period:period.value, account_split:false, operators:[], products:[], detailSummary:{}, me:data.value?.me || null, note:'数据服务暂时不可用，请稍后重试' }
  const result = await getJson(`/my-cpo?${params.toString()}`, fallback as any)
  data.value = result
  if (!selectedDate.value && result.data_date) selectedDate.value = result.data_date
  if (selectedDate.value) {
    await router.replace({ path:'/my-cpo', query:{ period:period.value, date:selectedDate.value } })
  }
  if (showLoading) loading.value = false
}

const changePeriod = async (value:Period) => {
  if (period.value === value) return
  period.value = value
  selectedDate.value = ''
  normalizeSelection()
  await router.replace({ path:'/my-cpo', query:{ period:value, ...(selectedDate.value ? {date:selectedDate.value} : {}) } })
  await load(true)
}
const changeRange = async (value:string) => {
  selectedDate.value = value || ''
  if (selectedDate.value) {
    await router.replace({ path:'/my-cpo', query:{ period:period.value, date:selectedDate.value } })
    await load(true)
  }
}
const money = (v:any) => v == null ? '—' : `$${Number(v).toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2})}`
const num = (v:any) => v == null ? '—' : Number(v).toLocaleString(undefined,{maximumFractionDigits:2})
const ratio = (v:any,s='') => v == null ? '—' : `${Number(v).toFixed(2)}${s}`
const typeValue = (product:any, field:'adTypeSpend'|'adTypeOrders', type:string) => product?.[field]?.[type] ?? null
const typeTotal = (field:'adTypeSpend'|'adTypeOrders', type:string) => {
  const values=products.value.map(p=>p?.[field]?.[type]).filter((v:any)=>v!=null)
  return values.length ? values.reduce((sum:number,v:any)=>sum+Number(v||0),0) : null
}
const tablePeriod = computed(() => period.value==='weekly'
  ? `${(data.value.period_start || '').slice(5).replace('-', '/')}~${(data.value.period_end || '').slice(5).replace('-', '/')}`
  : period.value==='monthly'
    ? `${(data.value.period_start || selectedDate.value).slice(0,7)}`
    : ((data.value.data_date || selectedDate.value).slice(5).replace('-', '/')))

onMounted(async () => { await loadPeriods(); await load(true) })
onActivated(() => { if (data.value?.operators?.length) load(false) })
</script>

<template>
  <section class="page operator-cpo-page">
    <div class="page-head">
      <div>
        <h1>CPO 单双数据情况</h1>
        <p>{{ myName }} 登录 · {{ data.me?.group || '—' }} 运营组 · 组内成员共享本组全部 ASIN 数据。</p>
      </div>
      <div class="operator-date-filter">
        <label><span>报告范围</span>
          <NSelect :value="period" :options="reportRangeOptions" style="width:112px" @update:value="changePeriod" />
        </label>
        <label><span>{{ rangeLabel }}</span>
          <NDatePicker
            v-if="period === 'daily'"
            :formatted-value="selectedDate || null"
            value-format="yyyy-MM-dd"
            type="date"
            :is-date-disabled="isDailyDateDisabled"
            style="width:180px"
            @update:formatted-value="v => changeRange(v || '')"
          />
          <NSelect
            v-else
            :value="selectedDate || null"
            :options="currentRangeOptions"
            :placeholder="rangeLabel"
            style="width:280px"
            @update:value="changeRange"
          />
        </label>
        <NButton type="primary" :disabled="loading || !selectedDate" @click="load(true)">应用</NButton>
      </div>
    </div>

    <DataSkeleton v-if="loading" variant="detail" :rows="8" />

    <div v-if="!loading" class="operator-scope-note">
      <strong>统一口径：</strong>{{ data.note || '只使用业务报告 + 推广的商品 + 达成转化的商品三项完整日期。' }}
    </div>

    <div v-if="!loading" class="card panel">
      <div class="panel-head">
        <div>
          <h2 v-if="period === 'weekly'">{{ data.period_start }} ~ {{ data.period_end }} · 我的周 CPO</h2>
          <h2 v-else-if="period === 'monthly'">{{ data.period_start?.slice(0,7) }} · 我的月 CPO</h2>
          <h2 v-else>{{ data.data_date || selectedDate }} · 我的 CPO</h2>
          <p v-if="period !== 'daily'">三项完整日期覆盖 {{ data.coverageDays ?? 0 }}/{{ data.expectedDays ?? 0 }} 天。</p>
          <p v-else>日快照 · 仅展示本人所在运营组的共享数据。</p>
        </div>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr><th>运营组</th><th>产品数据（有/应）</th><th>广告花费</th><th>广告单</th><th>全部订单</th><th>综合 CPO</th><th>ROAS</th><th>TACOS</th><th>状态</th></tr>
          </thead>
          <tbody>
            <tr v-for="r in data.operators" :key="r.group || r.name">
              <td><strong>{{ data.me?.group || r.group }}</strong></td>
              <td><strong>{{ num(r.dataProducts) }} / {{ num(r.products) }}</strong></td>
              <td>{{ money(r.spend) }}</td>
              <td>{{ num(r.adOrders) }}</td>
              <td>{{ num(r.totalOrders) }}</td>
              <td><strong>{{ money(r.cpo) }}</strong></td>
              <td>{{ ratio(r.roas) }}</td>
              <td>{{ ratio(r.tacos,'%') }}</td>
              <td><span class="operator-status" :class="{empty:r.status==='无当日数据' || r.status==='无周数据' || r.status==='无月数据',warn:r.status==='缺业务侧' || r.status==='部分缺业务侧' || r.status==='缺广告侧' || r.status==='缺产品映射' || r.status==='部分缺业务报告' || r.status==='缺业务报告'}">{{ r.status }}</span></td>
            </tr>
            <tr v-if="!data.operators?.length">
              <td colspan="9" class="muted">{{ data.me ? '该区间没有归属到本运营组的完整数据。' : '当前账号未绑定运营组，无法展示数据。' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div v-if="!loading" class="card detail-card">
      <div class="detail-head">
        <div>
          <h2>产品广告明细</h2>
          <p>先按业务账户边界配对，再按产品汇总展示；不在页面拆分账户。</p>
        </div>
        <div class="detail-badges">
          <span>{{ products.length }} 条产品记录</span>
          <span>{{ data.final_cpo === false ? '存在待补映射/非最终口径' : '完整口径' }}</span>
          <NButton size="tiny" quaternary @click="showDsp = !showDsp">{{ showDsp ? '收起 DSP' : '展开 DSP' }}</NButton>
        </div>
      </div>
      <div class="detail-wrap">
        <table class="detail-table">
          <thead>
            <tr class="group-head">
              <th rowspan="2" class="sticky-product">产品</th>
              <th rowspan="2">日期</th>
              <th rowspan="2">数据状态</th>
              <th :colspan="typeGroupColspan" class="metric-start">广告费用</th>
              <th :colspan="typeGroupColspan" class="metric-start">广告单</th>
              <th rowspan="2" class="metric-start">总费用</th>
              <th rowspan="2">总广告单</th>
              <th rowspan="2">全部订单</th>
              <th rowspan="2">综合 CPO</th>
              <th rowspan="2">ROAS</th>
              <th rowspan="2">TACOS</th>
            </tr>
            <tr>
              <th v-for="type in visibleAdTypes" :key="`spend-${type}`">{{ type }}</th>
              <th v-for="type in visibleAdTypes" :key="`orders-${type}`">{{ type }}</th>
            </tr>
          </thead>
          <tbody>
            <tr class="summary-first-row">
              <td class="sticky-product"><strong>综合情况</strong></td>
              <td>{{ tablePeriod }}</td>
              <td><span class="data-status" :class="{warn:data.final_cpo===false}">{{ data.final_cpo===false ? '非完整口径' : '完整口径' }}</span></td>
              <td v-for="type in visibleAdTypes" :key="`sum-s-${type}`">{{ money(typeTotal('adTypeSpend',type)) }}</td>
              <td v-for="type in visibleAdTypes" :key="`sum-o-${type}`">{{ num(typeTotal('adTypeOrders',type)) }}</td>
              <td class="metric-start"><strong>{{ money(detailSummary.spend) }}</strong></td>
              <td>{{ num(detailSummary.adOrders) }}</td>
              <td>{{ num(detailSummary.totalOrders) }}</td>
              <td><strong>{{ money(detailSummary.cpo) }}</strong></td>
              <td>{{ ratio(detailSummary.roas) }}</td>
              <td>{{ ratio(detailSummary.tacos,'%') }}</td>
            </tr>
            <tr v-for="product in products" :key="`${product.code}-${product.parentAsin || ''}`">
              <td class="sticky-product"><strong>{{ product.code }}</strong></td>
              <td>{{ tablePeriod }}</td>
              <td><span class="data-status" :class="{warn:product.dataStatus==='缺业务侧' || product.dataStatus==='部分缺业务侧' || product.dataStatus==='仅业务数据' || product.dataStatus==='缺业务报告'}">{{ product.dataStatus || '有数据' }}</span></td>
              <td v-for="type in visibleAdTypes" :key="`s-${product.code}-${type}`">{{ money(typeValue(product,'adTypeSpend',type)) }}</td>
              <td v-for="type in visibleAdTypes" :key="`o-${product.code}-${type}`">{{ num(typeValue(product,'adTypeOrders',type)) }}</td>
              <td class="metric-start"><strong>{{ money(product.spend) }}</strong></td>
              <td>{{ num(product.adOrders) }}</td>
              <td>{{ num(product.totalOrders) }}</td>
              <td><strong>{{ money(product.cpo) }}</strong></td>
              <td>{{ ratio(product.roas) }}</td>
              <td>{{ ratio(product.tacos,'%') }}</td>
            </tr>
            <tr v-if="!products.length"><td :colspan="detailColumnCount" class="muted empty-detail">该日期没有本运营组可用的产品级完整数据。</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  </section>
</template>

<style scoped>
.operator-date-filter{display:flex;align-items:flex-end;gap:8px;flex-wrap:nowrap;min-width:max-content}
.operator-date-filter label{display:flex;flex-direction:column;gap:5px;font-size:11px;color:#7b8492;flex:0 0 auto}
.operator-scope-note{margin:10px 0 12px;padding:9px 12px;border-radius:8px;border:1px solid #e7ebf1;background:#f8fafc;color:#667085;font-size:12px;line-height:1.65}
.operator-status,.data-status{display:inline-block;padding:3px 8px;border-radius:999px;background:#edf8f1;color:#287a4b;font-size:11px}
.operator-status.empty{background:#f2f4f7;color:#667085}
.operator-status.warn,.data-status.warn{background:#fff3e6;color:#a45f16}
.detail-card{margin-top:14px;overflow:hidden}
.detail-head{display:flex;align-items:center;justify-content:space-between;gap:16px;padding:14px 18px;border-bottom:1px solid #e8ebf0}
.detail-head h2{margin:0 0 4px;font-size:16px;color:#2f3a4d}.detail-head p{margin:0;color:#8a93a2;font-size:11px}
.detail-badges{display:flex;gap:7px;flex-wrap:wrap}.detail-badges span{padding:4px 8px;border-radius:6px;background:#f6f8fb;border:1px solid #edf0f4;color:#667085;font-size:10px}
.detail-wrap{overflow-x:auto;max-width:100%}
.detail-table{width:100%;min-width:1660px;border-collapse:separate;border-spacing:0;table-layout:fixed}
.detail-table th,.detail-table td{height:46px;padding:0 9px;border-right:1px solid #e9edf3;border-bottom:1px solid #e9edf3;text-align:right;white-space:nowrap;font-size:11px;color:#344054;background:#fff}
.detail-table th{background:#f8f9fb;color:#667085;font-weight:700;text-align:center}
.detail-table .group-head th{height:52px;font-size:12px}.detail-table .metric-start{border-left:2px solid #dfe5ed}
.detail-table .sticky-product{position:sticky;left:0;width:120px;min-width:120px;text-align:left!important;z-index:1}.detail-table thead .sticky-product{z-index:2;background:#f8f9fb!important}
.detail-table tfoot td{background:#f8fafc;font-weight:650;border-bottom:0}.detail-table tfoot .sticky-product{background:#f8fafc}
.empty-detail{text-align:center!important;height:90px!important}
@media(max-width:800px){.page-head{align-items:flex-start;flex-direction:column;gap:10px}}
</style>

<style scoped>
.summary-first-row td{background:#f8fafc!important;font-weight:650;border-bottom:2px solid #dfe5ed!important}.summary-first-row .sticky-product{background:#f8fafc!important}
</style>
