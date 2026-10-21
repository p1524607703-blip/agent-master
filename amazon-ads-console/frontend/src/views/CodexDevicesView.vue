<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { getJsonStrict } from '../api/client'
import { sumTokens, usageShare, percentLabel } from '../utils/codexUsage'

type Device = { deviceId:string; deviceName:string; platform:string; online:boolean; agentOnline:boolean; codexRunning:boolean; revoked:boolean; lastHeartbeatAt:string|null; lastRequestAt:string|null; totalTokens:number|string|null; todayTokens:number|string|null; inputTokens:number|null; outputTokens:number|null; requests:number; unknownRequests:number }
type Member = { userId:number; displayName:string; username:string; groupCode:string; groupName:string; personCode:string|null; roleCode:string; devices:Device[] }
type QuotaWindow = { usedPercent:number; remainingPercent:number; windowDurationMins:number; resetsAt:number }
type AccountQuota = { status:string; capturedAt?:string; primary:QuotaWindow|null; secondary:QuotaWindow|null; accountTotalTokens?:number|null; tokenTotalScope?:string }
type Overview = { accountQuota?:AccountQuota; members:Member[]; serverTime:string; onlineTimeoutSeconds:number; timezone:string; statisticsAvailable:boolean; integrationStage?:string; deploymentTarget?:string; pendingAccountingEvents?:number }
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
// Expire green indicators locally even if a refresh fails or the tab resumes after sleep.
const isOnline = (d:Device) => !!data.value?.statisticsAvailable && !stale.value && !d.revoked && !!d.lastHeartbeatAt &&
  !!data.value && (Date.parse(data.value.serverTime) + now.value - updatedAt.value - Date.parse(d.lastHeartbeatAt)) <= data.value.onlineTimeoutSeconds * 1000 && d.agentOnline
const members = computed(() => data.value?.members || [])
const filtered = computed(() => members.value.filter(m => (group.value === 'all' || m.groupCode === group.value) &&
  `${m.displayName} ${m.personCode || ''} ${m.username} ${m.devices.map(d=>d.deviceName).join(' ')}`.toLowerCase().includes(search.value.toLowerCase())))
watch(filtered, items => { if (!items.some(m=>m.userId===selectedId.value)) selectedId.value = items[0]?.userId ?? null })
const selected = computed(() => members.value.find(m=>m.userId === selectedId.value))
const devices = computed(() => members.value.flatMap(m=>m.devices))
const onlineCount = computed(() => devices.value.filter(isOnline).length)
const selectedOnline = computed(() => (selected.value?.devices || []).filter(isOnline).length)
const sum = sumTokens
// A monitored-device subtotal is never an account-wide denominator.
const accountTotal = computed(() => data.value?.accountQuota?.tokenTotalScope === 'verified-account-global' ? data.value.accountQuota.accountTotalTokens ?? null : null)
const accountShare = (m:Member) => usageShare(sum(m.devices, 'totalTokens'), accountTotal.value)
const quotaFresh = computed(() => !!data.value?.accountQuota?.capturedAt && data.value.accountQuota.status === 'available' && !stale.value && now.value - Date.parse(data.value.accountQuota.capturedAt) <= 300000)
const quotaMessages:Record<string,string> = {unconfigured:'尚未接入',unavailable:'读取失败',stale:'数据过期'}
const quotaState = computed(() => quotaMessages[data.value?.accountQuota?.status || 'unconfigured'] || '数据过期')
const quotaTitle = (w:QuotaWindow|null|undefined, fallback:string) => w?.windowDurationMins === 300 ? '5小时额度' : w?.windowDurationMins === 10080 ? '每周额度' : w ? `${w.windowDurationMins}分钟额度` : fallback
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
    if (!next.members.some(m=>m.userId === selectedId.value)) selectedId.value = next.members[0]?.userId ?? null
    updatedAt.value = Date.now()
    now.value = updatedAt.value
    error.value = ''
  } catch (e) { if (!stopped) error.value = e instanceof Error ? e.message : '暂时无法读取设备状态' }
  finally { loading.value = false }
}
function onVisible() { now.value = Date.now(); if (!document.hidden) void refresh() }
onMounted(() => { void refresh(); timer = setInterval(()=>{ if (!document.hidden) void refresh() },30000); clock = setInterval(()=>{now.value=Date.now()},1000); document.addEventListener('visibilitychange',onVisible) })
onUnmounted(() => { stopped = true; clearInterval(timer); clearInterval(clock); document.removeEventListener('visibilitychange',onVisible) })

