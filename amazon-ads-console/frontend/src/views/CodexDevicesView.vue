<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { getJsonStrict } from '../api/client'
import { sumTokens, percentLabel } from '../utils/codexUsage'
import { quotaDisplay, type AccountQuota } from '../utils/codexQuota'
import { confirmedShare, attributionMethod, allocationLabel, type Attribution } from '../utils/codexAttribution'
import { activityState, activityLabels, type ActivityDevice } from '../utils/codexActivity'
import CodexAccessPanel from '../components/CodexAccessPanel.vue'

type Device = ActivityDevice & { sourceKind?:string; currentWindowTokens?:number|string|null; currentWindowUnknownRequests?:number; deviceId:string; deviceName:string; platform:string; online:boolean; agentOnline:boolean; codexRunning:boolean; revoked:boolean; lastHeartbeatAt:string|null; lastRequestAt:string|null; totalTokens:number|string|null; todayTokens:number|string|null; inputTokens:number|null; outputTokens:number|null; requests:number; unknownRequests:number }
type Member = { userId:number; displayName:string; username:string; groupCode:string; groupName:string; personCode:string|null; roleCode:string; devices:Device[] }
type LedgerSource = {deviceId:string; userId:number; deviceName:string; displayName:string; roleCode:string; revoked:boolean; requests:number; measuredRequests:number; unknownRequests:number; cachedUnknownRequests:number; reasoningUnknownRequests:number; totalTokens:number|string|null; inputTokens:number|string|null; outputTokens:number|string|null; cachedTokens:number|string|null; reasoningTokens:number|string|null}
type Ledger = {status:string; scope:string; accountCoverage:string; startedAt:string|null; throughAt:string; totals:Omit<LedgerSource,'deviceId'|'userId'|'deviceName'|'displayName'|'roleCode'|'revoked'>; pendingAccountingEvents:number; sources:LedgerSource[]; uncoveredSources:string[]}
type Overview = { activityRecentSeconds:number; accountAttribution?:Attribution; recordedHistory?:Ledger; ledger?:Ledger; accountQuota?:AccountQuota; members:Member[]; serverTime:string; onlineTimeoutSeconds:number; timezone:string; statisticsAvailable:boolean; integrationStage?:string; deploymentTarget?:string; pendingAccountingEvents?:number }
const data = ref<Overview|null>(null)
const selectedId = ref<number|null>(null)
const search = ref('')
const group = ref('all')
const error = ref('')
const loading = ref(false)
const updatedAt = ref(0)
const now = ref(Date.now())
let timer: ReturnType<typeof setInterval>|undefined
let clock: ReturnType<typeof setInterval>|undefined
let stopped = false
const stale = computed(() => !!error.value || now.value - updatedAt.value > 45000)
// Use elapsed client time against the server clock; expire indicators on failed refreshes.
const deviceState = (d:Device) => activityState(d, Date.parse(data.value?.serverTime || '') + now.value - updatedAt.value,
  !!data.value?.statisticsAvailable && !stale.value, data.value?.activityRecentSeconds)
const isActive = (d:Device) => ['active','recent'].includes(deviceState(d))
const memberState = (m:Member) => m.devices.some(d=>deviceState(d)==='active') ? '正在使用' :
  m.devices.some(d=>deviceState(d)==='recent') ? '最近活跃' : stale.value || m.devices.some(d=>deviceState(d)==='unknown') ? '状态待确认' : m.devices.length ? '暂无近期请求' : '设备待接入'
const members = computed(() => data.value?.members || [])
const filtered = computed(() => members.value.filter(m => (group.value === 'all' || m.groupCode === group.value) &&
  `${m.displayName} ${m.personCode || ''} ${m.username} ${m.devices.map(d=>d.deviceName).join(' ')}`.toLowerCase().includes(search.value.toLowerCase())))
