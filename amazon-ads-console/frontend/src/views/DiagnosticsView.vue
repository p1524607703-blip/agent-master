<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { getDiagnosticRequests, getDiagnosticsStatus, type DiagnosticFilters, type DiagnosticRequest, type DiagnosticRequests, type DiagnosticStatus } from '../api/diagnostics'
import { browserTraceSnapshot, clearBrowserTrace, copyEvidence, downloadEvidence } from '../diagnostics/browserTrace'
import { usePageRenderTrace } from '../diagnostics/pageTrace'

const loading = ref(true)
usePageRenderTrace(loading)
const status = ref<DiagnosticStatus | null>(null)
const requests = ref<DiagnosticRequests>({ items: [], available: false })
const filters = ref({ request_id: '', user_id: '', username: '', endpoint: '', since: '', until: '', limit: '100' })
const error = ref('')
const feedback = ref('')
const browserTrace = ref(browserTraceSnapshot())
const selectedRequest = ref<DiagnosticRequest | null>(null)
let sequence = 0
const cacheEntries = computed(() => Object.entries(status.value?.cache || {}))
const time = (value?: string) => value ? new Date(value).toLocaleString() : '—'
const ms = (value?: number) => value == null ? '—' : `${Number(value).toFixed(1)} ms`
const cell = (value: unknown): string => value == null ? '—' : typeof value === 'object' ? JSON.stringify(value) : String(value)
const timing = (row: DiagnosticRequest, name: 'total_ms' | 'psql_ms' | 'build_ms' | 'lock_wait_ms') => row[name] ?? row.timings?.[name]
const cacheState = (row: DiagnosticRequest) => {
  if (row.l1_hit != null || row.l2_hit != null) return `L1 命中 ${row.l1_hit ?? 0} / 未命中 ${row.l1_miss ?? 0} / 过期 ${row.l1_stale ?? 0}；L2 命中 ${row.l2_hit ?? 0} / 未命中 ${row.l2_miss ?? 0} / 错误 ${row.l2_error ?? 0}`
  return row.cache_status || row.cache?.status || ((row.cache_hit ?? row.cache?.hit) == null ? '—' : (row.cache_hit ?? row.cache?.hit) ? '命中' : '未命中')
}
const release = (row: DiagnosticRequest) => row.release_version || (typeof row.release === 'string' ? row.release : row.release?.release_version) || '—'
const commit = (row: DiagnosticRequest) => row.git_commit || row.commit || (typeof row.release === 'object' ? row.release?.git_commit : undefined) || '—'
const details = computed(() => selectedRequest.value ? [
  ['用户', `${selectedRequest.value.username || '—'} (ID ${selectedRequest.value.user_id ?? '—'})`],
  ['角色 / 运营组', `${selectedRequest.value.role || '—'} / ${selectedRequest.value.operator_group || '—'}`],
  ['日期 / 周期', `${selectedRequest.value.date || '—'} / ${selectedRequest.value.period || '—'}`],
  ['区间', `${selectedRequest.value.period_start || '—'} ~ ${selectedRequest.value.period_end || '—'}`],
  ['锁获取 / 超时次数', `${selectedRequest.value.lock_acquired ?? '—'} / ${selectedRequest.value.lock_timeout ?? '—'}`],
  ['数据库调用次数', cell(selectedRequest.value.psql_calls)],
  ['进程 ID', cell(selectedRequest.value.pid)],
  ['异常类型', selectedRequest.value.exception_type || '无'],
] : [])

function activeFilters(): DiagnosticFilters {
  const result: DiagnosticFilters = { request_id: filters.value.request_id.trim(), user_id: filters.value.user_id.trim(), username: filters.value.username.trim(), endpoint: filters.value.endpoint.trim(), limit: filters.value.limit }
  if (filters.value.since) result.since = new Date(filters.value.since).toISOString()
  if (filters.value.until) result.until = new Date(filters.value.until).toISOString()
  return result
}

