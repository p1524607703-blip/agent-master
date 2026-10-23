<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useSessionStore } from '../stores/session'
import { allocationApi, type AllocationCapabilities, type AllocationRun, type JsonObject } from '../api/allocation'

const session = useSessionStore()
const capabilities = ref<AllocationCapabilities | null>(null)
const runs = ref<AllocationRun[]>([])
const current = ref<AllocationRun | null>(null)
const rows = ref<JsonObject[]>([])
const issues = ref<JsonObject[]>([])
const loading = ref(false)
const busy = ref(false)
const error = ref('')
const notice = ref('')
const showCreate = ref(false)
const period = ref('')
const timezone = ref('America/Los_Angeles')
const snapshotText = ref('')
const report = ref('products')
const runCursor = ref<string | null>(null)
const rowCursor = ref<string | null>(null)
const issueCursor = ref<string | null>(null)
const runTotal = ref<number>()
const rowTotal = ref<number>()
const issueTotal = ref<number>()
const hasProducts = ref(false)
const query = ref('')
const sortKey = ref<'final' | 'unit' | 'style'>('final')
const openRow = ref<string | null>(null)
const showAllColumns = ref(false)
const isManager = computed(() => ['management', 'super_admin'].includes(session.user?.roleCode || ''))
const availablePeriods = computed(() => [...new Set(runs.value.map(run => run.period).filter(Boolean))].sort().reverse())
const ownGroup = computed(() => session.user?.operatorCode || '未绑定')
const ownTotalLabel = computed(() => rowsComplete.value ? '我的分摊费用合计' : '已加载款式合计')
const canCreate = computed(() => isManager.value && capabilities.value?.can_create_run === true)
const enabled = computed(() => capabilities.value?.enabled === true)
const isConfirmedReference = (run: AllocationRun) => run.purpose === 'OPERATIONS_CONFIRMED_REFERENCE' && run.status === 'REFERENCE' && run.calculation_status === 'NOT_RECALCULATED' && run.review_status === 'OPERATIONS_CONFIRMED'
const currentIsReference = computed(() => current.value ? isConfirmedReference(current.value) : false)
const announcement = computed(() => capabilities.value?.message || (capabilities.value?.environment === 'PRODUCTION' && capabilities.value.authoritative_source_connected ? '已接入真实来源。运营确认历史参考与新规则试算分开展示，存在待核实项的结果继续保留待核实状态。' : '开发验收，尚未接入正式数据。当前文件为试算导出；正式 11 表结算模板与正式数据接入仍需验收。'))
const provenanceLabels: Record<string, string> = { source_label: '数据来源', report_exported_date: '原报表导出日期', fact_snapshot_date: '事实快照日期', rule_version: '规则版本', scope_label: '费用范围', mapping_version: '映射版本', source_sha256: '来源文件校验值' }
const provenanceItems = computed(() => Object.entries(current.value?.provenance || {}).filter(([key, value]) => key in provenanceLabels && typeof value === 'string' && value.trim()))
const labels: Record<string, string> = {
  source_spend: '来源广告费用', total_spend: '广告费用合计', final_cost: '最终承担费用', total_cost: '承担费用合计',
  creator_retained_cost: '创建方留存费用', transfer_out: '转出费用', transfer_in: '转入费用',
  protection_cost: '保护费用', remainder_cost: '余数承担', retained_total: '保护与余数合计',
  reconciliation_delta: '守恒差额', product_code: '款号', financial_product_id: '财务产品',
  operator_code: '运营代号', operator_group: '运营组', currency: '币种', direct_cost: '自推费用',
  halo_cost: '光环费用', business_units: '业务已订购件数', attributed_units: '广告归因件数',
  cpo: '每双／件成本', denominator_status: '销量匹配状态', campaign_id: '广告活动编号',
  campaign_name: '广告活动', account_id: '账户编号', code: '问题代码', message: '说明', severity: '程度',
  run_id: '计算编号', status: '状态', product_category: '经营品类', age_segment: '年龄层',
  group: '运营组', style: '款号', product_id: '财务产品编号', id: '编号', spend_cost: '来源广告费用',
  self_cost: '自推费用', provisional_cost: '暂计承担费用', transfer_out_cost: '转出费用',
  transfer_in_cost: '转入费用', unallocated_cost: '尚未分配费用', direct_units: '自推归因件数',
  halo_units: '光环归因件数', all_units: '全部归因件数', daily_business_unit_cost: '日常业务每双／件成本',
  settlement_business_unit_cost: '分摊后业务每双／件成本', attributed_unit_cost: '广告归因每双／件成本',
  denominator_reason: '销量匹配说明', unit: '计量单位', business_binding_version: '业务绑定版本',
  business_snapshot_id: '业务销量快照', denominator_scope: '销量范围', campaign_key: '广告活动范围',
  creator_group: '创建运营组', ad_product: '广告类型', ordered_product_units: '业务已订购件数',
  denominator_unit: '销量计量单位', daily_business_cpo: '日常业务每双／件成本',
  allocation_business_cpo: '分摊后业务每双／件成本', allocation_attributed_unit_cost: '广告归因每双／件成本',
  business_group: '经营业务组', classification_status: '分类确认状态', source: '费用来源',
  components: '费用组成明细', retention_reasons: '留存原因', pricing_items: '逐笔计价',
  created_cost: '创建广告费用', result_hash: '结果版本校验值',
  product_count: '覆盖款式数', campaign_count: '广告活动数',
}