watch(filtered, items => { if (!items.some(m=>m.userId===selectedId.value)) selectedId.value = items[0]?.userId ?? null })
const selected = computed(() => members.value.find(m=>m.userId === selectedId.value))
const devices = computed(() => members.value.flatMap(m=>m.devices))
const activeCount = computed(() => devices.value.filter(isActive).length)
const selectedActive = computed(() => (selected.value?.devices || []).filter(isActive).length)
const sum = sumTokens
const ledgerScope = ref<'recorded'|'current'>('recorded')
const ledger = computed(() => ledgerScope.value === 'recorded' ? data.value?.recordedHistory : data.value?.ledger)
const ledgerActive = computed(() => ledger.value?.status === 'active' && !stale.value)
const quotaView = computed(() => quotaDisplay(data.value?.accountQuota, now.value, stale.value))
const accountFresh = computed(() => quotaView.value.fresh && data.value?.accountAttribution?.status === 'available')
const memberShare = (m:Member) => confirmedShare(data.value?.accountAttribution,m.userId,accountFresh.value)
const deviceShare = (d:Device) => accountFresh.value ? data.value?.accountAttribution?.deviceShares?.find(row=>row.deviceId===d.deviceId)?.usedPercent ?? 0 : null
const isHost = (m:Member) => m.devices.some(d=>d.sourceKind==='local-host')
const accountPercent = (field:'usedPercent'|'remainingPercent'|'confirmedPercent'|'unattributedPercent') => accountFresh.value ? data.value?.accountAttribution?.[field] ?? null : null
const unknownRequests = computed(() => devices.value.reduce((n,d) => n + d.unknownRequests, 0))
const number = (v:number|string|null) => v === null || !Number.isFinite(Number(v)) ? '—' : Number(v).toLocaleString('zh-CN')
const time = (v:string|null) => v ? new Date(v).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false}) : '尚未收到'
async function refresh() {
  if (loading.value) return
  loading.value = true
  try {
    const next = await getJsonStrict<Overview>('/codex/overview')
    if (stopped) return
    data.value = next
    if (!next.members.some(m=>m.userId === selectedId.value)) selectedId.value = next.members.find(m=>m.devices.some(d=>d.sourceKind==='local-host'))?.userId ?? next.members[0]?.userId ?? null
    updatedAt.value = Date.now()
    now.value = updatedAt.value
    error.value = ''
  } catch (e) { if (!stopped) error.value = e instanceof Error ? e.message : '暂时无法读取设备状态' }
  finally { loading.value = false }
}
function onVisible() { now.value = Date.now(); if (!document.hidden) void refresh() }
onMounted(() => { void refresh(); timer = setInterval(()=>{ if (!document.hidden) void refresh() },15000); clock = setInterval(()=>{now.value=Date.now()},1000); document.addEventListener('visibilitychange',onVisible) })
onUnmounted(() => { stopped = true; clearInterval(timer); clearInterval(clock); document.removeEventListener('visibilitychange',onVisible) })

</script>

