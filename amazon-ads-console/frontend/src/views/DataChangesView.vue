<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useSessionStore } from '../stores/session'
import { changesApi, ModuleApiError, type ChangeBatch, type ChangeRow } from '../api/allocation'

const session = useSessionStore()
const batches = ref<ChangeBatch[]>([])
const current = ref<ChangeBatch | null>(null)
const rows = ref<ChangeRow[]>([])
const busy = ref(false)
const loading = ref(false)
const uploading = ref(false)
const disabled = ref(false)
const error = ref('')
const notice = ref('')
const errorFeedback = ref<HTMLParagraphElement | null>(null)
watch(error, async message => {
  if (!message) return
  await nextTick()
  errorFeedback.value?.focus()
})
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
const rowIssue = (value: unknown): string => {
  const code = display(value)
  const messages: Record<string, string> = {
    CHANGE_TYPE_INVALID: 'change_type：填写 ADD、MODIFY 或 DISABLE',
    PRODUCT_CODE_REQUIRED: 'product_code：请填写款号',
    CHILD_ASIN_REQUIRED_OR_SKU_UNRESOLVED: 'child_asin：请填写子 ASIN，当前 SKU 无法解析',
    CHILD_ASIN_INVALID: 'child_asin：须为 10 位大写字母或数字',
    PARENT_ASIN_INVALID: 'parent_asin：须为 10 位大写字母或数字',
    PARENT_OR_EXPLICIT_NO_PARENT_REQUIRED: 'parent_asin / no_parent：填写父 ASIN 或声明 true，不可同时填写',
    TARGET_OUTSIDE_OWN_SCOPE: 'operator_code：超出当前运营账号归属范围',
    RECORD_VERSION_REQUIRED: 'record_id / expected_version：修改或停用须提供原记录编号与版本',
    AUTHORITATIVE_SOURCE_UNAVAILABLE: '权威原记录尚未接入，暂不能校验修改或停用',
    MODIFIED_FIELDS_REQUIRED: 'modified_fields：请列出需要修改的字段',
    FIELD_SET_INVALID: 'modified_fields / clear_fields：字段不可修改或清空，请检查字段名',
    EFFECTIVE_DATE_INVALID: 'effective_from / effective_to：请填写有效的 YYYY-MM-DD 日期',
    EFFECTIVE_INTERVAL_INVALID: 'effective_to：结束日期不能早于生效日期',
    DUPLICATE_CHILD_CONFLICT: '同一子 ASIN 的批次信息冲突，请核对重复行',
  }
  return messages[code] ? messages[code] + '（' + code + '）' : code
}
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
async function template(kind: 'mapping' | 'mapping-add' = 'mapping-add') {
  busy.value = true; error.value = ''
  try { await changesApi.template(kind) } catch (e) { fail(e) } finally { busy.value = false }
}
async function more(kind: 'batches' | 'rows') {
  busy.value = true; error.value = ''
  try {
    if (kind === 'batches' && batchCursor.value) { const page = await changesApi.list(batchCursor.value); batches.value.push(...page.items); batchCursor.value = page.next_cursor }
    else if (kind === 'rows' && current.value && rowCursor.value) { const page = await changesApi.rows(current.value.id, rowCursor.value); rows.value.push(...page.items); rowCursor.value = page.next_cursor }
  } catch (e) { fail(e) }
  finally { busy.value = false }
}
function chooseFile(event: Event) {
  file.value = (event.target as HTMLInputElement).files?.[0] || null
  error.value = ''; notice.value = ''
}
function clearFile() {
  file.value = null
  if (fileInput.value) fileInput.value.value = ''
}
async function upload() {
  if (busy.value || loading.value) return
  error.value = ''; notice.value = ''
  if (!file.value || !file.value.name.toLowerCase().endsWith('.csv')) { error.value = '请先选择 UTF-8 CSV 表格。'; return }
  if (file.value.size > 1024 * 1024) { error.value = '表格超过 1 MiB，请拆分批次后提交。'; return }
  if (Object.values(context.value).some(value => !value.trim())) { error.value = '请填写账户、站点、运营代号、生效日期和修改原因。'; return }
  busy.value = true; uploading.value = true
  try {
    const batch = await changesApi.upload(file.value.name, await file.value.text(), context.value)
    notice.value = '表格已暂存校验。请查看逐行结果，确认后点击“提交审核”；暂存不会修改正式映射。'
    file.value = null; if (fileInput.value) fileInput.value.value = ''
    await refresh(); await select(batch)
  } catch (e) { fail(e) }
  finally { busy.value = false; uploading.value = false }
}
async function action(type: 'submit' | 'withdraw' | 'APPROVE' | 'REJECT') {
  const batch = current.value
  if (!batch || busy.value || loading.value) return
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
    <div class="page-head"><div><h1>数据提交与审批</h1><p>新增或调整 ASIN 映射，核对后提交，由独立管理人员审核。</p></div><div class="actions"><router-link to="/ad-allocation" class="btn">返回费用分摊</router-link><button :disabled="busy || loading" @click="refresh">刷新</button></div></div>
    <div class="notice">开发验收，尚未接入正式数据。批准结果会保留为“待正式生效”，正式主数据接入完成并验收后才可生效。</div>
    <p v-if="error" ref="errorFeedback" class="error" role="alert" tabindex="-1">{{ error }}</p><p v-if="notice" class="success" role="status">{{ notice }}</p>
    <p v-if="loading" role="status">正在读取申请…</p>
    <form v-if="!disabled" class="card upload-panel" :aria-busy="uploading" @submit.prevent="upload">
      <div class="upload-heading">
        <div><span class="section-kicker">ASIN 映射变更</span><h2>提交变更表</h2><p>先填写批次信息，再上传 CSV，核对校验结果后提交审核。</p></div>
        <span class="format-badge">批量 CSV 导入</span>
      </div>
      <ol class="workflow" aria-label="提交步骤">
        <li><span>1</span><div><strong>填写并上传</strong><small>同一批次使用相同账户与站点</small></div></li>
        <li><span>2</span><div><strong>核对校验结果</strong><small>查看每一行的变更与问题</small></div></li>
        <li><span>3</span><div><strong>提交独立审核</strong><small>暂存不会修改正式映射</small></div></li>
      </ol>
      <fieldset :disabled="busy || loading" class="upload-fields">
        <legend class="sr-only">变更批次信息（所有字段均为必填）</legend>
        <div class="upload-layout">
          <section class="context-section" aria-labelledby="context-title">
            <div class="section-title"><h3 id="context-title">批次信息</h3><span>以下字段均为必填</span></div>
            <div class="form-grid">
              <label>业务账户 ID<input v-model="context.account_id" required placeholder="填写已确认的业务账户 ID"></label>
              <label>站点 ID<input v-model="context.marketplace_id" required placeholder="填写该账户对应的站点 ID"></label>
              <label>运营代号<input v-model="context.operator_code" aria-label="运营代号" required :readonly="!isManager" :aria-describedby="!isManager ? 'operator-hint' : undefined"><small v-if="!isManager" id="operator-hint">由当前登录账号确定</small></label>
              <label>生效日期<input v-model="context.effective_from" type="date" required></label>
            </div>
            <label>修改原因与证据<textarea v-model="context.reason" required rows="3" placeholder="说明新增、修改或停用的依据，方便审核人员核对。"></textarea></label>
          </section>
          <section class="file-section" aria-labelledby="file-title">
            <div class="section-title"><h3 id="file-title">变更文件</h3><span>UTF-8 CSV · 最大 1 MiB</span></div>
            <div class="file-picker" :class="{ 'has-file': file }">
              <span class="file-icon" aria-hidden="true">CSV</span>
              <label for="mapping-file">选择变更表</label>
              <p id="file-hint">使用服务器模板填写，可一次提交多条 ASIN 映射。</p>
              <input id="mapping-file" ref="fileInput" type="file" accept=".csv,text/csv" aria-describedby="file-hint file-summary" @change="chooseFile">
              <div id="file-summary" class="file-summary" role="status">
                <template v-if="file"><strong>{{ file.name }}</strong><span>{{ file.size < 1024 ? file.size + ' B' : (file.size / 1024).toFixed(1) + ' KiB' }} · 上传前可重新选择</span><button type="button" class="text-button" @click="clearFile">移除文件</button></template>
                <span v-else>尚未选择文件</span>
              </div>
            </div>
            <p class="field-guide">核心字段：运营代号、款号、父 ASIN、子 ASIN。需要关联卖家 Listing 时填写 SKU；不要在身份表内修改费用或销量。</p>
            <button type="button" class="template-button" @click="template('mapping-add')">下载新增 ASIN 模板</button>
            <details class="template-guide">
              <summary>填写示例与字段说明</summary>
              <p>新增选 ADD，模板只保留 6 列。账户、站点、运营代号、生效日期和原因使用左侧批次信息；窄屏时在上方填写。不要修改英文列名，最多 5,000 行。</p>
              <dl>
                <dt>change_type · 必填</dt><dd>新增填写 ADD。</dd>
                <dt>product_code · 必填</dt><dd>款号，按文本填写，保留前导零。</dd>
                <dt>child_asin · 必填（推荐直接填写）</dt><dd>10 位大写字母或数字。只有权威数据源能够唯一解析 SKU 时才允许省略；当前未接入时不能只填 SKU。</dd>
                <dt>parent_asin / no_parent · 二选一</dt><dd>有父体：填写 10 位父 ASIN，no_parent 留空；无父体：父 ASIN 留空，no_parent 填 true。</dd>
                <dt>sku · 选填</dt><dd>关联卖家 Listing 时填写，保留大小写和空格。</dd>
              </dl>
              <p>以下仅为演示，不代表真实商品。下载的模板不含示例行，避免误提交。</p>
              <pre class="csv-example">change_type,product_code,parent_asin,no_parent,child_asin,sku
ADD,DEMO-01,B000000001,,B000000002,
ADD,DEMO-02,,true,B000000003,</pre>
              <p>可选分类 product_category、age_segment、business_group 及结束日期 effective_to 可用完整模板填写；不要把分类字段当作运营归属。</p>
              <button type="button" @click="template('mapping')">下载完整变更模板</button>
              <p><strong>修改 MODIFY：</strong>还需 record_id、expected_version 和 modified_fields（多个字段以 | 分隔）。只修改列出的字段，空白不自动清空；清空须在 clear_fields 中列出且同时属于 modified_fields。</p>
              <p><strong>停用 DISABLE：</strong>还需 record_id、expected_version。两者都依赖可访问的权威原记录；未接入时会校验失败，不可猜测编号或版本。</p>
              <p>完整模板的 ADD / MODIFY / DISABLE 都需账户、站点、运营代号、款号、生效日期和原因；CSV 对应值为空时才使用页面值，已有非空值优先。修改/停用仍须校验合并后的子 ASIN、父体声明和日期，审批规则不变。</p>
            </details>
          </section>
        </div>
      </fieldset>
      <div class="upload-footer">
        <p>整批校验，整批生效，不自动部分写入。<br><span>上传成功后，请在下方核对结果并提交审核。</span></p>
        <button type="submit" class="primary-button" :disabled="busy || loading || !file">{{ uploading ? '正在上传并校验…' : '上传并校验' }}</button>
      </div>
    </form>
    <div class="results-heading"><h2>申请与校验结果</h2><p>选择申请，查看逐行变更及审批进度。</p></div>
    <div class="workspace">
      <aside class="card panel"><h2>{{ isManager ? '可见申请' : '我的申请' }}</h2><p v-if="!batches.length && !loading">暂无申请。上传变更表后，可在这里查看进度。</p><button v-for="batch in batches" :key="batch.id" class="batch-item" :aria-pressed="current?.id === batch.id" :class="{ selected: current?.id === batch.id }" :disabled="busy" @click="select(batch)"><strong>{{ batch.file_name }}</strong><span>{{ status(batch.status) }} · {{ batch.row_count }} 行</span><small>{{ batch.id }}</small></button><p class="muted">已加载 {{ batches.length }} 条{{ batchCursor ? '，还有后续申请' : '' }}</p><button v-if="batchCursor" :disabled="busy" @click="more('batches')">加载更多申请</button></aside>
      <section class="card panel detail">
        <p v-if="!current" class="empty-detail" role="status">{{ busy ? '正在读取申请…' : '选择申请查看校验结果和审批状态。' }}</p>
        <template v-else><h2>{{ current.file_name }}</h2><div class="batch-meta"><span>{{ status(current.status) }}</span><span>版本 {{ current.version }}</span><span>{{ current.row_count }} 行 · {{ current.error_count }} 行有错误</span><span>提交人 {{ current.created_by }}</span></div><p class="muted">申请 {{ current.id }} · 创建于 {{ current.created_at || '待核实' }}</p><p v-if="current.review_reason">审批说明：{{ current.review_reason }}</p><p v-if="current.status === 'APPROVED_PENDING_APPLY'" class="notice">此批次已获独立批准，尚未正式生效；当前 CPO、映射和历史结算不受影响。</p>
          <div class="table-wrap"><table v-if="rows.length"><thead><tr><th>行号</th><th>原值</th><th>新值</th><th>修改字段</th><th>校验问题</th></tr></thead><tbody><tr v-for="row in rows" :key="row.line"><td>{{ row.line }}</td><td><pre>{{ display(row.old_values) }}</pre></td><td><pre>{{ display(row.new_values) }}</pre></td><td>{{ row.changed_fields?.join('、') || '—' }}</td><td :class="{ 'text-error': row.errors?.length }">{{ row.errors?.length ? row.errors.map(rowIssue).join('；') : '本行校验通过' }}</td></tr></tbody></table><p v-else>暂无逐行校验结果。</p></div><p class="muted">已加载 {{ rows.length }} / {{ current.row_count }} 行，请核对所有行后审批。</p><button v-if="rowCursor" :disabled="busy" @click="more('rows')">加载更多校验行</button>
          <div class="actions"><button v-if="current.capabilities.can_submit" class="primary-button" :disabled="busy" @click="action('submit')">提交审核</button><button v-if="String(current.created_by) === String(session.user?.userId) && ['READY','SUBMITTED','UNDER_REVIEW'].includes(current.status)" :disabled="busy" @click="action('withdraw')">撤回申请</button></div>
          <form v-if="canReview" class="review-box" @submit.prevent="action('APPROVE')"><h3>独立管理审批</h3><p>本次决定固定当前版本和内容。批准后还需经过正式生效校验；任何冲突均应重新核验。</p><label>审批理由与依据<textarea v-model="reviewReason" required rows="3"></textarea></label><div class="actions"><button type="submit" class="primary-button" :disabled="busy">批准当前批次</button><button type="button" :disabled="busy" @click="action('REJECT')">退回补充</button></div></form>
          <p v-else-if="isManager && String(current.created_by) === String(session.user?.userId)" class="muted">自己提交的申请须由另一名有权限的管理人员审批。</p>
        </template>
      </section>
    </div>
  </section>
</template>

<style scoped>
.actions,.batch-meta{display:flex;gap:10px;align-items:center;flex-wrap:wrap}.panel{padding:20px;margin-bottom:18px}.notice{padding:14px 18px;background:#fff5dd;color:#785716;border-radius:12px;margin-bottom:16px}.error{color:#a52836;background:#fff0f1;padding:14px;border-radius:10px}.success{color:#166747}.workspace{display:grid;grid-template-columns:280px minmax(0,1fr);gap:18px}.detail{min-width:0}.batch-item{display:grid;gap:7px;text-align:left;width:100%;margin:10px 0;padding:12px;overflow-wrap:anywhere}.batch-item.selected{border-color:#4464e9;background:#eef2ff}.batch-item span,.batch-item small,.muted{color:#64748b;font-size:13px}.form-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:14px}label{display:grid;gap:8px;margin:12px 0}button,input,textarea{font:inherit;border:1px solid #d9dfeb;border-radius:8px;padding:9px 12px;background:white}button{cursor:pointer}button:disabled{opacity:.5;cursor:default}textarea{width:100%;box-sizing:border-box}input[readonly]{background:#f5f7fa}.table-wrap{overflow:auto;margin:16px 0}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px;max-width:340px;margin:0}.text-error{color:#a52836}.review-box{margin-top:24px;padding-top:12px;border-top:1px solid #e5e9f1}.batch-meta span{padding:5px 9px;background:#f3f6fc;border-radius:6px;font-size:13px}@media(max-width:1000px){.workspace{grid-template-columns:1fr}}
.data-changes-page{max-width:1480px}
.upload-panel{margin-bottom:28px;overflow:hidden}
.upload-heading{padding:24px 28px 20px;display:flex;justify-content:space-between;align-items:center;gap:16px}
.section-kicker{color:#1769c2;font-size:12px;font-weight:600}
.upload-heading h2{margin:6px 0 8px;font-size:20px;color:#1f2937}
.upload-heading p,.results-heading p{margin:0;color:#64748b;font-size:13px;line-height:1.7}
.format-badge{flex-shrink:0;border:1px solid #dce9fc;background:#f4f8ff;color:#1769c2;padding:6px 10px;border-radius:6px;font-size:12px}
.workflow{list-style:none;display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:20px;margin:0;padding:18px 28px;background:#f8fafc;border-block:1px solid var(--line)}
.workflow li{display:flex;gap:10px;align-items:flex-start}
.workflow li>span{display:grid;place-items:center;flex-shrink:0;width:26px;height:26px;border-radius:50%;background:#eaf3ff;color:#1769c2;font-size:12px;font-weight:700}
.workflow strong{display:block;font-size:13px;font-weight:600;line-height:26px}
.workflow small{display:block;color:#64748b;font-size:12px;line-height:1.6}
.upload-fields{border:0;padding:24px 28px;margin:0;min-width:0}
.upload-layout{display:grid;grid-template-columns:minmax(0,1.2fr) minmax(0,1fr);gap:32px}
.context-section,.file-section{min-width:0}
.file-section{padding-left:28px;border-left:1px solid var(--line)}
.section-title{display:flex;justify-content:space-between;align-items:baseline;gap:8px;flex-wrap:wrap;margin-bottom:16px}
.section-title h3{margin:0;font-size:14px}
.section-title>span{font-size:12px;color:#64748b}
.form-grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}
label{margin:0 0 16px;color:#344054;font-size:13px;font-weight:500}
.form-grid label{margin-bottom:0;align-content:start}
.context-section>label{margin-top:18px;margin-bottom:0}
label small{font-weight:400;font-size:12px;color:#64748b}
input,textarea{width:100%;min-width:0;font-size:13px;line-height:1.5;color:#344054}
textarea{resize:vertical;min-height:92px}
button{font-size:13px;color:#344054;font-weight:500}
button:hover:not(:disabled){border-color:#91bfff;background:#f4f8ff}
fieldset:disabled{opacity:.6}
button:disabled{cursor:not-allowed}
input:focus-visible,textarea:focus-visible,button:focus-visible,a:focus-visible{outline:3px solid #b8d7ff;outline-offset:2px;border-color:var(--blue)}
.file-picker{border:1px dashed #c3cfdf;border-radius:8px;background:#fafbfd;padding:20px}
.file-picker.has-file{border-style:solid;border-color:#a7caf7;background:#f7fbff}
.file-icon{display:inline-block;padding:7px;border:1px solid #dce9fc;border-radius:6px;background:white;color:#1769c2;font-size:11px;font-weight:700;margin-bottom:12px}
.file-picker label{margin-bottom:6px}
.file-picker p{font-size:12px;color:#64748b;line-height:1.7;margin:0 0 14px}
input[type=file]{padding:5px;background:white;font-size:12px}
input[type=file]::file-selector-button{border:0;border-radius:4px;background:#eaf3ff;color:#1769c2;padding:7px 10px;margin-right:8px;cursor:pointer}
.file-summary{margin-top:12px;display:grid;gap:6px;font-size:12px;color:#64748b;overflow-wrap:anywhere}
.file-summary strong{color:#344054;font-weight:600}
.text-button{justify-self:start;padding:0;border:0;background:transparent;color:#1769c2;font-size:12px}
.field-guide{color:#64748b;font-size:12px;line-height:1.8;margin:14px 0 12px}
.template-button{font-size:12px}
.upload-footer{display:flex;align-items:center;justify-content:space-between;gap:20px;padding:18px 28px;border-top:1px solid var(--line)}
.upload-footer p{margin:0;color:#475467;font-size:12px;line-height:1.8}
.upload-footer p span{color:#64748b}
.primary-button{background:var(--blue);border-color:var(--blue);color:white}
.primary-button:hover:not(:disabled){background:#0868e8;border-color:#0868e8}
.upload-footer .primary-button{min-width:150px;min-height:40px}
.results-heading{margin-bottom:16px}
.results-heading h2{margin:0 0 5px;font-size:16px}
.detail h2{overflow-wrap:anywhere}
.batch-item.selected{border-color:#91bfff;background:#eef5ff;box-shadow:inset 3px 0 var(--blue)}
.detail .empty-detail{min-height:144px;padding:48px 20px;text-align:center;line-height:1.8;background:#f8fafc;border:1px dashed var(--line);border-radius:8px}
.error,.success{padding:12px 16px;border-radius:8px;margin:0 0 16px;font-size:13px;line-height:1.7;overflow-wrap:anywhere}
.success{background:#edf8f1;border:1px solid #cfe9db}
.notice{font-size:13px;line-height:1.7}
.review-box label{margin-top:16px}
.sr-only{position:absolute;width:1px;height:1px;padding:0;overflow:hidden;clip-path:inset(50%);white-space:nowrap}
@media(max-width:1100px){.upload-layout{grid-template-columns:1fr;gap:24px}.file-section{padding:24px 0 0;border-left:0;border-top:1px solid var(--line)}.workspace{grid-template-columns:1fr}}
@media(max-width:600px){.upload-heading,.upload-fields,.upload-footer{padding:18px}.upload-heading{align-items:flex-start;flex-direction:column;gap:12px}.workflow{grid-template-columns:1fr;padding:16px 18px;gap:12px}.workflow small{display:none}.form-grid{grid-template-columns:1fr}.upload-footer{flex-direction:column;align-items:stretch;gap:12px}.upload-footer .primary-button{width:100%}.file-picker,.panel{padding:16px}}
.template-guide{margin-top:14px;font-size:12px;line-height:1.8;color:#475467}.template-guide summary{cursor:pointer;color:#1769c2;font-weight:600}.template-guide p{margin:12px 0}.template-guide dt{font-weight:600;margin-top:10px}.template-guide dd{margin:3px 0 10px}.csv-example{max-width:100%;overflow:auto;white-space:pre;background:#f1f5f9;padding:10px;border-radius:6px}.template-guide summary:focus-visible{outline:3px solid #b8d7ff;outline-offset:3px}
</style>