async function load(): Promise<void> {
  const current = ++sequence
  loading.value = true
  error.value = ''
  feedback.value = ''
  selectedRequest.value = null
  try {
    const params = activeFilters()
    if (params.since && params.until && params.since > params.until) throw new Error('开始时间应早于结束时间')
    const results = await Promise.allSettled([getDiagnosticsStatus(), getDiagnosticRequests(params)])
    if (current !== sequence) return
    const [system, logs] = results
    status.value = system.status === 'fulfilled' ? system.value : null
    requests.value = logs.status === 'fulfilled' ? logs.value : { items: [], available: false }
    error.value = results.filter(result => result.status === 'rejected').map(result => result.reason instanceof Error ? result.reason.message : '诊断数据读取失败').join('；')
  } catch (err) {
    if (current === sequence) error.value = err instanceof Error ? err.message : '诊断数据读取失败'
  } finally {
    if (current === sequence) {
      loading.value = false
      browserTrace.value = browserTraceSnapshot()
    }
  }
}

async function copy(value: unknown, label: string): Promise<void> {
  try { await copyEvidence(value); feedback.value = `${label}已复制` }
  catch (err) { feedback.value = err instanceof Error ? err.message : '复制失败，请下载记录' }
}

function serverEvidence(): unknown {
  return { captured_at: new Date().toISOString(), filters: activeFilters(), status: status.value,
    requests: selectedRequest.value ? [selectedRequest.value] : requests.value.items }
}

function refreshBrowserTrace(): void { browserTrace.value = browserTraceSnapshot() }
function clearTrace(): void { clearBrowserTrace(); refreshBrowserTrace(); feedback.value = '当前浏览器记录已清空' }
onMounted(load)
</script>

