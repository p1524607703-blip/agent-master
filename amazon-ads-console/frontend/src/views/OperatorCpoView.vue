<script setup lang="ts">
import { computed, onActivated, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getJson } from '../api/client'
import { NButton, NDatePicker, NSelect } from 'naive-ui'
import DataSkeleton from '../components/DataSkeleton.vue'

type Period = 'daily'|'weekly'|'monthly'
type PeriodOption = { value:string; label:string; start?:string; end?:string }
type PeriodData = { daily:PeriodOption[]; weekly:PeriodOption[]; monthly:PeriodOption[]; latestDate?:string; weekRule?:string; note?:string }

const router = useRouter()
const route = useRoute()
const period = ref<Period>(['weekly','monthly'].includes(String(route.query.period)) ? route.query.period as Period : 'daily')
const selectedDate = ref(String(route.query.date || ''))
const loading = ref(true)
const data = ref<any>({ data_date:'', account_split:false, operators:[], note:'' })
const periods = ref<PeriodData>({ daily:[], weekly:[], monthly:[] })

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
  const exact=opts.find(x=>x.value===raw)
  if (exact) return
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
    : { data_date:selectedDate.value, period:period.value, account_split:false, operators:[], note:'数据服务暂时不可用，请稍后重试' }
  const result = await getJson(`/operator-cpo?${params.toString()}`, fallback as any)
  data.value = result
  if (!selectedDate.value && result.data_date) selectedDate.value = result.data_date
  if (selectedDate.value) {
    await router.replace({ path:'/operator-cpo', query:{ period:period.value, date:selectedDate.value } })
  }
  if (showLoading) loading.value = false
}

const changePeriod = async (value:Period) => {
  if (period.value === value) return
  period.value = value
  selectedDate.value = ''
  normalizeSelection()
  await router.replace({ path:'/operator-cpo', query:{ period:value, ...(selectedDate.value ? {date:selectedDate.value} : {}) } })
  await load(true)
}
const changeRange = async (value:string) => {
  selectedDate.value = value || ''
  if (selectedDate.value) {
    await router.replace({ path:'/operator-cpo', query:{ period:period.value, date:selectedDate.value } })
    await load(true)
  }
}
const openDetail = (name:string) => router.push({
  path:`/operators/${encodeURIComponent(name)}`,
  query:{ period:period.value, ...(selectedDate.value ? {date:selectedDate.value} : {}) },
})
const money = (v:any) => v == null ? '—' : `$${Number(v).toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2})}`
const num = (v:any) => v == null ? '—' : Number(v).toLocaleString(undefined,{maximumFractionDigits:2})
const ratio = (v:any,s='') => v == null ? '—' : `${Number(v).toFixed(2)}${s}`

onMounted(async () => { await loadPeriods(); await load(true) })
onActivated(() => { if (data.value?.operators?.length) load(false) })
</script>

<template>
  <section class="page operator-cpo-page">
    <div class="page-head">
      <div>
        <h1>运营单双情况</h1>
        <p>按运营本人汇总全部业务账户与 AMS；不提供账户拆分。</p>
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

    <DataSkeleton v-if="loading" variant="table" :rows="10" />

    <div v-if="!loading" class="operator-scope-note">
      <strong>统一口径：</strong>{{ data.note || 'CPO 按运营姓名跨账户汇总。' }}
    </div>

    <div v-if="!loading" class="card panel">
      <div class="panel-head">
        <div>
          <h2 v-if="period === 'weekly'">{{ data.period_start }} ~ {{ data.period_end }} · 周运营 CPO</h2>
          <h2 v-else-if="period === 'monthly'">{{ data.period_start?.slice(0,7) }} · 月运营 CPO</h2>
          <h2 v-else>{{ data.data_date || selectedDate }} · 运营 CPO</h2>
          <p v-if="period === 'weekly'">周快照（周一至周日）· 已有 {{ data.coverageDays ?? 0 }}/{{ data.expectedDays ?? 7 }} 个业务日期；点击运营姓名查看周产品明细。</p>
          <p v-else-if="period === 'monthly'">月快照 · 已有 {{ data.coverageDays ?? 0 }}/{{ data.expectedDays ?? 0 }} 个业务日期；点击运营姓名查看月产品明细。</p>
          <p v-else>日快照 · 点击运营姓名进入产品明细；列表与详情都不会按账户拆分。</p>
        </div>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr><th>运营</th><th>产品数据（有/应）</th><th>广告花费</th><th>广告单</th><th>全部订单</th><th>综合 CPO</th><th>ROAS</th><th>TACOS</th><th>状态</th></tr>
          </thead>
          <tbody>
            <tr v-for="r in data.operators" :key="r.name" class="clickable-row" @click="openDetail(r.name)">
              <td><strong>{{ r.name }}</strong></td>
              <td><strong>{{ num(r.dataProducts) }} / {{ num(r.products) }}</strong></td>
              <td>{{ money(r.spend) }}</td>
              <td>{{ num(r.adOrders) }}</td>
              <td>{{ num(r.totalOrders) }}</td>
              <td><strong>{{ money(r.cpo) }}</strong></td>
              <td>{{ ratio(r.roas) }}</td>
              <td>{{ ratio(r.tacos,'%') }}</td>
              <td><span class="operator-status" :class="{empty:r.status==='无当日数据' || r.status==='无周数据' || r.status==='无月数据',warn:r.status==='缺业务侧' || r.status==='部分缺业务侧' || r.status==='部分缺业务报告' || r.status==='缺业务报告' || r.status==='缺广告侧' || r.status==='缺产品映射'}">{{ r.status }}</span></td>
            </tr>
            <tr v-if="!data.operators?.length"><td colspan="9" class="muted">该日期没有可汇总的运营 CPO 数据。</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  </section>
</template>

<style scoped>
.operator-date-filter{display:flex;align-items:flex-end;gap:8px;flex-wrap:nowrap;min-width:max-content}.operator-date-filter label{display:flex;flex-direction:column;gap:5px;font-size:11px;color:#7b8492;flex:0 0 auto}.operator-scope-note{margin:10px 0 12px;padding:9px 12px;border-radius:8px;border:1px solid #e7ebf1;background:#f8fafc;color:#667085;font-size:12px}.operator-status{display:inline-block;padding:3px 8px;border-radius:999px;background:#edf8f1;color:#287a4b;font-size:12px}.operator-status.empty{background:#f2f4f7;color:#667085}.operator-status.warn{background:#fff3e6;color:#a45f16}@media(max-width:800px){.page-head{align-items:flex-start;flex-direction:column;gap:10px}}
</style>
