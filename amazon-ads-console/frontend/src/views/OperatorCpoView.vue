<script setup lang="ts">
import { isNavigatingAway } from '../router/navigation'
import SbAttributionToggle from '../components/SbAttributionToggle.vue'
import { CpoRequestGate, normalizeCpoDate, normalizeSbMode, sbModeLabel, type SbAttributionMode } from '../api/cpoReport'
import FullFunnelRows from '../components/FullFunnelRows.vue'
import PendingGroupExpenses from '../components/PendingGroupExpenses.vue'
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getJson, getJsonStrict } from '../api/client'
import { downloadOperatorReport } from '../api/operatorExports'
import { useSessionStore } from '../stores/session'
import { NButton, NDatePicker, NSelect } from 'naive-ui'
import DataSkeleton from '../components/DataSkeleton.vue'
import { usePageRenderTrace } from '../diagnostics/pageTrace'

type Period = 'daily'|'weekly'|'monthly'
type PeriodOption = { value:string; label:string; start?:string; end?:string }
type PeriodData = { daily:PeriodOption[]; weekly:PeriodOption[]; monthly:PeriodOption[]; latestDate?:string; latestCompleteDate?:string; weekRule?:string; note?:string }

const router = useRouter()
const session = useSessionStore()
const isManager = computed(() => ['management','super_admin'].includes(session.user?.roleCode || ''))
const ownOperatorNames:Record<string,string> = {
  ZJ:'子娟', AJ:'爱菊', YT:'雅婷', XM:'雪敏', DD:'丹丹',
  YS:'雨珊', LB:'丽斌', XH:'鑫华', LW:'林文', ZF:'珍凤',
}
const ownOperatorName = computed(() => ownOperatorNames[(session.user?.operatorCode || '').toUpperCase().slice(0,2)] || '')
const canOpenDetail = (name:string) => isManager.value || name===ownOperatorName.value
const downloadBusy = ref(false)
const exportError = ref('')
async function exportFromOverview(){
  if (downloadBusy.value || loading.value) return
  downloadBusy.value=true; exportError.value=''
  try {
    await downloadOperatorReport(isManager.value ? 'all' : 'summary',period.value,selectedDate.value,undefined,sbAttributionMode.value)
  } catch(e) {
    exportError.value=e instanceof Error ? e.message : '导出失败'
  } finally {
    downloadBusy.value=false
  }
}
const route = useRoute()
const period = ref<Period>(['weekly','monthly'].includes(String(route.query.period)) ? route.query.period as Period : 'daily')
const sbAttributionMode = ref<SbAttributionMode>(normalizeSbMode(route.query.sb_attribution_mode))
const selectedDate = ref(String(route.query.date || ''))
const loading = ref(true)
const loadError = ref('')
const requestGate = new CpoRequestGate()
let preparationSequence = 0
let disposed = false
onBeforeUnmount(() => { disposed = true; ++preparationSequence; requestGate.cancel() })
usePageRenderTrace(loading)
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
  if (period.value === 'daily' && periods.value.latestCompleteDate) {
    const latestComplete=opts.find(x=>x.value===periods.value.latestCompleteDate)
    if (latestComplete) { selectedDate.value=latestComplete.value; return }
  }
  selectedDate.value=opts[0].value
}

let periodsRequest: Promise<void> | undefined
const loadPeriods = () => {
  if (!periodsRequest) periodsRequest = getJson<PeriodData>('/operator-periods', { daily:[],weekly:[],monthly:[] })
    .then(result => { periods.value = result })
  return periodsRequest
}
const reportQuery = () => ({
  period:period.value,
  ...(selectedDate.value ? { date:selectedDate.value } : {}),
  sb_attribution_mode:sbAttributionMode.value,
})
const invalidateReport = () => {
  ++preparationSequence
  requestGate.cancel()
  loading.value = true
}
const changeSbMode = async (mode:SbAttributionMode) => {
  if (mode === sbAttributionMode.value) return
  invalidateReport()
  sbAttributionMode.value = mode
  await router.replace({ path:route.path, query:reportQuery() })
}