<template>
  <section class="page diagnostics-page">
    <div class="page-head"><div><h1>系统诊断 / 请求追踪</h1><p>查看请求耗时、缓存与发布信息，用请求 ID 关联浏览器和服务端证据。</p></div>
      <button class="btn" :disabled="loading" @click="load">{{ loading ? '读取中…' : '刷新' }}</button>
    </div>
    <p v-if="error" class="diagnostic-message error" role="alert">{{ error }}</p>
    <p v-if="feedback" class="diagnostic-message" role="status">{{ feedback }}</p>

    <div class="card panel">
      <div class="panel-head"><h2>运行状态</h2><span class="muted small">管理层可见</span></div>
      <div class="system-grid">
        <div><span>发布版本</span><strong>{{ status?.release?.release_version || '未提供' }}</strong></div>
        <div><span>Git 提交</span><strong class="mono">{{ status?.release?.git_commit || '未提供' }}</strong></div>
        <div><span>服务端追踪</span><strong>{{ status ? (status.trace?.available ? '可用' : '不可用') : '未取得状态' }}</strong><small v-if="status?.trace?.retention_days != null">最长保留 {{ status.trace.retention_days }} 天（容量限制可能提前轮转）</small></div>
      </div>
      <details v-if="cacheEntries.length" class="cache-details"><summary>缓存状态</summary><dl><template v-for="[key,value] in cacheEntries" :key="key"><dt>{{ key }}</dt><dd>{{ cell(value) }}</dd></template></dl></details>
    </div>

    <div class="card panel">
      <div class="panel-head"><div><h2>服务端请求记录</h2><p>时间按当前浏览器时区输入。{{ requests.retention_days != null ? `最长保留 ${requests.retention_days} 天，容量限制可能提前轮转。` : '' }}</p></div>
        <div class="diagnostic-actions"><button class="btn compact" :disabled="!status && !requests.items.length" @click="copy(serverEvidence(), '诊断证据')">复制诊断证据</button><button class="btn compact" :disabled="!status && !requests.items.length" @click="downloadEvidence(serverEvidence(), 'cpo-server-diagnostics.json')">下载证据</button></div>
      </div>
      <form class="diagnostic-filters" @submit.prevent="load">
        <label>请求 ID<input v-model="filters.request_id" placeholder="X-Request-ID" /></label>
        <label>用户 ID<input v-model="filters.user_id" type="number" min="1" placeholder="全部用户" /></label>
        <label>用户名<input v-model="filters.username" placeholder="全部用户名" /></label>
        <label>接口<input v-model="filters.endpoint" placeholder="如 /api/my-cpo" /></label>
        <label>开始时间<input v-model="filters.since" type="datetime-local" /></label>
        <label>结束时间<input v-model="filters.until" type="datetime-local" /></label>
        <label>记录数<select v-model="filters.limit"><option value="50">50</option><option value="100">100</option><option value="200">200</option></select></label>
        <button class="btn primary" :disabled="loading" type="submit">查询</button>
      </form>
      <p v-if="requests.scan_truncated || requests.message" class="diagnostic-message" role="status">{{ requests.message || '本次只扫描了最近部分日志；更早记录可能未包含在查询结果中。' }}</p>
      <div class="table-wrap"><table class="requests-table"><thead><tr><th>请求 / 时间</th><th>用户 / 接口</th><th>状态</th><th>总耗时</th><th>缓存</th><th>锁等待</th><th>数据库</th><th>构建</th><th>Revision / 版本</th><th>操作</th></tr></thead>
        <tbody><tr v-for="row in requests.items" :key="row.request_id" :class="{ selected: selectedRequest?.request_id === row.request_id }" @click="selectedRequest = row">
          <td><code class="request-id">{{ row.request_id }}</code><small>{{ time(row.started_at || row.timestamp) }}</small></td>
          <td>{{ row.username || '—' }} ({{ row.user_id ?? '—' }})<small>{{ row.method || 'GET' }} {{ row.endpoint || '—' }}</small></td>
          <td>{{ row.status_code ?? row.status ?? '—' }}</td><td>{{ ms(timing(row,'total_ms')) }}</td><td>{{ cacheState(row) }}</td><td>{{ ms(timing(row,'lock_wait_ms')) }}</td><td>{{ ms(row.db_wall_ms ?? timing(row,'psql_ms')) }}<small>{{ row.psql_calls ?? '—' }} 次调用</small></td><td>{{ ms(timing(row,'build_ms')) }}</td>
          <td class="revision"><code>{{ row.revision || row.cache?.revision || '—' }}</code><small>{{ release(row) }}</small><small>{{ commit(row) }}</small></td>
          <td><button class="link-btn" @click.stop="copy(row.request_id, '请求 ID')">复制 ID</button><button class="link-btn" @click.stop="copy(row, '请求证据')">复制证据</button></td>
        </tr><tr v-if="!requests.items.length"><td colspan="10" class="empty-records">{{ loading ? '正在读取请求记录…' : error ? '本次查询未成功，请重试。' : requests.available ? (requests.scan_truncated ? '已扫描部分没有匹配记录，更早日志可能未扫描。' : '筛选范围内没有请求记录。') : '服务端请求追踪当前不可用。' }}</td></tr></tbody>
      </table></div>
      <div v-if="selectedRequest" class="request-details"><h3>所选请求详情</h3><dl><template v-for="[label,value] in details" :key="label"><dt>{{ label }}</dt><dd>{{ value }}</dd></template></dl>
        <details v-if="selectedRequest.stack?.length"><summary>异常调用栈</summary><pre>{{ JSON.stringify(selectedRequest.stack, null, 2) }}</pre></details>
      </div>
      <p v-if="selectedRequest" class="muted small">已选中 {{ selectedRequest.request_id }}，复制诊断证据将仅包含此请求。<button class="link-btn" @click="selectedRequest = null">取消选择</button></p>
    </div>

    <div class="card panel">
      <div class="panel-head"><div><h2>当前浏览器加载记录</h2><p>仅在当前标签页内存保留最近 {{ browserTrace.capacity }} 条；刷新或退出登录后清空，不记录令牌、请求正文或查询参数。</p></div>
        <div class="diagnostic-actions"><button class="btn compact" @click="refreshBrowserTrace">更新记录</button><button class="btn compact" @click="copy(browserTraceSnapshot(), '浏览器记录')">复制</button><button class="btn compact" @click="downloadEvidence(browserTraceSnapshot(), 'cpo-browser-trace.json')">下载</button><button class="btn compact" @click="clearTrace">清空</button></div>
      </div>
      <div class="table-wrap"><table class="browser-table"><thead><tr><th>时间</th><th>事件</th><th>页面 / 接口</th><th>请求 ID</th><th>耗时</th><th>结果</th></tr></thead>
        <tbody><tr v-for="(event,index) in [...browserTrace.events].reverse()" :key="`${event.timestamp}-${index}`"><td>{{ time(event.timestamp) }}</td><td>{{ event.event }}<small v-if="event.stage">{{ event.stage === 'data' ? '数据已渲染' : '页面框架已渲染' }}</small></td><td>{{ event.endpoint || event.page_path }}</td><td><button v-if="event.request_id" class="link-btn mono" @click="filters.request_id = event.request_id; copy(event.request_id, '请求 ID')">{{ event.request_id }}</button><span v-else>—</span></td><td>{{ ms(event.duration_ms) }}</td><td>{{ event.status_code ?? event.outcome ?? '—' }}</td></tr>
          <tr v-if="!browserTrace.events.length"><td colspan="6" class="empty-records">当前标签页暂无加载记录。</td></tr>
        </tbody>
      </table></div>
    </div>
  </section>
