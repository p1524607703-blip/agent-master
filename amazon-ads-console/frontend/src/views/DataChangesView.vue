<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useSessionStore } from '../stores/session'
import { changesApi, ModuleApiError, type ChangeBatch, type ChangeRow } from '../api/allocation'

const session = useSessionStore()
const batches = ref<ChangeBatch[]>([])
const current = ref<ChangeBatch | null>(null)
const rows = ref<ChangeRow[]>([])
const busy = ref(false)
const loading = ref(false)
const disabled = ref(false)
const error = ref('')
const notice = ref('')
const file = ref<File | null>(null)
const fileInput = ref<HTMLInputElement | null>(null)
const context = ref({ account_id: '', marketplace_id: '', effective_from: '', reason: '', operator_code: session.user?.operatorCode || '' })
const reviewReason = ref('')
const batchCursor = ref<string | null>(null)
const rowCursor = ref<string | null>(null)
const isManager = computed(() => ['management', 'super_admin'].includes(session.user?.roleCode || ''))
const canReview = computed(() => isManager.value && current.value?.capabilities.can_review === true && String(current.value.created_by) !== String(session.user?.userId))
const stateNames: Record<string, string> = { DRAFT: '草稿', VALIDATING: '校验中', VALIDATION_FAILED: '校验未通过', READY: '待提交', SUBMITTED: '已提交待审核', UNDER_REVIEW: '审核中', APPROVED_PENDING_APPLY: '已批准，待正式生效', APPLIED: '已生效', REJECTED: '已退回', WITHDRAWN: '已撤回', CONFLICT: '存在版本冲突' }
const status = (value: string) => stateNames[value] || value
const display = (value: unknown): string => value == null ? '—' : typeof value === 'object' ? JSON.stringify(value) : String(value)
const fail = (e: unknown) => {
  error.value = e instanceof Error ? e.message : '操作失败，请重试。'
  if (e instanceof ModuleApiError && e.code === 'MODULE_DISABLED') disabled.value = true
}
async function refresh() {
  loading.value = true; error.value = ''
  try { const page = await changesApi.list(); batches.value = page.items; batchCursor.value = page.next_cursor; disabled.value = false }
  catch (e) { fail(e) }
  finally { loading.value = false }
}
async function select(batch: ChangeBatch) {
  busy.value = true; error.value = ''; rows.value = []; current.value = null; reviewReason.value = ''; rowCursor.value = null
  try { current.value = await changesApi.batch(batch.id); const page = await changesApi.rows(batch.id); rows.value = page.items; rowCursor.value = page.next_cursor }
  catch (e) { fail(e) }
  finally { busy.value = false }
}
async function template() {
  busy.value = true; error.value = ''
  try { await changesApi.template() } catch (e) { fail(e) } finally { busy.value = false }
}
async function more(kind: 'batches' | 'rows') {
  busy.value = true; error.value = ''
  try {
    if (kind === 'batches' && batchCursor.value) { const page = await changesApi.list(batchCursor.value); batches.value.push(...page.items); batchCursor.value = page.next_cursor }
    else if (kind === 'rows' && current.value && rowCursor.value) { const page = await changesApi.rows(current.value.id, rowCursor.value); rows.value.push(...page.items); rowCursor.value = page.next_cursor }
  } catch (e) { fail(e) }
  finally { busy.value = false }
}
function chooseFile(event: Event) { file.value = (event.target as HTMLInputElement).files?.[0] || null }
async function upload() {
  error.value = ''; notice.value = ''
  if (!file.value || !file.value.name.toLowerCase().endsWith('.csv')) { error.value = '请先选择 UTF-8 CSV 表格。'; return }
  if (file.value.size > 1024 * 1024) { error.value = '表格超过 1 MiB，请拆分批次后提交。'; return }
  if (Object.values(context.value).some(value => !value.trim())) { error.value = '请填写账户、站点、运营代号、生效日期和修改原因。'; return }
  busy.value = true
  try {
    const batch = await changesApi.upload(file.value.name, await file.value.text(), context.value)
    notice.value = '表格已暂存校验。请查看逐行结果，确认后点击“提交审核”；暂存不会修改正式映射。'
    file.value = null; if (fileInput.value) fileInput.value.value = ''
    await refresh(); await select(batch)
  } catch (e) { fail(e) }
  finally { busy.value = false }
}
async function action(type: 'submit' | 'withdraw' | 'APPROVE' | 'REJECT') {
  const batch = current.value
  if (!batch) return
  error.value = ''; notice.value = ''
  if ((type === 'APPROVE' || type === 'REJECT') && !reviewReason.value.trim()) { error.value = '请填写审批理由与依据。'; return }
  busy.value = true
  try {
    const next = type === 'submit' ? await changesApi.submit(batch) : type === 'withdraw' ? await changesApi.withdraw(batch) : await changesApi.decision(batch, type, reviewReason.value.trim())
    notice.value = `操作完成：${status(next.status)}。`
    await refresh(); await select(next)
  } catch (e) { fail(e) }
  finally { busy.value = false }
}
onMounted(refresh)
</script>

