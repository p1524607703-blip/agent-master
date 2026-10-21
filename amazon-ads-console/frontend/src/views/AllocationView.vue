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
const isManager = computed(() => ['management', 'super_admin'].includes(session.user?.roleCode || ''))
const canCreate = computed(() => isManager.value && capabilities.value?.can_create_run === true)
const enabled = computed(() => capabilities.value?.enabled === true)
const isConfirmedReference = (run: AllocationRun) => run.purpose === 'OPERATIONS_CONFIRMED_REFERENCE' && run.status === 'REFERENCE' && run.calculation_status === 'NOT_RECALCULATED' && run.review_status === 'OPERATIONS_CONFIRMED'
const currentIsReference = computed(() => current.value ? isConfirmedReference(current.value) : false)
const announcement = computed(() => capabilities.value?.message || (capabilities.value?.environment === 'PRODUCTION' && capabilities.value.authoritative_source_connected ? '已接入真实来源。运营确认历史参考与新规则试算分开展示，存在待核实项的结果继续保留待核实状态。' : '开发验收，尚未接入正式数据。当前文件为试算导出；正式 11 表结算模板与正式数据接入仍需验收。'))
const provenanceLabels: Record<string, string> = { source_label: '数据来源', report_exported_date: '原报表导出日期', fact_snapshot_date: '事实快照日期', rule_version: '规则版本', scope_label: '费用范围', mapping_version: '映射版本', source_sha256: '来源文件校验值' }
const provenanceItems = computed(() => Object.entries(current.value?.provenance || {}).filter(([key, value]) => key in provenanceLabels && typeof value === 'string' && value.trim()))
const preferredColumns = ['group', 'style', 'product_code', 'product_id', 'final_cost', 'self_cost', 'halo_cost', 'protection_cost', 'remainder_cost', 'spend_cost', 'transfer_out_cost', 'creator_retained_cost', 'ordered_product_units', 'business_units', 'daily_business_cpo', 'allocation_business_cpo', 'allocation_attributed_unit_cost', 'unit', 'denominator_unit', 'currency']
const columns = computed(() => {
  const available = [...new Set(rows.value.flatMap(row => Object.keys(row)))].filter(key => !key.endsWith('_minor'))
  return [...preferredColumns.filter(key => available.includes(key)), ...available.filter(key => !preferredColumns.includes(key))]
})
const labels: Record<string, string> = { source_spend: '来源广告费用', total_spend: '广告费用合计', final_cost: '最终承担费用', total_cost: '承担费用合计', creator_retained_cost: '创建方留存费用', transfer_out: '转出费用', transfer_in: '转入费用', protection_cost: '保护费用', remainder_cost: '余数承担', retained_total: '保护与余数合计', reconciliation_delta: '守恒差额', product_code: '款号', financial_product_id: '财务产品', operator_code: '运营代号', operator_group: '运营组', currency: '币种', direct_cost: '自推费用', halo_cost: '光环费用', business_units: '业务已订购件数', attributed_units: '广告归因件数', cpo: '每双／件成本', denominator_status: '销量匹配状态', campaign_id: '广告活动编号', account_id: '账户编号', code: '问题代码', message: '说明', severity: '程度', run_id: '计算编号', status: '状态', product_category: '经营品类', age_segment: '年龄层' }
Object.assign(labels, { group: '运营组', style: '款号', product_id: '财务产品编号', id: '编号', spend_cost: '来源广告费用', self_cost: '自推费用', provisional_cost: '暂计承担费用', transfer_out_cost: '转出费用', transfer_in_cost: '转入费用', creator_retained_cost: '创建方留存费用', unallocated_cost: '尚未分配费用', direct_units: '自推归因件数', halo_units: '光环归因件数', all_units: '全部归因件数', daily_business_unit_cost: '日常业务每双／件成本', settlement_business_unit_cost: '分摊后业务每双／件成本', attributed_unit_cost: '广告归因每双／件成本', denominator_reason: '销量匹配说明', unit: '计量单位', business_binding_version: '业务绑定版本', business_snapshot_id: '业务销量快照', denominator_scope: '销量范围', campaign_key: '广告活动范围', creator_group: '创建运营组', ad_product: '广告类型' })
Object.assign(labels, { ordered_product_units: '业务已订购件数', denominator_unit: '销量计量单位', daily_business_cpo: '日常业务每双／件成本', allocation_business_cpo: '分摊后业务每双／件成本', allocation_attributed_unit_cost: '广告归因每双／件成本', business_group: '经营业务组', classification_status: '分类确认状态', source: '费用来源', components: '费用组成明细', retention_reasons: '留存原因', pricing_items: '逐笔计价', created_cost: '创建广告费用', result_hash: '结果版本校验值' })
const summaryItems = computed(() => Object.entries(current.value?.summary || {}).filter(([key, value]) => !key.endsWith('_minor') && (typeof value !== 'object' || value === null)))
const statusLabel = (run: AllocationRun) => isConfirmedReference(run) ? '运营确认历史参考' : ({ SUCCEEDED: '试算完成', PARTIAL: '存在待核实项', FAILED: '计算失败', QUEUED: '排队中', RUNNING: '计算中', SNAPSHOTTING: '准备快照', CANCELLED: '已取消', NOT_RECALCULATED: '历史导入，未重算', REFERENCE: '历史参考' }[String(run.calculation_status || run.status)] || String(run.calculation_status || run.status || '待核实'))
const display = (value: unknown): string => value === null || value === undefined ? '待核实' : typeof value === 'object' ? JSON.stringify(value) : String(value)
const failure = (value: unknown) => { error.value = value instanceof Error ? value.message : '操作失败，请重试。' }

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
  busy.value = true; error.value = ''; rows.value = []; issues.value = []; current.value = null; hasProducts.value = false; rowCursor.value = null; issueCursor.value = null; rowTotal.value = undefined; issueTotal.value = undefined
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
    <div class="page-head"><div><h1>广告费用分摊</h1><p>按冻结版本核对款式费用、待核实项和成本口径。</p></div><div class="actions"><button :disabled="loading || busy" @click="load">刷新</button><button v-if="canCreate" :disabled="!enabled || busy" @click="showCreate = !showCreate">新建试算</button></div></div>
    <div class="notice">{{ announcement }}</div>
    <p v-if="error" class="error" role="alert">{{ error }}</p><p v-if="notice" class="success" role="status">{{ notice }}</p>
    <p v-if="loading" role="status">正在读取分摊模块…</p>
    <p v-else-if="capabilities && !enabled" class="card panel">模块当前未启用。启用后可查看本账号有权访问的版本。</p>
    <form v-if="showCreate && canCreate && enabled" class="card panel" @submit.prevent="create">
      <h2>管理层验收试算</h2><p>仅使用已冻结的验收快照，不会读取或修改正式数据库。费用币种为 USD，月份与快照必须一致。</p>
      <div class="form-grid"><label>结算月份<input v-model="period" type="month" required></label><label>报告时区<input v-model="timezone" required placeholder="America/Los_Angeles"></label></div>
      <label>验收快照 JSON<textarea v-model="snapshotText" rows="9" required spellcheck="false" placeholder="粘贴经核验的冻结快照"></textarea></label>
      <div class="actions"><button type="submit" :disabled="busy">{{ busy ? '提交中…' : '提交试算' }}</button><button type="button" @click="showCreate = false">收起</button></div>
    </form>
    <div v-if="enabled" class="workspace">
      <aside class="card panel"><h2>计算记录</h2><p v-if="!runs.length && !loading">暂无可见计算记录。</p><button v-for="run in runs" :key="run.run_id" class="run-item" :class="{ selected: current?.run_id === run.run_id }" :disabled="busy" @click="select(run)"><strong>{{ run.period || run.run_id }}</strong><span>{{ statusLabel(run) }} · 版本 {{ run.revision ?? '待核实' }}</span><small>{{ run.run_id }}</small></button><p class="muted">已加载 {{ runs.length }}{{ runTotal == null ? '' : ` / ${runTotal}` }} 条</p><button v-if="runCursor" :disabled="busy" @click="more('runs')">加载更多计算记录</button></aside>
      <div class="detail">
        <div v-if="!current" class="card panel">{{ busy ? '正在读取计算详情…' : '选择一条计算记录查看结果。' }}</div>
        <template v-else>
          <section class="card panel"><h2>{{ current.period || '分摊结果' }} · {{ statusLabel(current) }}</h2><p class="muted">编号 {{ current.run_id }} · 版本 {{ current.revision ?? '待核实' }} · USD</p><p v-if="currentIsReference" class="reference-note">运营确认历史参考，保留原文件与原确认口径；未按当前事实或新规则重新计算，不代表新增财务签核。</p><p v-else-if="current.calculation_status === 'PARTIAL' || current.status === 'PARTIAL'" class="notice">当前结果存在待核实项。接受不同报表日期的差异不会补齐未知价格、映射或销量，未知最终金额仍保留为空。</p><p v-else-if="current.purpose === 'REAL_DATA_TRIAL'" class="muted">真实数据试算，与运营确认历史参考分开保存。</p><dl v-if="provenanceItems.length" class="provenance"><div v-for="[key, value] in provenanceItems" :key="key"><dt>{{ provenanceLabels[key] }}</dt><dd>{{ value }}</dd></div></dl><div class="summary-grid"><div v-for="[key, value] in summaryItems" :key="key" class="metric"><span>{{ labels[key] || key }}</span><strong>{{ display(value) }}</strong></div></div><p v-if="!summaryItems.length">尚无可用汇总，等待计算完成或补全数据。</p></section>
          <section class="card panel"><div class="section-head"><h2>核对明细</h2><div class="actions"><select v-model="report" :disabled="busy" aria-label="明细类型" @change="changeReport"><option value="products">款式承担费用</option><option v-if="isManager" value="campaigns">广告活动守恒</option><option value="cpo">业务每双／件成本</option></select><button :disabled="busy" @click="exportReport">下载当前明细 CSV</button><button :disabled="busy || !hasProducts || !capabilities?.export_formats?.includes('xlsx')" @click="exportWorkbook">下载款式 Excel</button></div></div><p class="muted">金额单位为美元（USD）。空值表示尚不能可靠确定，不代表零费用。汇总采用服务器返回口径；下载包含当前授权范围的全部明细。</p><div class="table-wrap"><table v-if="rows.length"><thead><tr><th v-for="column in columns" :key="column">{{ labels[column] || column }}</th></tr></thead><tbody><tr v-for="(row, index) in rows" :key="index"><td v-for="column in columns" :key="column">{{ display(row[column]) }}</td></tr></tbody></table><p v-else>当前没有可用明细。</p></div><p class="muted">已加载 {{ rows.length }}{{ rowTotal == null ? '' : ` / ${rowTotal}` }} 条</p><button v-if="rowCursor" :disabled="busy" @click="more('rows')">加载更多明细</button></section>
          <section v-if="isManager" class="card panel"><h2>待核实项（已加载 {{ issues.length }}{{ issueTotal == null ? '' : ` / ${issueTotal}` }} 条）</h2><p v-if="!issues.length">本页未返回待核实项。正式可确认状态以服务器校验为准。</p><ul v-else class="issues"><li v-for="(issue, index) in issues" :key="index"><strong>{{ display(issue.code || issue.type || '待核实') }}</strong><span>{{ display(issue.message || issue.reason || issue) }}</span></li></ul><button v-if="issueCursor" :disabled="busy" @click="more('issues')">加载更多待核实项</button></section>
        </template>
      </div>
    </div>
  </section>