const num = (value: unknown): number | null => {
  if (value === null || value === undefined || value === '') return null
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : null
}
const money = (value: unknown, suffix = ''): string => {
  const parsed = num(value)
  return parsed === null ? '—' : `${parsed.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}${suffix}`
}
const integer = (value: unknown): string => {
  const parsed = num(value)
  return parsed === null ? '—' : parsed.toLocaleString('zh-CN')
}
const unitCost = (value: unknown): string => {
  const parsed = num(value)
  return parsed === null ? '—' : parsed.toFixed(2)
}
const display = (value: unknown): string => value === null || value === undefined ? '待核实' : typeof value === 'object' ? JSON.stringify(value) : String(value)
const statusLabel = (run: AllocationRun) => isConfirmedReference(run) ? '运营确认历史参考' : ({ SUCCEEDED: '试算完成', PARTIAL: '存在待核实项', FAILED: '计算失败', QUEUED: '排队中', RUNNING: '计算中', SNAPSHOTTING: '准备快照', CANCELLED: '已取消', NOT_RECALCULATED: '历史导入，未重算', REFERENCE: '历史参考' }[String(run.calculation_status || run.status)] || String(run.calculation_status || run.status || '待核实'))
const runKind = (run: AllocationRun) => isConfirmedReference(run) ? '运营确认版' : run.purpose === 'REAL_DATA_TRIAL' ? '新规则试算' : '其他版本'
const failure = (value: unknown) => { error.value = value instanceof Error ? value.message : '操作失败，请重试。' }

const productRows = computed(() => report.value === 'products' ? rows.value : [])
const visibleRows = computed(() => {
  const keyword = query.value.trim().toLowerCase()
  const filtered = keyword ? productRows.value.filter(row => `${row.style || ''} ${row.group || ''} ${row.product_id || ''}`.toLowerCase().includes(keyword)) : [...productRows.value]
  return filtered.sort((a, b) => {
    if (sortKey.value === 'style') return String(a.style || '').localeCompare(String(b.style || ''))
    if (sortKey.value === 'unit') return (num(b.allocation_attributed_unit_cost) ?? -1) - (num(a.allocation_attributed_unit_cost) ?? -1)
    return (num(b.final_cost) ?? -1) - (num(a.final_cost) ?? -1)
  })
})
const loadedCount = computed(() => productRows.value.length)
const loadedTotal = computed(() => productRows.value.reduce((sum, row) => sum + (num(row.final_cost) ?? 0), 0))
const hasLoadedCost = computed(() => productRows.value.some(row => num(row.final_cost) !== null))
const rowsComplete = computed(() => rowTotal.value != null && productRows.value.length >= rowTotal.value)
const composition = computed(() => {
  const parts = [
    { key: 'self_cost', name: '自推费用', color: '#1677ff', hint: '本组自己投放产生的广告花费' },
    { key: 'halo_cost', name: '光环费用', color: '#7c3aed', hint: '同款由其他组投放、订单归到本组后分摊进来的费用' },
    { key: 'protection_cost', name: '保护费用', color: '#f59e0b', hint: '按规则给创建方的保护性分摊' },
    { key: 'remainder_cost', name: '余数承担', color: '#94a3b8', hint: '按比例分配后的四舍五入差额' },
  ]
  const total = parts.reduce((sum, part) => sum + (productRows.value.reduce((inner, row) => inner + (num(row[part.key]) ?? 0), 0)), 0)
  return parts.map(part => {
    const amount = productRows.value.reduce((sum, row) => sum + (num(row[part.key]) ?? 0), 0)
    return { ...part, amount, share: total > 0 ? amount / total : 0 }
  })
})
const compositionTotal = computed(() => composition.value.reduce((sum, part) => sum + part.amount, 0))
const hasComposition = computed(() => compositionTotal.value > 0)

const summaryNumber = (key: string) => num(current.value?.summary?.[key])
const kpi = computed(() => {
  const finalCost = summaryNumber('final_cost') ?? summaryNumber('total_cost')
  const sourceSpend = summaryNumber('source_spend') ?? summaryNumber('spend_cost') ?? summaryNumber('total_spend')
  const delta = summaryNumber('reconciliation_delta')
  const products = summaryNumber('product_count')
  const campaigns = summaryNumber('campaign_count')
  if (finalCost !== null || sourceSpend !== null || products !== null) {
    return { mode: 'summary' as const, finalCost, sourceSpend, delta, products: products ?? (loadedCount.value || null), campaigns }
  }
  return { mode: 'rows' as const, finalCost: hasLoadedCost.value ? loadedTotal.value : null, sourceSpend: null, delta: null, products: loadedCount.value || null, campaigns: null }
})
const deltaOk = computed(() => kpi.value.delta !== null && Math.abs(kpi.value.delta) < 0.005)