</template>

<style scoped>
.diagnostics-page{max-width:1700px}.diagnostics-page .panel-head{align-items:center;flex-wrap:wrap;gap:10px}.diagnostic-message{padding:10px 12px;border:1px solid #dce8f7;background:#f7fbff;color:#3268d8;border-radius:8px;font-size:12px}.diagnostic-message.error{background:#fff6ef;border-color:#f2d6b5;color:#a45f16}.system-grid{display:grid;grid-template-columns:1fr 2fr 1fr;gap:12px;margin-top:14px}.system-grid>div{background:#f8fafc;border:1px solid #edf0f4;border-radius:8px;padding:12px}.system-grid span,.system-grid small{display:block;font-size:11px;color:#7b8495}.system-grid strong{display:block;margin:6px 0;font-size:14px;overflow-wrap:anywhere}.mono{font-family:ui-monospace,SFMono-Regular,monospace}.cache-details{font-size:12px;margin-top:14px}.cache-details summary{cursor:pointer;color:#3268d8}.cache-details dl{display:grid;grid-template-columns:minmax(150px,1fr) 3fr;gap:8px;margin:12px 0 0}.cache-details dt{color:#7b8495}.cache-details dd{margin:0;overflow-wrap:anywhere}.diagnostic-actions{display:flex;gap:7px;flex-wrap:wrap}.diagnostic-filters{display:flex;align-items:flex-end;gap:9px;flex-wrap:wrap;margin:14px 0}.diagnostic-filters label{font-size:11px;color:#7b8495;display:flex;flex-direction:column;gap:5px}.diagnostic-filters input,.diagnostic-filters select{height:34px;max-width:240px;border:1px solid var(--line);border-radius:7px;padding:0 9px;background:#fff;color:#344054}.diagnostic-filters input[type=number]{width:100px}.requests-table{min-width:1370px}.requests-table tr{cursor:pointer}.requests-table tr.selected td{background:#f1f6ff}.requests-table small,.browser-table small{display:block;margin-top:6px;font-size:10px;color:#7b8495}.request-id{display:inline-block;max-width:260px;overflow-wrap:anywhere;white-space:normal}.revision{max-width:260px;overflow-wrap:anywhere}.requests-table td{vertical-align:top}.request-details{padding:12px;border:1px solid #edf0f4;border-radius:8px;margin-top:12px;font-size:12px}.request-details h3{margin:0 0 10px;font-size:13px}.request-details dl{display:grid;grid-template-columns:160px 1fr;gap:8px}.request-details dt{color:#7b8495}.request-details dd{margin:0;overflow-wrap:anywhere}.request-details pre{overflow:auto;white-space:pre-wrap;color:#536276}.request-details summary{cursor:pointer;color:#3268d8}.empty-records{text-align:center;color:#7b8495;height:90px}.browser-table{min-width:1050px}.browser-table .link-btn{font-size:11px;overflow-wrap:anywhere}.btn:disabled{opacity:.6;cursor:default}@media(max-width:760px){.system-grid{grid-template-columns:1fr}.diagnostic-filters label{max-width:100%}.cache-details dl{grid-template-columns:1fr}}
</style>