<template>
  <main class="codex-page">
    <header class="page-heading">
      <div>
        <span class="eyebrow">CODEX · 团队设备</span>
        <h1>分发人员 &amp; 设备</h1>
        <p>账户总额度100% · 人员消耗归属 · rc.7 · 请求活动状态</p>
      </div>
      <button class="refresh" :disabled="loading" @click="refresh">{{ loading ? '刷新中…' : '刷新状态' }}</button>
    </header>

    <div v-if="error" class="error" role="alert">{{ error }}。使用状态暂不可确认。<button @click="refresh">重试</button></div>

    <div class="summary-grid">
      <div class="summary-card"><span>分发成员</span><strong>{{ data ? members.length : '—' }}<small> 人</small></strong></div>
      <div class="summary-card"><span>已登记设备</span><strong>{{ data?.statisticsAvailable ? devices.length : '—' }}<small> 台</small></strong></div>
      <div class="summary-card"><span><i class="dot" :class="{green:data?.statisticsAvailable && activeCount>0}"></i>活跃设备（近5分钟）</span><strong>{{ data?.statisticsAvailable && !stale ? activeCount : '—' }}<small> 台</small></strong></div>
      <div class="summary-card"><span>今日已计量 Token（可见来源）</span><strong>{{ number(sum(devices,'todayTokens')) }}</strong></div>
    </div>

    <div class="notes"><template v-if="data?.statisticsAvailable">按实际请求识别使用状态：正在处理为“正在使用”，近5分钟有请求为“最近活跃”，其余显示“暂无近期请求”。子设备无需运行心跳程序；暂无请求不表示电脑关机。<span v-if="data.pendingAccountingEvents"> {{ data.pendingAccountingEvents }} 条用量记录正在等待入库。</span></template><template v-else>尚未接入真实设备与用量。</template><span class="legend">绿点使用中或最近活跃 · 灰点暂无近期请求 · “—”暂无计量</span></div>

    <CodexAccessPanel :members="members" :selected-id="selectedId" @changed="refresh" />

    <section class="account-quota" aria-label="官方账户剩余额度">
      <div v-for="entry in quotaView.windows" :key="entry.key" class="quota-card">
        <span>{{ entry.title }} · 官方账户剩余</span>
        <strong>{{ percentLabel(entry.remainingPercent) }}</strong>
        <small>重置：{{ time(new Date(entry.resetsAt*1000).toISOString()) }}</small>
      </div>
      <div class="quota-card">
        <span>官方额度采集状态</span><strong>{{ quotaView.state }}</strong>
        <small>按官方实际返回的窗口展示；未返回的窗口不补成0%或无限额度。</small>
      </div>
    </section>
    <section class="summary-grid account-allocation" aria-label="本期账户额度归属">
      <div class="summary-card"><span>账户已用 · 总额度为100%</span><strong>{{ percentLabel(accountPercent('usedPercent')) }}</strong></div>
      <div class="summary-card"><span>账户剩余</span><strong>{{ percentLabel(accountPercent('remainingPercent')) }}</strong></div>
      <div class="summary-card"><span>已归属人员消耗（含估算）</span><strong>{{ percentLabel(accountPercent('confirmedPercent')) }}</strong></div>
      <div class="summary-card"><span>待归属消耗</span><strong>{{ percentLabel(accountPercent('unattributedPercent')) }}</strong></div>
    </section>
    <p v-if="data?.accountAttribution?.status==='reconciliation-required'" class="error">官方额度回调后与已确认记录不一致，归属待复核；暂不展示人员比例。</p>
    <p v-else-if="!accountFresh" class="notes">账户额度归属暂不可确认，请等待有效采集或核对归属配置。</p>
    <p v-if="data?.accountAttribution?.startedAt" class="usage-disclaimer">本期：{{ time(data.accountAttribution.startedAt) }} 至 {{ time(new Date((data.accountAttribution.resetsAt || 0)*1000).toISOString()) }}。0%表示暂无已归属额度消耗，不表示从未使用过模型。</p>
    <p class="usage-disclaimer">账户总额度为100%；人员已归属消耗＋待归属＝账户已用，另加账户剩余＝100%。后台每约2分钟自动核对：单一可见来源的额度增量自动推定归属，保留本人确认记录；并发按本统计区间各设备已计量总Token比例自动估算，刚开始执行尚无计量的设备自动等待回传；采集中断、身份不明或完全没有计量的部分单列。自动推定只覆盖已监测来源，包含额度取整及延迟的不确定性，不是官方逐设备账单。具体Token独立计量，不拿接入前或以前区间的Token重分历史消耗，也不将Token换算为账单金额。<span v-if="unknownRequests"> {{ unknownRequests }} 条请求或日志计量待核对。</span><span v-if="data?.accountQuota?.capturedAt"> 额度采集：{{ time(data.accountQuota.capturedAt) }}</span></p>

    <p v-if="data?.accountAttribution?.automaticMonitor" class="usage-disclaimer">自动归属：{{ data.accountAttribution.automaticMonitor.status==='active' && now-Date.parse(data.accountAttribution.automaticMonitor.capturedAt)<=300000 ? '运行中' : '已暂停或待核对' }} · 最近核对 {{ time(data.accountAttribution.automaticMonitor.capturedAt) }} · 本人确认 {{ percentLabel(data.accountAttribution.ownerConfirmedPercent ?? null) }} · 自动归属 {{ allocationLabel(data.accountAttribution.automaticPercent ?? null) }}（其中并发估算 {{ allocationLabel(data.accountAttribution.concurrentEstimatedPercent ?? null) }}）。<span v-if="data.accountAttribution.automaticMonitor.pendingSettlementPercent"> 等待计量后自动结算：{{ allocationLabel(data.accountAttribution.automaticMonitor.pendingSettlementPercent) }}。</span><span v-if="data.accountAttribution.partialConcurrentEstimate"> 部分估算包含尚未完整回传的计量，置信度较低；不会据此声称精确消耗。</span></p>

    <details class="ledger-panel" aria-label="统一入口用量账本">
      <summary>入口Token历史明细（不参与账户额度分摊）</summary>
      <div class="group-tabs ledger-tabs"><button :class="{active:ledgerScope==='recorded'}" @click="ledgerScope='recorded'">入口累计</button><button :class="{active:ledgerScope==='current'}" @click="ledgerScope='current'">入口账本启用后</button></div>
      <p v-if="!ledgerActive">{{ stale ? '读取中断，暂不展示账本占比' : ledgerScope === 'recorded' ? '尚无入口历史记录' : '尚未启用本期账本起点' }}</p>
      <template v-else-if="ledger">
        <p>{{ ledgerScope === 'recorded' ? '首次记录' : '统计起点' }}：{{ time(ledger.startedAt) }} · 截止：{{ time(ledger.throughAt) }}</p>
        <div class="summary-grid">
          <div class="summary-card"><span>{{ ledgerScope === 'recorded' ? '入口累计已计量 Token' : '本期已计量 Token' }}</span><strong>{{ number(ledger.totals.totalTokens) }}</strong></div>
          <div class="summary-card"><span>已计量 / 所选范围记录</span><strong>{{ ledger.totals.measuredRequests }} / {{ ledger.totals.requests }}</strong></div>
          <div class="summary-card"><span>未知用量请求</span><strong>{{ ledger.totals.unknownRequests }}</strong></div>
          <div class="summary-card"><span>等待补账</span><strong>{{ ledger.pendingAccountingEvents }}</strong></div>
        </div>
        <p>未覆盖：{{ ledger.uncoveredSources.join('、') }}。下表保留全部已记录入口Token，包含停用设备与已离职人员历史，不随人员搜索改变；不用于账户额度归属。未知用量与待补账单列。缓存明细缺失 {{ ledger.totals.cachedUnknownRequests }} 次、推理明细缺失 {{ ledger.totals.reasoningUnknownRequests }} 次；明细已知部分单列，不重复加进总Token。</p>
        <p v-if="!ledger.totals.requests && ledgerScope==='current'">启用后尚无新请求，可切到“入口累计”查看已记录Token消耗。</p>
        <div class="ledger-scroll"><table><thead><tr><th>人员 / 来源</th><th>输入</th><th>输出</th><th>缓存（输入内）</th><th>推理（输出内）</th><th>总Token</th><th>未知请求</th></tr></thead>
          <tbody><tr v-for="source in ledger.sources" :key="source.deviceId"><td>{{ source.displayName }} · {{ source.deviceName }}{{ source.revoked ? '（停用）' : '' }}</td><td>{{ number(source.inputTokens) }}</td><td>{{ number(source.outputTokens) }}</td><td>{{ number(source.cachedTokens) }}</td><td>{{ number(source.reasoningTokens) }}</td><td>{{ number(source.totalTokens) }}</td><td>{{ source.unknownRequests }}</td></tr></tbody></table></div>
      </template>
    </details>

    <div class="workspace">
      <section class="people-panel" aria-label="分发人员">
        <div class="panel-heading">
          <div class="heading-block"><h2>分发人员</h2><p>选择成员查看设备与用量</p></div>
          <span class="count-chip">{{ filtered.length }} 人</span>
        </div>
        <div class="people-filters">
          <input v-model="search" aria-label="搜索成员或设备" placeholder="搜索姓名、编码或设备" />
          <div class="group-tabs"><button v-for="g in [{key:'all',name:'全部'},{key:'operations',name:'运营组'},{key:'ai',name:'AI 小组'}]" :key="g.key" :class="{active:group===g.key}" @click="group=g.key">{{ g.name }}</button></div>
        </div>
        <div class="people-list">
          <button v-for="m in filtered" :key="m.userId" class="person" :class="{selected:m.userId===selectedId}" @click="selectedId=m.userId"><span class="avatar">{{ m.displayName.slice(-2) }}</span><span class="person-info"><strong>{{ m.displayName }} <small>{{ m.personCode || '管理层' }}</small></strong><span>{{ m.groupName }} · {{ data?.statisticsAvailable ? `${m.devices.length} 台设备 · ${memberState(m)}` : '设备待接入' }}</span><span v-if="data?.statisticsAvailable" class="share-line">已归属占账户额度 <b>{{ allocationLabel(memberShare(m)) }}</b></span></span><i class="dot" :class="{green:m.devices.some(isActive)}" :aria-label="memberState(m)"></i></button>
          <p v-if="!filtered.length" class="empty">{{ loading ? '正在读取人员名单…' : '没有匹配的成员' }}</p>
        </div>
      </section>

      <section class="devices-panel" aria-label="人员设备与用量">
        <template v-if="selected">
          <div class="panel-heading">
            <div class="heading-block"><h2>{{ selected.displayName }}<span class="group-badge">{{ selected.groupName }}</span></h2><p>{{ selected.username }}<span v-if="selected.personCode"> · {{ selected.personCode }}</span><span v-if="selected.roleCode==='management'"> · 保留管理权限</span></p></div>
            <span class="status-chip" :class="{live:selectedActive>0}">{{ stale ? '状态待确认' : selected.devices.length ? `${selectedActive} / ${selected.devices.length} 活跃` : '设备待分发' }}</span>
          </div>
          <div class="member-totals">
            <div><span>今日已计量</span><strong>{{ number(sum(selected.devices,'todayTokens')) }} <small>Token</small></strong></div>
            <div><span>{{ isHost(selected) ? '本期本机已计量' : '历史累计已计量' }}</span><strong>{{ number(sum(selected.devices,'totalTokens')) }} <small>Token</small></strong></div>
            <div class="share-total"><span>已归属占账户总额度</span><strong>{{ allocationLabel(memberShare(selected)) }}</strong><span class="share-track" aria-hidden="true"><i :style="{width:`${memberShare(selected) ?? 0}%`}"></i></span><small>分母：本期官方账户额度100% · {{ attributionMethod(data?.accountAttribution, selected.userId) }}</small></div>
          </div>
          <div v-if="!selected.devices.length" class="empty-device">
            <svg class="monitor-icon" viewBox="0 0 48 40" fill="none" aria-hidden="true"><rect x="2" y="2" width="44" height="29" rx="5" stroke="currentColor" stroke-width="2.4"/><path d="M17 38h14M24 31v7M10 9h10" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"/></svg>
            <h3>尚未接入设备</h3>
            <p>日本代理服务器部署并完成设备分发后，<br />这里将显示 {{ selected.displayName }} 的设备状态和实际用量。</p>
          </div>
          <div v-else class="device-list">
            <article v-for="d in selected.devices" :key="d.deviceId" class="device-card">
              <header><div><h3>{{ d.deviceName }}</h3><p>{{ d.platform || '未填写系统' }}</p></div><span class="connection"><i class="dot" :class="{green:isActive(d)}"></i>{{ activityLabels[deviceState(d)] }}<template v-if="deviceState(d)==='active'"> · {{ d.activeRequests }} 个请求</template></span></header>
              <div class="device-stats"><div><span>今日 Token</span><strong>{{ number(d.todayTokens) }}</strong></div><div><span>{{ d.sourceKind==='local-host' ? '本期本机 Token' : '累计入口 Token' }}</span><strong>{{ number(d.totalTokens) }}</strong></div><div><span>{{ d.sourceKind==='local-host' ? '本期计量事件' : '累计请求' }}</span><strong>{{ d.requests }}</strong></div></div>
              <p class="heartbeat-help">本期已归属占账户总额度：{{ allocationLabel(deviceShare(d)) }}（含自动推定／并发估算，详情见人员归属依据）</p>
              <p class="heartbeat-help">本期已计量Token：{{ number(d.currentWindowTokens ?? null) }}<span v-if="d.sourceKind==='local-host'"> · 按本机日志事件计量，仅覆盖已扫描本机会话</span><span v-if="d.currentWindowUnknownRequests"> · 本期{{ d.currentWindowUnknownRequests }}处用量待核对</span></p>
              <p class="heartbeat-help">{{ d.sourceKind==='local-host' ? '主设备按已有本机采集的模型用量事件判断最近活跃。' : '服务器按设备独立 Key 识别请求，结束后自动记录实际 Token；重启电脑后继续使用即可。' }}</p>
              <footer><span>{{ d.sourceKind==='local-host' ? '最后用量事件' : '最后使用时间' }}：{{ time(d.lastActivityAt ?? null) }}<br /><template v-if="d.sourceKind==='local-host'">本机采集：{{ time(d.lastHeartbeatAt) }}</template><template v-else>最近请求结束：{{ time(d.lastRequestAt) }}</template><br v-if="d.unknownRequests" /><span v-if="d.unknownRequests">{{ d.unknownRequests }} {{ d.sourceKind==='local-host' ? '处日志用量边界待核对' : '次请求未返回Token，暂未计入用量' }}</span></span></footer>
            </article>
          </div>
        </template>
        <p v-else class="empty">{{ loading ? '正在加载…' : '请选择一位成员' }}</p>
      </section>
    </div>

    <p class="updated">额度归属 rc.7 · 请求活动状态 · 每 15 秒刷新 · 时间以北京时间显示<span v-if="data"> · 最近更新 {{ time(data.serverTime) }}</span></p>
  </main>