</script>

<template>
  <main class="codex-page">
    <header class="page-heading">
      <div>
        <span class="eyebrow">CODEX · 团队设备</span>
        <h1>分发人员 &amp; 设备</h1>
        <p>按人员查看设备连接与 Token 用量</p>
      </div>
      <button class="refresh" :disabled="loading" @click="refresh">{{ loading ? '刷新中…' : '刷新状态' }}</button>
    </header>

    <div v-if="error" class="error" role="alert">{{ error }}。状态暂不可确认，已暂停显示在线绿点。<button @click="refresh">重试</button></div>

    <div class="summary-grid">
      <div class="summary-card"><span>分发成员</span><strong>{{ data ? members.length : '—' }}<small> 人</small></strong></div>
      <div class="summary-card"><span>已登记设备</span><strong>{{ data?.statisticsAvailable ? devices.length : '—' }}<small> 台</small></strong></div>
      <div class="summary-card"><span><i class="dot" :class="{green:data?.statisticsAvailable && onlineCount>0}"></i>在线设备</span><strong>{{ data?.statisticsAvailable && !stale ? onlineCount : '—' }}<small> 台</small></strong></div>
      <div class="summary-card"><span>本入口今日已计量 Token</span><strong>{{ number(sum(devices,'todayTokens')) }}</strong></div>
    </div>

    <div class="notes"><template v-if="data?.statisticsAvailable">测试接入 · {{ data.deploymentTarget }}。绿点须同时收到有效心跳和客户端运行状态；不代表正在执行任务。<span v-if="data.pendingAccountingEvents"> {{ data.pendingAccountingEvents }} 条用量记录正在等待入库。</span></template><template v-else>筹备阶段 · 最终由日本代理服务器统一部署分发；公司 M4 仅用于测试，尚未接入真实设备与用量。</template><span class="legend">绿点在线 · 灰点离线或未接入 · “—”暂无计量</span></div>

    <section class="account-quota" aria-label="官方账户剩余额度">
      <div v-for="entry in [{key:'primary',name:'5小时额度'},{key:'secondary',name:'每周额度'}]" :key="entry.key" class="quota-card">
        <span>{{ quotaTitle(entry.key==='primary' ? data?.accountQuota?.primary : data?.accountQuota?.secondary,entry.name) }} · 官方账户剩余</span>
        <template v-if="quotaFresh && (entry.key==='primary' ? data?.accountQuota?.primary : data?.accountQuota?.secondary)">
          <strong>{{ percentLabel((entry.key==='primary' ? data?.accountQuota?.primary : data?.accountQuota?.secondary)?.remainingPercent ?? null) }}</strong>
          <small>重置：{{ time(new Date(((entry.key==='primary' ? data?.accountQuota?.primary : data?.accountQuota?.secondary)?.resetsAt ?? 0)*1000).toISOString()) }}</small>
        </template>
        <template v-else><strong>—</strong><small>{{ quotaFresh ? '当前未返回此额度窗口' : quotaState }}</small></template>
      </div>
    </section>
    <p class="usage-disclaimer">官方额度独立读取，不从Token反推。设备占账户总量需可信的全账户Token分母，目前无法核对，显示“—”；不会把设备小计强制归一为100%。<span v-if="unknownRequests"> {{ unknownRequests }} 次请求用量未知。</span><span v-if="data?.accountQuota?.capturedAt"> 额度采集：{{ time(data.accountQuota.capturedAt) }}</span></p>

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
          <button v-for="m in filtered" :key="m.userId" class="person" :class="{selected:m.userId===selectedId}" @click="selectedId=m.userId"><span class="avatar">{{ m.displayName.slice(-2) }}</span><span class="person-info"><strong>{{ m.displayName }} <small>{{ m.personCode || '管理层' }}</small></strong><span>{{ m.groupName }} · {{ data?.statisticsAvailable ? `${m.devices.length} 台设备` : '设备待接入' }}</span><span v-if="data?.statisticsAvailable" class="share-line">占账户总量 <b>{{ percentLabel(accountShare(m)) }}</b></span></span><i class="dot" :class="{green:m.devices.some(isOnline)}" :aria-label="m.devices.some(isOnline)?'在线':'离线或未接入'"></i></button>
          <p v-if="!filtered.length" class="empty">{{ loading ? '正在读取人员名单…' : '没有匹配的成员' }}</p>
        </div>
      </section>

      <section class="devices-panel" aria-label="人员设备与用量">
        <template v-if="selected">
          <div class="panel-heading">
            <div class="heading-block"><h2>{{ selected.displayName }}<span class="group-badge">{{ selected.groupName }}</span></h2><p>{{ selected.username }}<span v-if="selected.personCode"> · {{ selected.personCode }}</span><span v-if="selected.roleCode==='management'"> · 保留管理权限</span></p></div>
            <span class="status-chip" :class="{live:selectedOnline>0}">{{ selected.devices.length ? `${selectedOnline} / ${selected.devices.length} 在线` : '设备待分发' }}</span>
          </div>
          <div class="member-totals">
            <div><span>今日已计量</span><strong>{{ number(sum(selected.devices,'todayTokens')) }} <small>Token</small></strong></div>
            <div><span>累计已计量</span><strong>{{ number(sum(selected.devices,'totalTokens')) }} <small>Token</small></strong></div>
            <div class="share-total"><span>占账户累计Token</span><strong>{{ percentLabel(accountShare(selected)) }}</strong><span class="share-track" aria-hidden="true"><i :style="{width:`${accountShare(selected) ?? 0}%`}"></i></span><small>{{ accountTotal === null ? '全账户Token总量尚无法核对' : `账户已用 ${number(accountTotal)} Token` }}</small></div>
          </div>
          <div v-if="!selected.devices.length" class="empty-device">
            <svg class="monitor-icon" viewBox="0 0 48 40" fill="none" aria-hidden="true"><rect x="2" y="2" width="44" height="29" rx="5" stroke="currentColor" stroke-width="2.4"/><path d="M17 38h14M24 31v7M10 9h10" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"/></svg>
            <h3>尚未接入设备</h3>
            <p>日本代理服务器部署并完成设备分发后，<br />这里将显示 {{ selected.displayName }} 的设备状态和实际用量。</p>
          </div>
          <div v-else class="device-list">
            <article v-for="d in selected.devices" :key="d.deviceId" class="device-card">
              <header><div><h3>{{ d.deviceName }}</h3><p>{{ d.platform || '未填写系统' }}</p></div><span class="connection"><i class="dot" :class="{green:isOnline(d)}"></i>{{ d.revoked ? '已停用' : stale ? '状态待确认' : isOnline(d) ? (d.codexRunning ? '在线 · Codex运行中' : '设备在线 · Codex未运行') : d.lastHeartbeatAt ? '离线' : '尚无心跳' }}</span></header>
              <div class="device-stats"><div><span>今日 Token</span><strong>{{ number(d.todayTokens) }}</strong></div><div><span>累计 Token</span><strong>{{ number(d.totalTokens) }}</strong></div><div><span>累计请求</span><strong>{{ d.requests }}</strong></div></div>
              <p v-if="!d.lastHeartbeatAt" class="heartbeat-help">模型调用不自动上报在线；限时测试仅5分钟；需要持续在线时，请安装新包的持续在线检测组件。</p>
              <footer><span>最近心跳：{{ time(d.lastHeartbeatAt) }}<br />最近调用：{{ time(d.lastRequestAt) }}<br v-if="d.unknownRequests" /><span v-if="d.unknownRequests">{{ d.unknownRequests }} 次请求未返回 Token 数据，暂未计入用量</span></span></footer>
            </article>
          </div>
        </template>
        <p v-else class="empty">{{ loading ? '正在加载…' : '请选择一位成员' }}</p>
      </section>
    </div>

    <p class="updated">每 30 秒刷新 · 时间以北京时间显示<span v-if="data"> · 最近更新 {{ time(data.serverTime) }}</span></p>
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