const load = async (force=false) => {
  const sourcePath = route.path
  const preparation = ++preparationSequence
  // Explicit dates can load immediately; date choices are fetched concurrently.
  if (!selectedDate.value) {
    await loadPeriods()
    if (disposed || preparation !== preparationSequence) return
    normalizeSelection()
  } else void loadPeriods()
  if (disposed) return
  const targetOperator = ''
  const targetPeriod = period.value
  const targetDate = selectedDate.value
  const targetMode = sbAttributionMode.value
  const key = JSON.stringify([targetOperator,targetPeriod,targetDate,targetMode])
  const request = requestGate.start(key, force)
  if (!request) return
  loading.value = true
  loadError.value = ''
  exportError.value = ''
  try {
    const params = new URLSearchParams({ period:targetPeriod, sb_attribution_mode:targetMode })
    if (targetDate) params.set('date',targetDate)
    const result = await getJsonStrict<any>('/operator-cpo' + '?' + params.toString(), { signal:request.signal })
    if (!request.current()) return
    if (result.sbAttributionMode !== targetMode) throw new Error('服务器返回的 SB 归属方式与当前选择不一致')
    data.value = result
    if (!selectedDate.value && result.data_date) selectedDate.value = result.data_date
    request.finish(JSON.stringify([targetOperator,targetPeriod,selectedDate.value,targetMode]))
    if (route.path === sourcePath && !isNavigatingAway(sourcePath)) await router.replace({ path:'/operator-cpo', query:reportQuery() })
  } catch (error) {
    if (!request.current()) return
    loadError.value = request.signal.aborted ? '数据读取超时，请重试' : error instanceof Error ? error.message : '数据读取失败，请稍后重试'
    data.value = { data_date:selectedDate.value, operators:[], account_split:false, note:'' }
    request.finish()
  } finally {
    if (request.current()) loading.value = false
  }
}

watch(
  () => route.path.startsWith('/operator-cpo')
    ? [String(route.params.operator || ''), String(route.query.period || ''), String(route.query.date || ''), String(route.query.sb_attribution_mode || '')]
    : null,
  async value => {
    if (!value) { ++preparationSequence; requestGate.cancel(); return }
    period.value = ['weekly','monthly'].includes(String(route.query.period)) ? route.query.period as Period : 'daily'
    selectedDate.value = normalizeCpoDate(route.query.date, period.value)
    sbAttributionMode.value = normalizeSbMode(route.query.sb_attribution_mode)
    await load()
  },
  { immediate:true },
)

const changePeriod = async (value:Period) => {
  if (period.value === value) return
  invalidateReport()
  period.value = value
  selectedDate.value = ''
  normalizeSelection()
  await router.replace({ path:'/operator-cpo', query:reportQuery() })
}
const changeRange = async (value:string) => {
  if (!value || value === selectedDate.value) return
  invalidateReport()
  selectedDate.value = normalizeCpoDate(value, period.value)
  await router.replace({ path:'/operator-cpo', query:reportQuery() })
}

const openDetail = (name:string) => {
  if (!canOpenDetail(name)) return
  if (!isManager.value) {
    router.push({ path:'/my-cpo', query:reportQuery() })
    return
  }
  router.push({ path:`/operators/${encodeURIComponent(name)}`,
    query:reportQuery() })
}
const money = (v:any) => v == null ? '—' : `$${Number(v).toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2})}`
const num = (v:any) => v == null ? '—' : Number(v).toLocaleString(undefined,{maximumFractionDigits:2})
const ratio = (v:any,s='') => v == null ? '—' : `${Number(v).toFixed(2)}${s}`


</script>