</template>

<style scoped>.codex-page{padding:18px 24px 20px;max-width:1600px;margin:auto;color:#233247;text-align:left}
.page-heading{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;margin-bottom:12px}
.eyebrow{font-size:10px;letter-spacing:1.2px;color:#8190a5}
.page-heading h1{font-size:20px;letter-spacing:-.3px;margin:4px 0;color:#1b2a3d}
.page-heading p{margin:0;font-size:12px;color:#7b8798}
.refresh{padding:7px 14px;border:1px solid #d5dfec;background:#fff;border-radius:999px;color:#3e5e87;cursor:pointer;font-size:12px;flex-shrink:0}
.refresh:hover{border-color:#b9cde4;color:#25537f}
.refresh:disabled{opacity:.5;cursor:default}

.summary-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}
.summary-card{display:flex;flex-direction:column;justify-content:space-between;gap:8px;min-height:64px;padding:10px 14px;background:#fff;border:1px solid #e2e8f0;border-radius:11px}
.summary-card span{display:flex;align-items:center;gap:7px;font-size:11px;color:#7a899a}
.summary-card strong{font-size:20px;line-height:1.15;font-weight:650;font-variant-numeric:tabular-nums;color:#1b2a3d}
.summary-card small{font-size:11px;color:#8a96a7;font-weight:400;margin-left:2px}

.notes{margin-top:9px;padding:7px 12px;border:1px solid #e3eaf3;border-radius:9px;background:#f7fafd;color:#71849c;font-size:11px;line-height:1.6}
.notes .legend{margin-left:10px;color:#94a2b4}

.workspace{display:grid;grid-template-columns:300px minmax(0,1fr);gap:12px;align-items:stretch;height:clamp(300px,calc(100vh - 330px),380px);margin-top:12px}
.people-panel,.devices-panel{display:flex;flex-direction:column;min-width:0;min-height:0;background:#fff;border:1px solid #dfe6ef;border-radius:12px;overflow:hidden}
.panel-heading{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;padding:12px 18px 10px;border-bottom:1px solid #edf0f5}
.heading-block{min-width:0}
.heading-block h2{margin:0;font-size:15px;line-height:20px;color:#1b2a3d}
.heading-block p{margin:4px 0 0;font-size:10px;line-height:14px;color:#7b8798;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.count-chip,.status-chip{flex-shrink:0;height:20px;padding:0 9px;border-radius:999px;font-size:10px;line-height:18px;border:1px solid #e3e9f1;background:#f6f9fc;color:#7d8b9d;white-space:nowrap}
.status-chip.live{background:#effaf4;border-color:#cdeedb;color:#1d8a5b}
.group-badge{display:inline-block;margin-left:8px;vertical-align:1px;font-size:10px;font-weight:400;line-height:14px;padding:1px 8px;border-radius:999px;background:#f0f4fa;color:#7689a1}

.people-filters{padding:9px 12px 10px;border-bottom:1px solid #f2f5f9}
.people-filters input{width:100%;padding:7px 10px;border:1px solid #e1e7ee;border-radius:8px;background:#f8fafc;font-size:12px;color:#34465b;outline:none}
.people-filters input:focus{border-color:#86b6f3;background:#fff}
.group-tabs{display:flex;gap:2px;padding-top:7px}
.group-tabs button{border:0;background:transparent;color:#7a8798;cursor:pointer;padding:4px 10px;border-radius:999px;font-size:11px}
.group-tabs button.active{background:#eaf3ff;color:#2568ba}

.people-list{flex:1;min-height:0;overflow-y:auto;padding:5px}
.person{display:flex;align-items:center;gap:9px;width:100%;text-align:left;background:#fff;border:1px solid transparent;border-radius:9px;padding:7px 9px;cursor:pointer;margin:1px 0}
.person:hover{background:#f6f9fd}
.person.selected{background:#f0f6ff;border-color:#d3e4fc}
.avatar{width:30px;height:30px;display:grid;place-items:center;border-radius:9px;background:#edf1f6;color:#60758d;font-size:11px;flex-shrink:0}
.person.selected .avatar{background:#dfeaff;color:#3169b4}
.person-info{flex:1;min-width:0}
.person-info strong{display:block;font-size:12px;font-weight:600;color:#34465b;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.person-info strong small{font-size:10px;font-weight:400;color:#8e9aae;margin-left:4px}
.person-info>span{display:block;font-size:10px;color:#97a1ae;margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.dot{display:inline-block;width:7px;height:7px;border-radius:50%;background:#b6bfca;flex-shrink:0}
.dot.green{background:#34b774;box-shadow:0 0 0 3px rgba(52,183,116,.10)}

.member-totals{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;padding:12px 18px;border-bottom:1px solid #edf0f5}
.member-totals span{display:block;font-size:10px;color:#95a0af}
.member-totals strong{display:block;margin-top:4px;font-size:20px;font-weight:600;font-variant-numeric:tabular-nums;color:#1b2a3d}
.member-totals small{font-size:10px;font-weight:400;color:#94a0af}

.empty-device{flex:1;min-height:0;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:18px 20px;text-align:center}
.monitor-icon{width:38px;height:32px;color:#b6c4d8}
.empty-device h3{margin:12px 0 5px;font-size:14px;font-weight:500;color:#66778e}
.empty-device p{margin:0;font-size:11px;line-height:1.8;color:#94a0b0}

.device-list{flex:1;min-height:0;overflow-y:auto;display:grid;gap:9px;align-content:start;padding:12px 18px 14px}
.device-card{border:1px solid #e5ebf3;border-radius:10px;padding:12px 14px}
.device-card header{display:flex;align-items:center;justify-content:space-between;gap:12px}
.device-card h3{margin:0;font-size:13px;color:#1b2a3d}
.device-card header p{margin:3px 0 0;font-size:10px;color:#96a0af}
.connection{display:flex;align-items:center;gap:7px;font-size:10px;color:#7c8a9b;flex-shrink:0}
.device-stats{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;padding:10px 0}
.device-stats span{display:block;font-size:10px;color:#95a0af}
.device-stats strong{display:block;margin-top:4px;font-size:16px;font-weight:500;font-variant-numeric:tabular-nums;color:#1b2a3d}
.device-card footer{border-top:1px solid #f0f3f7;padding-top:8px;font-size:10px;line-height:1.7;color:#8f9aac;overflow-wrap:anywhere}

.updated{margin-top:9px;font-size:10px;color:#a3adba;text-align:right}
.error{border:1px solid #edd2bc;background:#fff9f0;border-radius:9px;font-size:11px;color:#a3773c;padding:9px 12px;margin-bottom:9px}
.error button{background:none;border:0;color:#98692a;cursor:pointer;margin-left:8px}
.empty{padding:30px 20px;text-align:center;color:#99a4b3;font-size:12px}

@media(max-width:1100px){
  .workspace{grid-template-columns:260px minmax(0,1fr)}
  .codex-page{padding:16px 18px 18px}
}
@media(max-width:760px){
  .workspace{grid-template-columns:1fr;height:auto}
  .people-list{max-height:280px}
  .device-list{max-height:420px}
  .summary-grid{grid-template-columns:repeat(2,minmax(0,1fr))}
  .page-heading h1{font-size:19px}
  .codex-page{padding:14px 12px 18px}
  .notes .legend{display:block;margin-left:0}
  .updated{text-align:left;line-height:1.7}
}

.usage-controls{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-top:10px;font-size:11px;color:#63778e}
.usage-controls>div{display:flex;gap:3px;padding:3px;border-radius:8px;background:#edf2f8;flex-shrink:0}
.usage-controls button{border:0;border-radius:6px;padding:4px 12px;background:transparent;color:#667c94;cursor:pointer}
.usage-controls button.active{background:#fff;color:#2568ba;box-shadow:0 1px 3px #d6dfeb}
.usage-disclaimer{font-size:10px;line-height:1.6;color:#8a97a6;margin:5px 0 0}
.person-info>.share-line{color:#6c829b}.share-line b{color:#376eaa;font-weight:600}
.share-total>small{display:block;font-size:10px;color:#8999aa;margin-top:4px}
.share-track{display:block!important;height:4px;border-radius:4px;background:#e8eff8;margin-top:6px;overflow:hidden}
.share-track i{display:block;height:100%;background:#5b94d7;border-radius:4px}
.heartbeat-help{font-size:10px;color:#8796a8;line-height:1.6;margin:8px 0}

.account-quota{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin-top:10px}
.quota-card{display:flex;flex-direction:column;gap:5px;background:#fff;border:1px solid #dce7f3;border-radius:10px;padding:11px 15px}
.quota-card>span{font-size:11px;color:#70849a}.quota-card strong{font-size:23px;color:#285e97}.quota-card small{font-size:10px;color:#8393a5}
</style>

<style scoped>.ledger-panel{margin:14px 0;padding:14px;border:1px solid #e2e8f0;border-radius:11px;background:#fff}.ledger-panel h2{font-size:15px;margin:0 0 8px}.ledger-panel p{font-size:12px;color:#71849c;line-height:1.7}.ledger-scroll{overflow-x:auto}.ledger-scroll table{width:100%;font-size:12px;border-collapse:collapse;white-space:nowrap}.ledger-scroll td,.ledger-scroll th{padding:9px;text-align:left;border-bottom:1px solid #edf1f7}</style>

<style scoped>.ledger-tabs{max-width:260px;margin:8px 0}</style>

<style scoped>.account-allocation{margin-top:10px}.ledger-panel summary{cursor:pointer;font-size:13px;color:#647b96}.account-allocation .summary-card strong{color:#285f98}</style>