const campaignRows = computed(() => report.value === 'campaigns' ? rows.value : [])
const tableRows = computed(() => report.value === 'campaigns' ? campaignRows.value : rows.value)
const dynamicColumns = computed(() => {
  const available = [...new Set(tableRows.value.flatMap(row => Object.keys(row)))].filter(key => !key.endsWith('_minor'))
  const keyColumns = ['campaign_id', 'campaign_name', 'group', 'product_count', 'campaign_count', 'spend_cost', 'final_cost', 'transfer_out_cost', 'transfer_in_cost', 'reconciliation_delta']
  const ordered = [...keyColumns.filter(key => available.includes(key)), ...available.filter(key => !keyColumns.includes(key))]
  return showAllColumns.value ? ordered : ordered.slice(0, 8)
})
const hasHiddenColumns = computed(() => {
  const available = new Set(tableRows.value.flatMap(row => Object.keys(row)))
  return available.size > dynamicColumns.value.length
})
const detailFields = (row: JsonObject) => {
  const skip = new Set(['id', 'group', 'style', 'product_id', 'currency', 'unit', 'final_cost', 'self_cost', 'halo_cost', 'protection_cost', 'remainder_cost', 'attributed_units', 'direct_units', 'halo_units', 'allocation_attributed_unit_cost'])
  return Object.entries(row).filter(([key, value]) => !skip.has(key) && !key.endsWith('_minor') && value !== null && value !== undefined && value !== '')
}
const rowSegments = (row: JsonObject) => {
  const parts = [
    { key: 'self_cost', color: '#1677ff' },
    { key: 'halo_cost', color: '#7c3aed' },
    { key: 'protection_cost', color: '#f59e0b' },
    { key: 'remainder_cost', color: '#94a3b8' },
  ]
  const total = num(row.final_cost) ?? 0
  return parts.map(part => ({ ...part, amount: num(row[part.key]) ?? 0, share: total > 0 ? (num(row[part.key]) ?? 0) / total : 0 })).filter(part => part.amount > 0)
}
const toggleRow = (row: JsonObject) => {
  const key = String(row.id || row.style)
  openRow.value = openRow.value === key ? null : key
}

async function load() {
  loading.value = true; error.value = ''
  try {
    capabilities.value = await allocationApi.capabilities()
    if (enabled.value) {
      const page = await allocationApi.runs(); runs.value = page.items; runCursor.value = page.next_cursor; runTotal.value = page.total
      const selected = page.items.find(run => run.run_id === current.value?.run_id) || page.items.find(isConfirmedReference) || page.items[0]
      if (selected) await select(selected)
      else { current.value = null; rows.value = []; issues.value = []; hasProducts.value = false }
    }
    else { runs.value = []; current.value = null; hasProducts.value = false }
  } catch (e) { failure(e) }
  finally { loading.value = false }
}
async function select(run: AllocationRun) {
  busy.value = true; error.value = ''; rows.value = []; issues.value = []; current.value = null; hasProducts.value = false; rowCursor.value = null; issueCursor.value = null; rowTotal.value = undefined; issueTotal.value = undefined; openRow.value = null; query.value = ''
  try {
    const detail = await allocationApi.run(run.run_id)
    current.value = detail
    if (!isManager.value && report.value === 'campaigns') report.value = 'products'
    const page = await allocationApi.rows(run.run_id, report.value)
    rows.value = page.items; rowCursor.value = page.next_cursor; rowTotal.value = page.total
    hasProducts.value = report.value === 'products' ? page.items.length > 0 : (await allocationApi.rows(run.run_id, 'products')).items.length > 0
    if (isManager.value) { const page = await allocationApi.rows(run.run_id, 'issues'); issues.value = page.items; issueCursor.value = page.next_cursor; issueTotal.value = page.total }
  } catch (e) { failure(e) }
  finally { busy.value = false }
}
async function changeReport() { if (current.value) await select(current.value) }
async function more(kind: 'runs' | 'rows' | 'issues') {
  busy.value = true; error.value = ''
  try {
    if (kind === 'runs' && runCursor.value) { const page = await allocationApi.runs(runCursor.value); runs.value.push(...page.items); runCursor.value = page.next_cursor; runTotal.value = page.total }
    else if (kind === 'rows' && current.value && rowCursor.value) { const page = await allocationApi.rows(current.value.run_id, report.value, rowCursor.value); rows.value.push(...page.items); rowCursor.value = page.next_cursor; rowTotal.value = page.total }
    else if (kind === 'issues' && isManager.value && current.value && issueCursor.value) { const page = await allocationApi.rows(current.value.run_id, 'issues', issueCursor.value); issues.value.push(...page.items); issueCursor.value = page.next_cursor; issueTotal.value = page.total }
  } catch (e) { failure(e) }
  finally { busy.value = false }
}
async function create() {
  error.value = ''; notice.value = ''
  if (!/^\d{4}-(0[1-9]|1[0-2])$/.test(period.value)) { error.value = '请选择完整自然月。'; return }
  if (!timezone.value.trim()) { error.value = '请填写报告时区。'; return }
  let snapshot: unknown
  try { snapshot = JSON.parse(snapshotText.value) } catch { error.value = '快照文件内容不是有效的 JSON。'; return }
  if (!snapshot || typeof snapshot !== 'object' || Array.isArray(snapshot)) { error.value = '快照必须为对象。'; return }
  busy.value = true
  try {
    const run = await allocationApi.create(period.value, timezone.value.trim(), snapshot)
    showCreate.value = false; notice.value = '试算已提交。请刷新查看计算状态。'
    await load(); if (run.run_id) await select(run)
  } catch (e) { failure(e) }
  finally { busy.value = false }
}
async function exportReport() {
  if (!current.value) return
  busy.value = true; error.value = ''
  try { await allocationApi.export(current.value.run_id, report.value); notice.value = currentIsReference.value ? '已下载运营确认历史参考明细。该版本保留原确认口径，未按当前数据或新规则重算。' : '已下载试算明细；待核实项与未知金额继续保留，不表示已确认完整结算。' }
  catch (e) { failure(e) }
  finally { busy.value = false }
}
async function exportWorkbook() {
  if (!current.value || !hasProducts.value || !capabilities.value?.export_formats?.includes('xlsx')) return
  busy.value = true; error.value = ''
  try {
    await allocationApi.workbook(current.value.run_id)
    notice.value = currentIsReference.value ? '已下载本账号有权查看的款式 Excel，来源为运营确认历史版本，保留原确认口径。' : '已下载本账号有权查看的款式 Excel。试算及待核实值保留原状态，未知最终金额仍为空。'
  } catch (e) { failure(e) }
  finally { busy.value = false }
}
onMounted(load)
</script>