<template>
  <section class="page operator-cpo-page">
    <div class="page-head">
      <div>
        <h1>运营单双情况</h1>
        <p>按运营本人汇总全部业务账户与 AMS；不提供账户拆分。</p>
      </div>
      <div class="operator-date-filter">
        <SbAttributionToggle :model-value="sbAttributionMode" @update:model-value="changeSbMode" />
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

    <p v-if="loadError && !loading" class="overview-export-error" role="alert">{{ loadError }}。本次数据未读取成功，请重试。</p>

    <FullFunnelRows v-if="!loading" :ledger="data.fullFunnel" />
    <PendingGroupExpenses v-if="!loading && isManager" :entries="data.groupPendingExpenses"
      :total="data.operatorPendingSpend" :all-groups="true" />

    <div v-if="!loading" class="operator-scope-note">
      <strong>{{ sbModeLabel(sbAttributionMode) }} · 统一口径：</strong>{{ data.note || 'CPO 按运营姓名跨账户汇总。' }}
    </div>

    <div v-if="!loading" class="card panel">
      <div class="panel-head overview-report-head">
        <div>
          <h2 v-if="period === 'weekly'">{{ data.period_start }} ~ {{ data.period_end }} · 周运营 CPO</h2>
          <h2 v-else-if="period === 'monthly'">{{ data.period_start?.slice(0,7) }} · 月运营 CPO</h2>
          <h2 v-else>{{ data.data_date || selectedDate }} · 运营 CPO</h2>
          <p v-if="period === 'weekly'">周快照（周一至周日）· 已有 {{ data.coverageDays ?? 0 }}/{{ data.expectedDays ?? 7 }} 个业务日期；点击运营姓名查看周产品明细。</p>
          <p v-else-if="period === 'monthly'">月快照 · 已有 {{ data.coverageDays ?? 0 }}/{{ data.expectedDays ?? 0 }} 个业务日期；点击运营姓名查看月产品明细。</p>
          <p v-else>日快照 · {{ isManager ? '点击运营姓名查看明细' : '共用汇总可查看所有运营；个人产品明细仅限本人' }}；不按账户拆分。</p>
        </div>
        <NButton type="primary" :loading="downloadBusy" :disabled="!selectedDate || loading"
          @click="exportFromOverview">{{ isManager ? '一键导出所有报表' : '导出共用汇总' }}</NButton>
      </div>
      <p v-if="exportError" class="overview-export-error" role="alert">{{ exportError }}</p>
      <div class="table-wrap">
        <table>
          <thead>
            <tr><th>运营</th><th>产品数据（有/应）</th><th>广告花费</th><th>广告单</th><th>全部订单</th><th>综合 CPO</th><th>ROAS</th><th>TACOS</th><th>状态</th></tr>
          </thead>
          <tbody>
            <tr v-for="r in data.operators" :key="r.name" :class="{'clickable-row':canOpenDetail(r.name)}" @click="openDetail(r.name)">
              <td><strong>{{ r.name }}</strong></td>
              <td><strong>{{ num(r.dataProducts) }} / {{ num(r.products) }}</strong></td>
              <td>{{ money(r.spend) }}<small v-if="Number(r.pendingProductSpend) > 0 && canOpenDetail(r.name)" class="pending-expense-hint">含组内待分摊费用 {{ money(r.pendingProductSpend) }}</small></td>
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
.operator-date-filter{display:flex;align-items:flex-end;gap:8px;flex-wrap:wrap}.operator-date-filter label{display:flex;flex-direction:column;gap:5px;font-size:11px;color:#7b8492;flex:0 0 auto}.operator-scope-note{margin:10px 0 12px;padding:9px 12px;border-radius:8px;border:1px solid #e7ebf1;background:#f8fafc;color:#667085;font-size:12px}.operator-status{display:inline-block;padding:3px 8px;border-radius:999px;background:#edf8f1;color:#287a4b;font-size:12px}.operator-status.empty{background:#f2f4f7;color:#667085}.operator-status.warn{background:#fff3e6;color:#a45f16}@media(max-width:800px){.page-head{align-items:flex-start;flex-direction:column;gap:10px}}
.overview-report-head{display:flex;justify-content:space-between;align-items:center;gap:16px;flex-wrap:wrap}
.overview-export-error{color:#b42318;font-size:12px;margin:10px 0}
.pending-expense-hint{display:block;color:#a45f16;font-size:11px;margin-top:3px}
</style>