</template>

<style scoped>
.reference-note{padding:12px;background:#eef6ff;color:#315579;border-radius:8px}.provenance{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin:16px 0}.provenance dt{font-size:12px;color:#64748b}.provenance dd{margin:5px 0 0;overflow-wrap:anywhere}.actions,.section-head{display:flex;gap:10px;align-items:center;flex-wrap:wrap}.section-head{justify-content:space-between}.panel{padding:20px}.notice{padding:14px 18px;background:#fff5dd;color:#785716;border-radius:12px;margin-bottom:16px}.error{color:#a52836;background:#fff0f1;padding:14px;border-radius:10px}.success{color:#166747}.workspace{display:grid;grid-template-columns:260px minmax(0,1fr);gap:18px}.detail{display:grid;gap:18px;min-width:0}.run-item{display:grid;gap:6px;text-align:left;width:100%;margin:10px 0;padding:12px}.run-item.selected{border-color:#4464e9;background:#eef2ff}.run-item small{overflow-wrap:anywhere;color:#64748b}.run-item span,.muted{color:#64748b;font-size:13px}.summary-grid,.form-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:16px}.metric{display:grid;gap:8px;background:#f7f9fc;padding:14px;border-radius:10px}.metric span{color:#64748b;font-size:13px}.metric strong{font-size:22px}label{display:grid;gap:8px;margin:12px 0}button,input,textarea,select{font:inherit;border:1px solid #d9dfeb;border-radius:8px;padding:9px 12px;background:white}button{cursor:pointer}button:disabled{opacity:.5;cursor:default}textarea{width:100%;box-sizing:border-box;font-family:monospace}.table-wrap{overflow:auto}td{max-width:340px;overflow-wrap:anywhere;white-space:normal}.issues{padding-left:20px}.issues li{margin:12px 0}.issues span{display:block;margin-top:5px}@media(max-width:1000px){.workspace{grid-template-columns:1fr}}
</style>