<template>
  <section class="page allocation-page">
    <header class="page-head">
      <div><h1>广告费用分摊</h1><p>{{ isManager ? '每个款最终承担多少广告费、钱从哪来，一眼看清。' : '按月查看本人款式承担的广告费用；日常费用和 CPO 请到“我的 CPO 明细”。' }}</p></div>
      <div class="actions"><router-link to="/data-changes" class="btn">{{ isManager ? '映射提交与审批' : '新品 / ASIN 提交' }}</router-link><button :disabled="loading || busy" @click="load">刷新</button><button v-if="canCreate" :disabled="!enabled || busy" @click="showCreate = !showCreate">新建试算</button></div>
    </header>

    <div class="notice">{{ announcement }}</div>
    <p v-if="!isManager && !loading && availablePeriods.length" class="scope-note">当前账号 {{ ownGroup }} · 可查看月份：{{ availablePeriods.join('、') }}。只展示已提供的月度结果，其他月份尚无结果时不会显示为 0。</p>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <p v-if="notice" class="success" role="status">{{ notice }}</p>
    <p v-if="loading" role="status">正在读取分摊模块…</p>
    <p v-else-if="capabilities && !enabled" class="card panel">模块当前未启用。启用后可查看本账号有权访问的版本。</p>

    <form v-if="showCreate && canCreate && enabled" class="card panel" @submit.prevent="create">
      <h2>管理层验收试算</h2><p>仅使用已冻结的验收快照，不会读取或修改正式数据库。费用币种为 USD，月份与快照必须一致。</p>
      <div class="form-grid"><label>结算月份<input v-model="period" type="month" required></label><label>报告时区<input v-model="timezone" required placeholder="America/Los_Angeles"></label></div>
      <label>验收快照 JSON<textarea v-model="snapshotText" rows="9" required spellcheck="false" placeholder="粘贴经核验的冻结快照"></textarea></label>
      <div class="actions"><button type="submit" :disabled="busy">{{ busy ? '提交中…' : '提交试算' }}</button><button type="button" @click="showCreate = false">收起</button></div>
    </form>

    <div v-if="enabled" class="workspace">
      <aside class="card panel runs-panel">
        <h2>计算记录</h2>
        <p v-if="!runs.length && !loading" class="muted">当前账号尚无可查看的分摊结果。</p>
        <button v-for="run in runs" :key="run.run_id" class="run-item" :class="{ selected: current?.run_id === run.run_id }" :disabled="busy" @click="select(run)">
          <span class="run-top"><strong>{{ run.period || '未标月份' }}</strong><em class="run-kind">{{ runKind(run) }}</em></span>
          <span class="run-status">{{ statusLabel(run) }}</span>
          <small>版本 {{ run.revision ?? '待核实' }}</small>
        </button>
        <p v-if="!loading" class="muted">已加载 {{ runs.length }}{{ runTotal == null ? '' : ` / ${runTotal}` }} 条</p>
        <button v-if="runCursor" :disabled="busy" @click="more('runs')">加载更多</button>
      </aside>

      <div class="detail">
        <div v-if="!current" class="card panel">{{ loading || busy ? '正在读取分摊结果…' : runs.length ? '选择一条计算记录查看结果。' : '当前账号尚无已提供的月度分摊结果；日常费用和 CPO 请查看“我的 CPO 明细”。' }}</div>
        <template v-else>
          <section class="card panel hero-panel">
            <div class="hero-head">
              <div>
                <span class="eyebrow">{{ current.period || '分摊结果' }} · {{ runKind(current) }}</span>
                <h2>{{ statusLabel(current) }}</h2>
              </div>
              <span class="status-pill" :class="{ good: currentIsReference || current.calculation_status === 'SUCCEEDED', warn: current.status === 'PARTIAL' }">{{ statusLabel(current) }}</span>
            </div>

            <div class="kpis" :class="{ 'own-kpis': !isManager }">
              <div class="kpi kpi-primary">
                <span>{{ !isManager ? ownTotalLabel : kpi.mode === 'rows' ? '已加载款式合计' : '最终承担费用' }}</span>
                <strong>{{ kpi.finalCost === null ? '待核实' : money(kpi.finalCost) }}<small v-if="kpi.finalCost !== null">USD</small></strong>
                <p>{{ isManager ? '本版本所有款式分摊后的承担总额，是这张表的最终结论。' : `仅统计本人 ${ownGroup} 有权查看的款式，不含其他运营费用。` }}</p>
              </div>
              <div v-if="isManager" class="kpi">
                <span>来源广告费用</span>
                <strong>{{ money(kpi.sourceSpend) }}</strong>
                <p>广告报表里的花费总额，也是本次分摊的起点。</p>
              </div>
              <div v-if="isManager" class="kpi">
                <span>守恒差额</span>
                <strong :class="deltaOk ? 'ok' : 'warn-text'">{{ kpi.delta === null ? '—' : money(kpi.delta) }}</strong>
                <p>来源费用 − 最终承担。等于 0 才说明钱没有多也没有少。</p>
              </div>
              <div class="kpi">
                <span>{{ isManager ? '覆盖规模' : '我的款式' }}</span>
                <strong class="scale"><template v-if="kpi.products !== null">{{ integer(kpi.products) }}<small>款</small></template><i v-if="kpi.products !== null && kpi.campaigns !== null">·</i><template v-if="kpi.campaigns !== null">{{ integer(kpi.campaigns) }}<small>活动</small></template><template v-if="kpi.products === null && kpi.campaigns === null">—</template></strong>
                <p>{{ isManager ? '参与本期分摊的款式数，以及这些款式涉及的广告活动数。' : '当前所选月份、版本下，本账号可查看的款式数。' }}</p>
              </div>
            </div>

            <p v-if="!isManager" class="muted scope-note">{{ kpi.finalCost === null ? '当前版本仍有待核实金额，暂不显示确定的分摊总额。' : `以上为本人已加载 ${loadedCount} 款的可见合计${rowsComplete ? '' : '（尚未加载完）'}。` }}</p>
            <p v-else-if="kpi.mode === 'rows'" class="muted scope-note">{{ kpi.finalCost === null ? `当前版本没有返回汇总，且金额尚不能确定（待核实）；以下是已加载 ${loadedCount} 款的件数明细。` : `当前版本没有返回汇总，以上为已加载 ${loadedCount} 款的可见合计${rowsComplete ? '' : '（尚未加载完）'}。` }}</p>
            <p v-if="currentIsReference" class="reference-note">运营确认历史参考：保留原文件与原确认口径，未按当前事实或新规则重算，不代表新增财务签核。</p>
            <p v-else-if="current.calculation_status === 'PARTIAL' || current.status === 'PARTIAL'" class="warning-note">本次试算存在待核实项：未知价格、映射或销量不会被估算补齐，相关金额保持为空。</p>

            <details class="meta-details">
              <summary>数据来源与口径</summary>
              <dl v-if="provenanceItems.length" class="provenance"><div v-for="[key, value] in provenanceItems" :key="key"><dt>{{ provenanceLabels[key] }}</dt><dd>{{ value }}</dd></div></dl>
              <p class="muted">编号 {{ current.run_id }} · 版本 {{ current.revision ?? '待核实' }} · 币种 USD</p>
            </details>
          </section>

          <section v-if="report === 'products'" class="card panel">
            <div class="section-head"><div><h2>钱花在哪</h2><p class="muted">本版本 {{ loadedCount }} 款的费用构成{{ rowsComplete ? '' : '（仅统计已加载部分）' }}。</p></div></div>
            <div v-if="hasComposition" class="composition">
              <div class="stack" role="img" :aria-label="`自推 ${money(composition[0].amount)}，光环 ${money(composition[1].amount)}，保护 ${money(composition[2].amount)}，余数 ${money(composition[3].amount)}`">
                <i v-for="part in composition" :key="part.key" :style="{ width: `${part.share * 100}%`, background: part.color }" :title="`${part.name} ${money(part.amount)}`"></i>
              </div>
              <ul class="legend">
                <li v-for="part in composition" :key="part.key"><i :style="{ background: part.color }"></i><span>{{ part.name }}</span><strong>{{ money(part.amount) }}</strong><em>{{ (part.share * 100).toFixed(1) }}%</em><small>{{ part.hint }}</small></li>
              </ul>
            </div>
            <p v-else class="muted">本版本金额尚未确定或没有费用构成数据，暂不展示拆解。</p>
          </section>

          <section v-if="report === 'products'" class="card panel">
            <div class="section-head">
              <div><h2>款式明细</h2><p class="muted">点一行展开费用构成。金额 USD，空值表示尚不能确定，不代表 0。</p></div>
              <div class="actions">
                <input v-model="query" class="search" type="search" placeholder="搜索款号 / 运营组" aria-label="搜索款号">
                <select v-model="sortKey" aria-label="排序"><option value="final">按最终承担 ↓</option><option value="unit">按每件成本 ↓</option><option value="style">按款号 ↑</option></select>
                <button :disabled="busy" @click="exportReport">导出 CSV</button>
                <button :disabled="busy || !hasProducts || !capabilities?.export_formats?.includes('xlsx')" @click="exportWorkbook">导出 Excel</button>
              </div>
            </div>

            <ul v-if="visibleRows.length" class="product-list">
              <li v-for="row in visibleRows" :key="String(row.id || row.style)" class="product" :class="{ open: openRow === String(row.id || row.style) }">
                <button class="product-main" @click="toggleRow(row)">
                  <span class="p-style"><strong>{{ row.style || '未标款号' }}</strong><em>{{ row.group || '—' }}</em></span>
                  <span class="p-cost"><strong>{{ money(row.final_cost) }}</strong><small>最终承担</small></span>
                  <span class="p-unit"><strong>{{ unitCost(row.allocation_attributed_unit_cost) }}</strong><small>每件成本</small></span>
                  <span class="p-units"><strong>{{ integer(row.attributed_units) }}</strong><small>归因件数</small></span>
                  <span class="p-bar"><i v-for="part in rowSegments(row)" :key="part.key" :style="{ width: `${part.share * 100}%`, background: part.color }"></i></span>
                  <span class="caret" aria-hidden="true">{{ openRow === String(row.id || row.style) ? '−' : '+' }}</span>
                </button>
                <div v-if="openRow === String(row.id || row.style)" class="product-detail">
                  <div class="detail-block">
                    <h3>费用构成</h3>
                    <dl class="kv">
                      <div><dt>自推费用</dt><dd>{{ money(row.self_cost) }}</dd></div>
                      <div><dt>光环费用</dt><dd>{{ money(row.halo_cost) }}</dd></div>
                      <div><dt>保护费用</dt><dd>{{ money(row.protection_cost) }}</dd></div>
                      <div><dt>余数承担</dt><dd>{{ money(row.remainder_cost) }}</dd></div>
                    </dl>
                  </div>
                  <div class="detail-block">
                    <h3>件数</h3>
                    <dl class="kv">
                      <div><dt>全部归因件数</dt><dd>{{ integer(row.attributed_units) }}</dd></div>
                      <div><dt>自推件数</dt><dd>{{ integer(row.direct_units) }}</dd></div>
                      <div><dt>光环件数</dt><dd>{{ integer(row.halo_units) }}</dd></div>
                      <div><dt>计量单位</dt><dd>{{ display(row.unit) }}</dd></div>
                    </dl>
                  </div>
                  <div v-if="detailFields(row).length" class="detail-block wide">
                    <h3>其他字段</h3>
                    <dl class="kv">
                      <div v-for="[key, value] in detailFields(row)" :key="key"><dt>{{ labels[key] || key }}</dt><dd>{{ display(value) }}</dd></div>
                    </dl>
                  </div>
                </div>
              </li>
            </ul>
            <p v-else class="muted">没有匹配的款式。</p>
            <div class="load-more"><span class="muted">已显示 {{ visibleRows.length }} / {{ loadedCount }}{{ rowTotal == null ? '' : `（共 ${rowTotal}）` }}</span><button v-if="rowCursor" :disabled="busy" @click="more('rows')">加载更多</button></div>
          </section>

          <section v-else class="card panel">
            <div class="section-head">
              <div><h2>{{ report === 'campaigns' ? '广告活动守恒' : '业务每双／件成本' }}</h2><p class="muted">金额 USD。表格只显示关键列，其余字段可展开。</p></div>
              <div class="actions"><select v-model="report" :disabled="busy" aria-label="明细类型" @change="changeReport"><option value="products">款式承担费用</option><option v-if="isManager" value="campaigns">广告活动守恒</option><option value="cpo">业务每双／件成本</option></select><button v-if="hasHiddenColumns" @click="showAllColumns = !showAllColumns">{{ showAllColumns ? '只看关键列' : '显示全部字段' }}</button><button :disabled="busy" @click="exportReport">导出 CSV</button></div>
            </div>
            <div class="table-wrap"><table v-if="tableRows.length"><thead><tr><th v-for="column in dynamicColumns" :key="column">{{ labels[column] || column }}</th></tr></thead><tbody><tr v-for="(row, index) in tableRows" :key="index"><td v-for="column in dynamicColumns" :key="column">{{ display(row[column]) }}</td></tr></tbody></table><p v-else>当前没有可用明细。</p></div>
            <div class="load-more"><span class="muted">已加载 {{ tableRows.length }}{{ rowTotal == null ? '' : ` / ${rowTotal}` }}</span><button v-if="rowCursor" :disabled="busy" @click="more('rows')">加载更多</button></div>
          </section>

          <section v-if="isManager" class="card panel">
            <div class="section-head"><div><h2>待核实项</h2><p class="muted">已加载 {{ issues.length }}{{ issueTotal == null ? '' : ` / ${issueTotal}` }} 条。为空不代表一定完整，以服务器校验为准。</p></div></div>
            <ul v-if="issues.length" class="issues">
              <li v-for="(issue, index) in issues" :key="index"><span class="issue-code">{{ display(issue.code || issue.type || '待核实') }}</span><span class="issue-msg">{{ display(issue.message || issue.reason || issue) }}</span></li>
            </ul>
            <p v-else class="muted">本页未返回待核实项。</p>
            <button v-if="issueCursor" :disabled="busy" @click="more('issues')">加载更多</button>
          </section>

          <details class="card panel explain">
            <summary>这些指标是什么意思？</summary>
            <dl class="glossary">
              <div><dt>最终承担费用</dt><dd>本组本期实际承担的广告费用 = 自推 + 光环 + 保护 + 余数。</dd></div>
              <div><dt>自推费用</dt><dd>本组自己投放的广告花掉的钱。</dd></div>
              <div><dt>光环费用</dt><dd>同款由别的组投放、但订单算到本组，按规则分摊进来的费用。</dd></div>
              <div><dt>保护费用</dt><dd>按规则留给创建方的保护性分摊。</dd></div>
              <div><dt>余数承担</dt><dd>按比例分配后四舍五入产生的差额，保证总额守恒。</dd></div>
              <div><dt>每件成本</dt><dd>最终承担费用 ÷ 广告归因件数，用来横向比较款式贵不贵。</dd></div>
              <div><dt>守恒差额</dt><dd>来源广告费用与最终承担总额的差，应为 0.00。</dd></div>
            </dl>
          </details>
        </template>
      </div>
    </div>
  </section>