<template>
  <section class="page data-changes-page">
    <div class="page-head"><div><h1>数据提交与审批</h1><p>上传映射变更表，核对后提交，由独立管理人员审核。</p></div><div class="actions"><router-link to="/ad-allocation" class="btn">返回费用分摊</router-link><button :disabled="busy || loading" @click="refresh">刷新</button><button :disabled="busy || disabled" @click="template">下载 CSV 模板</button></div></div>
    <div class="notice">开发验收，尚未接入正式数据。批准结果会保留为“待正式生效”，正式主数据接入完成并验收后才可生效。</div>
    <p v-if="error" class="error" role="alert">{{ error }}</p><p v-if="notice" class="success" role="status">{{ notice }}</p>
    <p v-if="loading" role="status">正在读取申请…</p>
    <form v-if="!disabled" class="card panel" @submit.prevent="upload"><h2>提交变更表</h2><p class="muted">核心字段是运营代号、款号、父 ASIN、子 ASIN。账户、站点与生效日期在批次中固定；需要关联卖家 Listing 时填写 SKU。请使用服务器模板，不在身份表内修改费用或销量。</p><div class="form-grid"><label>业务账户 ID<input v-model="context.account_id" required placeholder="使用已确认的真实业务账户"></label><label>站点 ID<input v-model="context.marketplace_id" required placeholder="账户对应的实际站点"></label><label>运营代号<input v-model="context.operator_code" required :readonly="!isManager"></label><label>生效日期<input v-model="context.effective_from" type="date" required></label></div><label>修改原因与证据<textarea v-model="context.reason" required rows="2" placeholder="说明新增、修改或停用的依据"></textarea></label><label>变更表（UTF-8 CSV，最大 1 MiB）<input ref="fileInput" type="file" accept=".csv,text/csv" :disabled="busy" @change="chooseFile"></label><div class="actions"><button type="submit" :disabled="busy || !file">{{ busy ? '处理中…' : '上传并校验' }}</button><span class="muted">先暂存校验，再提交审核；整批原子生效，不自动部分写入。</span></div></form>
    <div class="workspace">
      <aside class="card panel"><h2>{{ isManager ? '可见申请' : '我的申请' }}</h2><p v-if="!batches.length && !loading">暂无可见申请。</p><button v-for="batch in batches" :key="batch.id" class="batch-item" :class="{ selected: current?.id === batch.id }" :disabled="busy" @click="select(batch)"><strong>{{ batch.file_name }}</strong><span>{{ status(batch.status) }} · {{ batch.row_count }} 行</span><small>{{ batch.id }}</small></button><p class="muted">已加载 {{ batches.length }} 条{{ batchCursor ? '，还有后续申请' : '' }}</p><button v-if="batchCursor" :disabled="busy" @click="more('batches')">加载更多申请</button></aside>
      <section class="card panel detail">
        <p v-if="!current">{{ busy ? '正在读取申请…' : '选择申请查看校验结果和审批状态。' }}</p>
        <template v-else><h2>{{ current.file_name }}</h2><div class="batch-meta"><span>{{ status(current.status) }}</span><span>版本 {{ current.version }}</span><span>{{ current.row_count }} 行 · {{ current.error_count }} 行有错误</span><span>提交人 {{ current.created_by }}</span></div><p class="muted">申请 {{ current.id }} · 创建于 {{ current.created_at || '待核实' }}</p><p v-if="current.review_reason">审批说明：{{ current.review_reason }}</p><p v-if="current.status === 'APPROVED_PENDING_APPLY'" class="notice">此批次已获独立批准，尚未正式生效；当前 CPO、映射和历史结算不受影响。</p>
          <div class="table-wrap"><table v-if="rows.length"><thead><tr><th>行号</th><th>原值</th><th>新值</th><th>修改字段</th><th>校验问题</th></tr></thead><tbody><tr v-for="row in rows" :key="row.line"><td>{{ row.line }}</td><td><pre>{{ display(row.old_values) }}</pre></td><td><pre>{{ display(row.new_values) }}</pre></td><td>{{ row.changed_fields?.join('、') || '—' }}</td><td :class="{ 'text-error': row.errors?.length }">{{ row.errors?.length ? row.errors.map(display).join('；') : '本行校验通过' }}</td></tr></tbody></table><p v-else>暂无逐行校验结果。</p></div><p class="muted">已加载 {{ rows.length }} / {{ current.row_count }} 行，请核对所有行后审批。</p><button v-if="rowCursor" :disabled="busy" @click="more('rows')">加载更多校验行</button>
          <div class="actions"><button v-if="current.capabilities.can_submit" :disabled="busy" @click="action('submit')">提交审核</button><button v-if="String(current.created_by) === String(session.user?.userId) && ['READY','SUBMITTED','UNDER_REVIEW'].includes(current.status)" :disabled="busy" @click="action('withdraw')">撤回申请</button></div>
          <form v-if="canReview" class="review-box" @submit.prevent="action('APPROVE')"><h3>独立管理审批</h3><p>本次决定固定当前版本和内容。批准后还需经过正式生效校验；任何冲突均应重新核验。</p><label>审批理由与依据<textarea v-model="reviewReason" required rows="3"></textarea></label><div class="actions"><button type="submit" :disabled="busy">批准当前批次</button><button type="button" :disabled="busy" @click="action('REJECT')">退回补充</button></div></form>
          <p v-else-if="isManager && String(current.created_by) === String(session.user?.userId)" class="muted">自己提交的申请须由另一名有权限的管理人员审批。</p>
        </template>
      </section>
    </div>
  </section>