</template>

<style scoped>
.kpis.own-kpis{grid-template-columns:repeat(2,minmax(0,1fr))}
@media(max-width:640px){.kpis.own-kpis{grid-template-columns:1fr}}
.actions,.section-head{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.section-head{justify-content:space-between;align-items:flex-start}
.section-head h2{margin:0 0 4px}
.panel{padding:18px;margin-bottom:0}
.notice{padding:11px 14px;background:#fff8e8;color:#7a5a17;border-radius:9px;margin-bottom:12px;font-size:12px;line-height:1.6}
.error{color:#a52836;background:#fff0f1;padding:10px 14px;border-radius:8px;font-size:12px}
.success{color:#166747;font-size:12px}
.workspace{display:grid;grid-template-columns:250px minmax(0,1fr);gap:14px;align-items:start}
.detail{display:grid;gap:14px;min-width:0}

.runs-panel h2{font-size:15px;margin:0 0 10px}
.run-item{display:grid;gap:5px;width:100%;text-align:left;margin:8px 0;padding:10px 11px;background:#fff;border:1px solid #e7eaf0;border-radius:9px}
.run-item.selected{border-color:#9dc7ff;background:#f5f9ff}
.run-top{display:flex;align-items:center;justify-content:space-between;gap:8px}
.run-top strong{font-size:14px}
.run-kind{font-style:normal;font-size:10px;color:#5b7699;background:#eef5ff;border-radius:999px;padding:2px 7px;white-space:nowrap}
.run-status{font-size:11px;color:#4b5563}
.run-item small{color:#8a93a2;font-size:10px}
.muted{color:#64748b;font-size:12px}

.hero-panel{padding:20px 20px 16px}
.hero-head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:14px}
.eyebrow{font-size:11px;letter-spacing:.6px;color:#8190a5}
.hero-head h2{font-size:20px;margin:5px 0 0;color:#1b2a3d}
.status-pill{font-size:11px;padding:5px 10px;border-radius:999px;background:#f2f4f7;color:#667085;white-space:nowrap}
.status-pill.good{background:#eaf8f0;color:#177a51}
.status-pill.warn{background:#fff4e5;color:#a8650c}

.kpis{display:grid;grid-template-columns:1.35fr 1fr 1fr 1.15fr;gap:10px}
.kpi{display:flex;flex-direction:column;gap:6px;padding:12px 14px;background:#f8fafc;border:1px solid #edf1f6;border-radius:11px;min-height:104px}
.kpi>span{font-size:11px;color:#7b8495}
.kpi strong{font-size:22px;line-height:1.2;color:#1b2a3d;font-variant-numeric:tabular-nums}
.kpi strong small{font-size:11px;color:#8a96a7;font-weight:400;margin-left:3px}
.kpi strong.ok{color:#12805c}
.kpi strong.warn-text{color:#b45309}
.kpi p{margin:auto 0 0;font-size:10.5px;line-height:1.55;color:#94a0af}
.kpi-primary{background:#f2f7ff;border-color:#d9e8fb}
.kpi-primary strong{font-size:26px;color:#0f4c9c}
.kpi .scale{display:flex;align-items:baseline;gap:4px;flex-wrap:wrap;font-size:19px}
.kpi .scale i{font-style:normal;color:#cbd5e1;margin:0 2px}

.scope-note{margin:10px 0 0}
.reference-note{margin:12px 0 0;padding:10px 12px;background:#eef6ff;color:#315579;border-radius:8px;font-size:11.5px;line-height:1.7}
.warning-note{margin:12px 0 0;padding:10px 12px;background:#fff8e8;color:#7a5a17;border-radius:8px;font-size:11.5px;line-height:1.7}
.meta-details{margin-top:12px;border-top:1px dashed #e7eaf0;padding-top:10px}
.meta-details summary{cursor:pointer;font-size:11px;color:#7b8495}
.provenance{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:10px;margin:10px 0 6px}
.provenance dt{font-size:10px;color:#8a93a2}
.provenance dd{margin:3px 0 0;font-size:11.5px;color:#344054;overflow-wrap:anywhere}

.composition{margin-top:8px}
.stack{display:flex;height:16px;border-radius:999px;overflow:hidden;background:#eef2f7}
.stack i{display:block;height:100%}
.stack i+i{box-shadow:inset 1px 0 0 rgba(255,255,255,.55)}
.legend{list-style:none;padding:0;margin:12px 0 0;display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}
.legend li{display:grid;grid-template-columns:8px auto 1fr auto;align-items:center;gap:6px;font-size:12px;color:#4b5563}
.legend li>i{width:8px;height:8px;border-radius:3px}
.legend li strong{grid-column:4;font-variant-numeric:tabular-nums;color:#1b2a3d;font-size:13px;text-align:right}
.legend li em{grid-column:3;justify-self:end;font-style:normal;font-size:10px;color:#8a93a2}
.legend li small{grid-column:1/-1;font-size:10px;color:#9aa5b4;line-height:1.5}

.search{height:34px;padding:0 10px;font-size:12px;border:1px solid #d9dfeb;border-radius:8px;min-width:170px}
.product-list{list-style:none;margin:8px 0 0;padding:0}
.product{border:1px solid #edf1f6;border-radius:10px;margin:8px 0;overflow:hidden;background:#fff}
.product.open{border-color:#cfe0f7;box-shadow:0 0 0 3px #f2f7ff}
.product-main{display:grid;grid-template-columns:minmax(120px,1.2fr) 130px 110px 90px minmax(90px,1fr) 24px;align-items:center;gap:10px;width:100%;text-align:left;background:#fff;border:0;padding:11px 13px;cursor:pointer}
.product-main:hover{background:#f9fbfe}
.p-style strong{display:block;font-size:13px;color:#1b2a3d}
.p-style em{font-style:normal;font-size:10px;color:#8a93a2}
.p-cost strong,.p-unit strong,.p-units strong{display:block;font-size:14px;color:#1b2a3d;font-variant-numeric:tabular-nums}
.p-cost small,.p-unit small,.p-units small{display:block;font-size:10px;color:#94a0af;margin-top:2px}
.p-bar{display:flex;height:8px;border-radius:999px;overflow:hidden;background:#eef2f7}
.p-bar i{display:block;height:100%}
.caret{font-size:14px;color:#98a2b3;text-align:center}
.product-detail{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;padding:4px 14px 14px;border-top:1px solid #f1f4f8;background:#fcfdff}
.detail-block{padding-top:10px}
.detail-block.wide{grid-column:1/-1}
.detail-block h3{font-size:11px;color:#8190a5;font-weight:600;margin:0 0 6px;letter-spacing:.4px}
.kv{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px 16px;margin:0}
.kv div{display:flex;justify-content:space-between;gap:10px;font-size:11.5px;padding:3px 0;border-bottom:1px dashed #edf1f6}
.kv dt{color:#7b8495}
.kv dd{margin:0;color:#344054;font-variant-numeric:tabular-nums;text-align:right;overflow-wrap:anywhere}
.load-more{display:flex;align-items:center;justify-content:space-between;margin-top:10px}

.table-wrap{overflow:auto;margin-top:8px}
table{min-width:720px}
th{font-size:11px;white-space:nowrap}
td{font-size:12px;max-width:320px;overflow-wrap:anywhere;white-space:normal}

.issues{list-style:none;padding:0;margin:8px 0 0}
.issues li{display:flex;gap:10px;align-items:flex-start;padding:8px 0;border-bottom:1px solid #f2f4f8;font-size:12px}
.issue-code{flex:0 0 auto;font-size:10px;background:#fff4e5;color:#a8650c;border-radius:6px;padding:3px 7px}
.issue-msg{color:#4b5563;line-height:1.6}

.explain{margin-top:0}
.explain summary{cursor:pointer;font-size:12px;color:#4b5563}
.glossary{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px 18px;margin:10px 0 0}
.glossary div{display:grid;grid-template-columns:86px 1fr;gap:8px;font-size:11.5px;padding:4px 0;border-bottom:1px dashed #eef1f5}
.glossary dt{color:#1b2a3d;font-weight:600}
.glossary dd{margin:0;color:#5b6675;line-height:1.6}

.form-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:16px}
label{display:grid;gap:8px;margin:12px 0}
button,input,textarea,select{font:inherit;border:1px solid #d9dfeb;border-radius:8px;padding:8px 12px;background:#fff}
button{cursor:pointer;font-size:12px}
button:disabled{opacity:.5;cursor:default}
textarea{width:100%;box-sizing:border-box;font-family:monospace}

@media(max-width:1200px){.kpis{grid-template-columns:repeat(2,minmax(0,1fr))}.legend{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:1000px){.workspace{grid-template-columns:1fr}.product-main{grid-template-columns:1.4fr 1fr 1fr 24px}.p-units,.p-bar{display:none}}
@media(max-width:760px){.kpis{grid-template-columns:1fr}.glossary,.product-detail{grid-template-columns:1fr}.product-main{grid-template-columns:1.4fr 1fr 24px}.p-unit{display:none}}
</style>