</template>

<style scoped>
.actions,.batch-meta{display:flex;gap:10px;align-items:center;flex-wrap:wrap}.panel{padding:20px;margin-bottom:18px}.notice{padding:14px 18px;background:#fff5dd;color:#785716;border-radius:12px;margin-bottom:16px}.error{color:#a52836;background:#fff0f1;padding:14px;border-radius:10px}.success{color:#166747}.workspace{display:grid;grid-template-columns:280px minmax(0,1fr);gap:18px}.detail{min-width:0}.batch-item{display:grid;gap:7px;text-align:left;width:100%;margin:10px 0;padding:12px;overflow-wrap:anywhere}.batch-item.selected{border-color:#4464e9;background:#eef2ff}.batch-item span,.batch-item small,.muted{color:#64748b;font-size:13px}.form-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:14px}label{display:grid;gap:8px;margin:12px 0}button,input,textarea{font:inherit;border:1px solid #d9dfeb;border-radius:8px;padding:9px 12px;background:white}button{cursor:pointer}button:disabled{opacity:.5;cursor:default}textarea{width:100%;box-sizing:border-box}input[readonly]{background:#f5f7fa}.table-wrap{overflow:auto;margin:16px 0}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px;max-width:340px;margin:0}.text-error{color:#a52836}.review-box{margin-top:24px;padding-top:12px;border-top:1px solid #e5e9f1}.batch-meta span{padding:5px 9px;background:#f3f6fc;border-radius:6px;font-size:13px}@media(max-width:1000px){.workspace{grid-template-columns:1fr}}
</style>
