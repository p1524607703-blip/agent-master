<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { getJsonStrict } from '../api/client'
import { sumTokens, percentLabel } from '../utils/codexUsage'
import { quotaDisplay, type AccountQuota } from '../utils/codexQuota'
import { confirmedShare, attributionMethod, allocationLabel, type Attribution } from '../utils/codexAttribution'
import { activityState, activityLabels, type ActivityDevice } from '../utils/codexActivity'
import CodexAccessPanel from '../components/CodexAccessPanel.vue'
import CodexControlPanel from '../components/CodexControlPanel.vue'
import CodexQuotaBatches from '../components/CodexQuotaBatches.vue'
import CodexModelPanel from '../components/CodexModelPanel.vue'
type Device = ActivityDevice & { sourceKind?:string; currentWindowTokens?:number|string|null; currentWindowUnknownRequests?:number; deviceId:string; deviceName:string; platform:string; online:boolean; agentOnline:boolean; codexRunning:boolean; revoked:boolean; lastHeartbeatAt:string|null; lastRequestAt:string|null; totalTokens:number|string|null; todayTokens:number|string|null; inputTokens:number|null; outputTokens:number|null; requests:number; unknownRequests:number }
type Member = { userId:number; displayName:string; username:string; groupCode:string; groupName:string; personCode:string|null; roleCode:string; devices:Device[] }
type LedgerSource = {deviceId:string; userId:number; deviceName:string; displayName:string; roleCode:string; revoked:boolean; requests:number; measuredRequests:number; unknownRequests:number; cachedUnknownRequests:number; reasoningUnknownRequests:number; totalTokens:number|string|null; inputTokens:number|string|null; outputTokens:number|string|null; cachedTokens:number|string|null; reasoningTokens:number|string|null}
type Ledger = {status:string; scope:string; accountCoverage:string; startedAt:string|null; throughAt:string; totals:Omit<LedgerSource,'deviceId'|'userId'|'deviceName'|'displayName'|'roleCode'|'revoked'>; pendingAccountingEvents:number; sources:LedgerSource[]; uncoveredSources:string[]}
type Overview = { activityRecentSeconds:number; accountAttribution?:Attribution; recordedHistory?:Ledger; ledger?:Ledger; accountQuota?:AccountQuota; members:Member[]; serverTime:string; onlineTimeoutSeconds:number; timezone:string; statisticsAvailable:boolean; integrationStage?:string; deploymentTarget?:string; pendingAccountingEvents?:number }

const data=ref<Overview|null>(null),selectedId=ref<number|null>(null),tab=ref<'people'|'usage'|'access'>('people')
const search=ref(''),group=ref('all'),error=ref(''),loading=ref(false),updatedAt=ref(0),now=ref(Date.now())
const control=ref<{activeRequests:number;queuedRequests:number}|null>(null),pendingApprovals=ref<number|null>(null),modelRevision=ref(0)
const selectedDeviceId=ref<string|null>(null),drawer=ref<HTMLDialogElement|null>(null)
const chartScope=ref<'todayTokens'|'currentWindowTokens'>('todayTokens'),ledgerScope=ref<'recorded'|'current'>('recorded')
let timer:ReturnType<typeof setInterval>|undefined,clock:ReturnType<typeof setInterval>|undefined,stopped=false
const sum=sumTokens
const stale=computed(()=>!!error.value||now.value-updatedAt.value>45000)
const members=computed(()=>data.value?.members||[]),devices=computed(()=>members.value.flatMap(m=>m.devices))
const filtered=computed(()=>members.value.filter(m=>(group.value==='all'||m.groupCode===group.value)&&`${m.displayName} ${m.personCode||''} ${m.devices.map(d=>d.deviceName).join(' ')}`.toLowerCase().includes(search.value.toLowerCase())))
watch(filtered,items=>{if(selectedId.value!==null&&!items.some(m=>m.userId===selectedId.value))selectedId.value=null})
const selected=computed(()=>members.value.find(m=>m.userId===selectedId.value))
const scopeDevices=computed(()=>selected.value?.devices||filtered.value.flatMap(m=>m.devices))
const hostDevices=computed(()=>scopeDevices.value.filter(d=>d.sourceKind==='local-host'))
const visibleIds=computed(()=>scopeDevices.value.map(d=>d.deviceId))
const selectedDevice=computed(()=>devices.value.find(d=>d.deviceId===selectedDeviceId.value))
const deviceNames=computed(()=>Object.fromEntries(members.value.flatMap(m=>m.devices.map(d=>[d.deviceId,`${m.displayName} · ${d.deviceName}`]))))
const deviceState=(d:Device)=>activityState(d,Date.parse(data.value?.serverTime||'')+now.value-updatedAt.value,!!data.value?.statisticsAvailable&&!stale.value,data.value?.activityRecentSeconds)
const activeCount=computed(()=>devices.value.filter(d=>deviceState(d)==='active').length)
const recentCount=computed(()=>devices.value.filter(d=>['active','recent'].includes(deviceState(d))).length)
const number=(v:number|string|null|undefined)=>v==null||!Number.isFinite(Number(v))?'—':Number(v).toLocaleString('zh-CN')
const compact=(v:number|string|null|undefined)=>v==null?'—':Number(v)>=1000000?`${(Number(v)/1000000).toFixed(1)}M`:Number(v)>=10000?`${(Number(v)/1000).toFixed(1)}K`:number(v)
const time=(v:string|null|undefined)=>v?new Date(v).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false}):'尚无记录'
const relative=(v:string|null|undefined)=>{if(!v)return '尚无记录';const s=Math.max(0,Math.floor((now.value-Date.parse(v))/1000));return s<60?'刚刚':s<3600?`${Math.floor(s/60)}分钟前`:s<86400?`${Math.floor(s/3600)}小时前`:time(v)}
const usage=computed(()=>Object.fromEntries(devices.value.map(d=>[d.deviceId,{today:stale.value?'—':compact(d.todayTokens),last:relative(d.lastActivityAt),activity:activityLabels[deviceState(d)]}])) )
const quotaView=computed(()=>quotaDisplay(data.value?.accountQuota,now.value,stale.value))
const accountFresh=computed(()=>quotaView.value.fresh&&data.value?.accountAttribution?.status==='available')
const memberShare=(m:Member)=>confirmedShare(data.value?.accountAttribution,m.userId,accountFresh.value)
const unknownRequests=computed(()=>devices.value.reduce((n,d)=>n+d.unknownRequests,0))
const ledger=computed(()=>ledgerScope.value==='recorded'?data.value?.recordedHistory:data.value?.ledger)
const ledgerActive=computed(()=>ledger.value?.status==='active'&&!stale.value)
const bars=computed(()=>members.value.map(m=>({member:m,value:sum(m.devices,chartScope.value)})).sort((a,b)=>Number(b.value??-1)-Number(a.value??-1)))
const barMax=computed(()=>Math.max(1,...bars.value.map(b=>Number(b.value??0))))
async function refresh(){
 if(loading.value)return;loading.value=true
 try{const next=await getJsonStrict<Overview>('/codex/overview');if(stopped)return;data.value=next;updatedAt.value=Date.now();now.value=updatedAt.value;error.value=''}
 catch{if(!stopped)error.value='状态更新中断，正在显示上次记录。'}finally{loading.value=false}
 try{const r=await getJsonStrict<{items:{device_id:string;auth_mode:string;approved_at:string|null;access_approved_at:string|null}[]}>('/codex/device-bindings');if(!stopped)pendingApprovals.value=new Set(r.items.filter(i=>!i.access_approved_at||(i.auth_mode==='hardware'&&!i.approved_at)).map(i=>i.device_id)).size}catch{if(!stopped)pendingApprovals.value=null}
}
async function showDevice(id:string){selectedDeviceId.value=id;await nextTick();if(!drawer.value?.open)drawer.value?.showModal()}
function accessFromDrawer(){drawer.value?.close();tab.value='access'}
function onVisible(){now.value=Date.now();if(!document.hidden)void refresh()}
onMounted(()=>{void refresh();timer=setInterval(()=>{if(!document.hidden)void refresh()},15000);clock=setInterval(()=>{now.value=Date.now()},1000);document.addEventListener('visibilitychange',onVisible)})
onUnmounted(()=>{stopped=true;clearInterval(timer);clearInterval(clock);document.removeEventListener('visibilitychange',onVisible)})
</script>

<template>
 <main class="codex-page">
  <header class="page-heading">
<div>
<span class="eyebrow">CODEX · 团队使用中心</span>
<h1>个人与设备</h1>
</div>
<div class="heading-actions">
<span class="freshness" :class="{warning:stale}">{{stale?'等待更新':'数据已更新'}}<small v-if="data">{{relative(data.serverTime)}}</small>
</span>
<button :disabled="loading" @click="refresh">{{loading?'刷新中…':'刷新'}}</button>
<button class="primary" @click="tab='access'">接入管理</button>
</div>
</header>
  <p v-if="error" class="alert" role="alert">{{error}} 使用状态暂不可确认。<button @click="refresh">重新读取</button>
</p>
  <section class="account-strip" aria-label="共享账户额度">
<div class="account-label">
<strong>共享账户额度</strong>
<small>{{quotaView.state}}</small>
</div>
<div v-for="entry in quotaView.windows" :key="entry.key" class="quota-window">
<div>
<span>{{entry.title}}</span>
<strong>{{percentLabel(entry.remainingPercent)}} <small>剩余</small>
</strong>
</div>
<div class="track" role="progressbar" :aria-label="`${entry.title} 剩余额度`" :aria-valuenow="entry.remainingPercent??undefined" aria-valuemin="0" aria-valuemax="100">
<i :class="{low:(entry.remainingPercent??100)<20}" :style="{width:`${Math.max(0,Math.min(100,entry.remainingPercent??0))}%`}">
</i>
</div>
<small>重置：{{time(new Date(entry.resetsAt*1000).toISOString())}}</small>
</div>
<p v-if="!quotaView.windows.length">等待官方额度采集，未返回的窗口不推算。</p>
</section>
  <section class="summary-grid" aria-label="运行概况">
<div>
<span>正在处理</span>
<strong>{{!stale&&control?control.activeRequests:'—'}}<small> 请求</small>
</strong>
<small>{{stale?'使用状态待确认':`${activeCount} 台设备正在使用`}}</small>
</div>
<div>
<span>排队等待</span>
<strong>{{!stale&&control?control.queuedRequests:'—'}}<small> 请求</small>
</strong>
<small>到达并发上限后自动排队</small>
</div>
<div>
<span>活跃设备</span>
<strong>{{!stale&&data?recentCount:'—'}}<small> / {{devices.length}} 台</small>
</strong>
<small>近 5 分钟有使用记录</small>
</div>
<div>
<span>今日已计量 Token</span>
<strong :title="number(sum(devices,'todayTokens'))">{{stale?'—':compact(sum(devices,'todayTokens'))}}</strong>
<small>中转入口与已采集本机来源</small>
</div>
</section>
  <div v-if="pendingApprovals || unknownRequests || data?.pendingAccountingEvents" class="attention">
<button v-if="pendingApprovals" @click="tab='access'">{{pendingApprovals}} 项接入待批准 →</button>
<button v-if="unknownRequests || data?.pendingAccountingEvents" @click="tab='usage'">用量待核对 {{unknownRequests}} 条 · 待入库 {{data?.pendingAccountingEvents??0}} 条 →</button>
</div>
  <nav class="page-tabs" aria-label="设备页面分区">
<button v-for="t in [{id:'people',name:'人员与设备'},{id:'usage',name:'用量分析'},{id:'access',name:'接入管理'}]" :key="t.id" :class="{active:tab===t.id}" :aria-current="tab===t.id?'page':undefined" @click="tab=t.id as typeof tab">{{t.name}}<span v-if="t.id==='access'&&pendingApprovals">{{pendingApprovals}}</span>
</button>
</nav>
  <div v-show="tab==='people'" class="workspace">
   <aside class="people-panel">
<div class="panel-heading">
<h2>人员</h2>
<span>{{filtered.length}} 人</span>
</div>
<input v-model="search" aria-label="搜索成员或设备" placeholder="搜索姓名或设备" />
<div class="group-tabs">
<button v-for="g in [{key:'all',name:'全部'},{key:'operations',name:'运营组'},{key:'ai',name:'AI 小组'}]" :key="g.key" :class="{active:group===g.key}" @click="group=g.key">{{g.name}}</button>
</div>
<button class="person all-people" :class="{selected:selectedId===null}" @click="selectedId=null">
<strong>全部人员</strong>
<small>查看当前筛选范围的设备</small>
</button>
<button v-for="m in filtered" :key="m.userId" class="person" :class="{selected:selectedId===m.userId}" @click="selectedId=m.userId">
<span class="avatar">{{m.displayName.slice(-2)}}</span>
<span>
<strong>{{m.displayName}}</strong>
<small>{{m.devices.length}} 台设备 · {{m.devices.some(d=>deviceState(d)==='active')?'正在使用':m.groupName}}</small>
<small :title="number(sum(m.devices,'todayTokens'))">今日 {{stale?'—':compact(sum(m.devices,'todayTokens'))}} Token</small>
</span>
</button>
<p v-if="!filtered.length" class="empty">没有匹配的人员或设备</p>
</aside>
   <section class="devices-panel">
<div class="device-context">
<header class="panel-heading">
<div>
<h2>{{selected?.displayName || '全部人员'}}<small v-if="selected">{{selected.groupName}}</small>
</h2>
<p>{{selected?'该人员名下的设备与用量':'当前筛选范围的设备 · 账户额度为团队共享'}}</p>
</div>
</header>
<div class="member-totals">
<div>
<span>今日已计量</span>
<strong :title="number(sum(scopeDevices,'todayTokens'))">{{stale?'—':compact(sum(scopeDevices,'todayTokens'))}}</strong>
</div>
<div>
<span>本期已计量</span>
<strong :title="number(sum(scopeDevices,'currentWindowTokens'))">{{stale?'—':compact(sum(scopeDevices,'currentWindowTokens'))}}</strong>
</div>
<div v-if="selected">
<span>占账户额度 <em>估算</em>
</span>
<strong :title="attributionMethod(data?.accountAttribution,selected.userId)">{{allocationLabel(memberShare(selected))}}</strong>
<small>{{attributionMethod(data?.accountAttribution,selected.userId)}}</small>
</div>
<div v-else>
<span>已登记设备</span>
<strong>{{scopeDevices.length}} <small>台</small>
</strong>
</div>
</div>
    </div>
    <CodexControlPanel :refresh-key="updatedAt" :visible-device-ids="visibleIds" :usage="usage" @changed="refresh" @detail="showDevice" @state="control=$event" />
<article v-for="d in hostDevices" :key="d.deviceId" class="host-row">
<div>
<strong>{{d.deviceName}}</strong>
<small>本机直连采集 · {{activityLabels[deviceState(d)]}}</small>
</div>
<div>
<span>今日 {{stale?'—':compact(d.todayTokens)}} Token</span>
<small>最近使用 {{relative(d.lastActivityAt)}}</small>
</div>
<button @click="showDevice(d.deviceId)">详情</button>
</article>
    <p class="scope-note">使用状态按实际请求判断。“暂无近期请求”不表示电脑关机；启停仅控制中转接入，本机直连采集单独展示。</p>
   </section>
  </div>
  <section v-if="tab==='usage'" class="usage-page">
   <section class="surface">
<header class="panel-heading">
<div>
<h2>人员用量比较</h2>
<p>具体 Token 独立计量，所有人员使用同一时间口径</p>
</div>
<div class="segmented">
<button :class="{active:chartScope==='todayTokens'}" @click="chartScope='todayTokens'">今日</button>
<button :class="{active:chartScope==='currentWindowTokens'}" @click="chartScope='currentWindowTokens'">本期</button>
</div>
</header>
<div class="bars">
<button v-for="row in bars" :key="row.member.userId" class="bar-row" @click="selectedId=row.member.userId;tab='people'">
<span>{{row.member.displayName}}</span>
<span class="bar-track">
<i :style="{width:`${stale?0:Math.max(0,Number(row.value??0)/barMax*100)}%`}">
</i>
</span>
<strong :title="number(row.value)">{{stale?'—':compact(row.value)}}</strong>
</button>
</div>
</section>
   <section class="surface allocation">
<h2>本期账户额度归属 <em>估算</em>
</h2>
<p>与上方 Token 计量分开呈现；暂估已包含在人员归属中。</p>
<div class="allocation-numbers">
<div>
<span>账户已用</span>
<strong>{{percentLabel(accountFresh?data?.accountAttribution?.usedPercent??null:null)}}</strong>
</div>
<div>
<span>已归属人员（含暂估）</span>
<strong>{{percentLabel(accountFresh?data?.accountAttribution?.confirmedPercent??null:null)}}</strong>
</div>
<div>
<span>待归属</span>
<strong>{{percentLabel(accountFresh?data?.accountAttribution?.unattributedPercent??null:null)}}</strong>
</div>
</div>
<p v-if="!accountFresh" class="alert">额度归属暂不可确认，请等待采集恢复或复核。</p>
<details>
<summary>归属批次与修订记录</summary>
<CodexQuotaBatches :value="data?.accountAttribution" :names="deviceNames" :fresh="accountFresh && data?.accountAttribution?.batchMonitoring?.status==='active' && now-Date.parse(data?.accountAttribution?.batchMonitoring?.capturedAt||'')<=300000" />
</details>
</section>
   <details class="surface ledger-panel">
<summary>历史账本与 Token 明细</summary>
<div class="segmented">
<button :class="{active:ledgerScope==='recorded'}" @click="ledgerScope='recorded'">入口累计</button>
<button :class="{active:ledgerScope==='current'}" @click="ledgerScope='current'">账本启用后</button>
</div>
<p v-if="!ledgerActive">{{stale?'数据暂不可确认':'尚无该范围的记录'}}</p>
<template v-else-if="ledger">
<p>{{time(ledger.startedAt)}} 至 {{time(ledger.throughAt)}} · 总 Token {{number(ledger.totals.totalTokens)}} · 未知用量 {{ledger.totals.unknownRequests}} 条 · 等待补账 {{ledger.pendingAccountingEvents}} 条</p>
<div class="table-scroll">
<table>
<thead>
<tr>
<th>人员／来源</th>
<th>输入</th>
<th>输出</th>
<th>缓存（输入内）</th>
<th>推理（输出内）</th>
<th>总 Token</th>
</tr>
</thead>
<tbody>
<tr v-for="source in ledger.sources" :key="source.deviceId">
<td>{{source.displayName}} · {{source.deviceName}}<small v-if="source.revoked">已撤销 · 历史保留</small>
</td>
<td>{{number(source.inputTokens)}}</td>
<td>{{number(source.outputTokens)}}</td>
<td>{{number(source.cachedTokens)}}</td>
<td>{{number(source.reasoningTokens)}}</td>
<td>{{number(source.totalTokens)}}</td>
</tr>
</tbody>
</table>
</div>
<p>未覆盖：{{ledger.uncoveredSources.join('、')}}。账本保留停用设备和历史人员，范围不随人员筛选改变。</p>
</template>
</details>
   <details class="surface">
<summary>统计口径与采集状态</summary>
<p>官方额度可能迟报或取整，人员额度占比为估算，不能视作官方逐设备账单或费用。未知来源单列待归属，未知用量不填为 0。缓存与推理 Token 已分别包含在输入与输出中，不重复相加。</p>
<p>本机直连仅覆盖已扫描会话；子设备按独立 API Key 记录。多个实体设备共用一个 Key 会合并到同一登记。</p>
<p>本期起点 {{time(data?.accountAttribution?.startedAt)}} · 额度采集 {{time(data?.accountQuota?.capturedAt)}} · {{quotaView.updatePolicy}}</p>
</details>
  </section>
  <section v-if="tab==='access'" class="access-page">
<CodexModelPanel @changed="modelRevision++;refresh()" />
<CodexAccessPanel :members="members" :selected-id="selectedId" :external-refresh="modelRevision" @changed="refresh" />
</section>
  <dialog ref="drawer" class="device-drawer" @close="selectedDeviceId=null">
<template v-if="selectedDevice">
<header>
<div>
<span class="eyebrow">设备详情</span>
<h2>{{selectedDevice.deviceName}}</h2>
</div>
<button aria-label="关闭设备详情" @click="drawer?.close()">关闭</button>
</header>
<p>{{selectedDevice.platform}} · {{activityLabels[deviceState(selectedDevice)]}}</p>
<div class="drawer-stats">
<div>
<span>今日 Token</span>
<strong>{{number(selectedDevice.todayTokens)}}</strong>
</div>
<div>
<span>本期 Token</span>
<strong>{{number(selectedDevice.currentWindowTokens)}}</strong>
</div>
</div>
<p>最后使用 {{time(selectedDevice.lastActivityAt)}}</p>
<p v-if="selectedDevice.unknownRequests" class="alert">{{selectedDevice.unknownRequests}} 条用量待核对，未计入已知消耗。</p>
<details>
<summary>历史与计量来源</summary>
<p>{{selectedDevice.sourceKind==='local-host'?'本期本机已计量':'累计入口已计量'}}：{{number(selectedDevice.totalTokens)}} Token</p>
<p>{{selectedDevice.sourceKind==='local-host'?'本期计量事件':'累计请求'}}：{{selectedDevice.requests}}</p>
<p>最后采集／心跳：{{time(selectedDevice.lastHeartbeatAt)}}</p>
<p>设备 ID：<code>{{selectedDevice.deviceId}}</code>
</p>
</details>
<button v-if="selectedDevice.sourceKind!=='local-host'" class="primary" @click="accessFromDrawer">管理 Key 与接入审批</button>
<p class="scope-note">Key、硬件验证在接入管理中维护；修改显示名称不改变历史归属。</p>
</template>
</dialog>
  <footer class="updated">每 15 秒更新 · 时间以北京时间显示 · {{data?time(data.serverTime):'等待数据'}}<span>普通 API 接入 · rc.12</span>
</footer>
 </main>
</template>

<style scoped>
.codex-page{padding:26px 28px 30px;max-width:1680px;margin:auto;color:#25354b;font-size:14px}.page-heading,.heading-actions,.panel-heading{display:flex;align-items:center;justify-content:space-between;gap:16px}.page-heading{margin-bottom:22px}.eyebrow{font-size:11px;letter-spacing:1px;color:#7d8da3}h1{font-size:25px;margin:6px 0}h2{font-size:17px;margin:0}p{font-size:13px;color:#76869b;line-height:1.7;margin:7px 0}small{font-size:12px;color:#8090a4;font-weight:400}button{font:inherit;font-size:13px;border:1px solid #dce4ee;border-radius:8px;padding:8px 13px;background:white;color:#4d6685;cursor:pointer}button:disabled{opacity:.5;cursor:default}button:hover:not(:disabled){border-color:#8cacd2}button:focus-visible,summary:focus-visible{outline:2px solid #3f80c9;outline-offset:3px}.primary{background:#326dac;color:white;border-color:#326dac}.freshness{font-size:12px;color:#34866d}.freshness small{display:block;text-align:right}.warning{color:#ad792d}.account-strip{display:flex;align-items:center;gap:28px;background:#fff;border:1px solid #e2e8f0;border-radius:14px;padding:20px 24px}.account-label{min-width:135px}.account-label small{display:block;margin-top:8px}.quota-window{flex:1;min-width:180px;max-width:440px}.quota-window>div:first-child{display:flex;justify-content:space-between;gap:12px;margin-bottom:9px;font-size:13px}.quota-window strong{font-size:19px}.track{height:7px;background:#edf1f6;border-radius:8px;overflow:hidden;margin-bottom:8px}.track i{display:block;height:100%;background:#5b94c9;border-radius:8px}.track i.low{background:#d19b43}.summary-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:16px 0}.summary-grid>div{padding:19px 22px;background:#fff;border:1px solid #e2e8f0;border-radius:12px}.summary-grid span,.member-totals span,.drawer-stats span{display:block;font-size:13px;color:#76869b}.summary-grid strong{display:block;margin:10px 0 5px;font-size:26px;font-variant-numeric:tabular-nums}.attention{display:flex;gap:10px;margin:12px 0}.attention button{background:#fff8ec;color:#946b2d;border-color:#f0dfbf}.page-tabs{display:flex;gap:24px;border-bottom:1px solid #dce4ed;margin:24px 0 20px}.page-tabs button{border:0;border-bottom:3px solid transparent;border-radius:0;background:transparent;padding:0 4px 14px;font-size:15px}.page-tabs button.active{color:#2d69a9;border-bottom-color:#2d69a9;font-weight:600}.page-tabs button span{font-size:11px;margin-left:7px;background:#fff0da;border-radius:9px;padding:2px 6px}.workspace{display:grid;grid-template-columns:235px minmax(0,1fr);gap:18px;align-items:start}.people-panel,.devices-panel,.surface{background:#fff;border:1px solid #e2e8f0;border-radius:13px;min-width:0}.people-panel{padding:15px;position:sticky;top:18px}.panel-heading{padding:20px;border-bottom:1px solid #edf1f6}.people-panel .panel-heading{padding:2px 0 15px;border:0}.people-panel input{width:100%;box-sizing:border-box;border:1px solid #dce4ed;border-radius:8px;background:#f8fafc;padding:10px;font:inherit;font-size:13px}.group-tabs{display:flex;gap:3px;margin:10px 0}.group-tabs button{font-size:12px;padding:6px 9px;border:0;background:transparent}.group-tabs .active,.segmented .active{background:#edf4fc;color:#2d69a9}.person{display:flex;gap:11px;text-align:left;width:100%;border:1px solid transparent;margin:5px 0;padding:11px 9px}.person strong{font-size:14px;color:#334a65}.person small{display:block;font-size:12px;margin-top:5px}.person.selected{background:#f0f6fd;border-color:#d5e5f6}.all-people{display:block}.avatar{width:32px;height:32px;display:grid;place-items:center;background:#ecf1f8;border-radius:10px;font-size:12px;flex-shrink:0}.devices-panel>.panel-heading h2 small{margin-left:12px}.member-totals{display:grid;grid-template-columns:repeat(3,1fr);padding:20px;gap:16px;border-bottom:1px solid #edf1f6}.member-totals strong{display:block;font-size:23px;margin:10px 0 5px;font-variant-numeric:tabular-nums}.host-row{display:flex;justify-content:space-between;align-items:center;gap:18px;margin:18px 20px 0;padding:16px;background:#f5f8fc;border-radius:10px}.host-row small{display:block;margin-top:6px}.scope-note{font-size:12px;margin:12px 20px 18px}.surface{padding:22px;margin-bottom:16px}.surface .panel-heading{padding:0 0 18px}.segmented{display:flex;gap:5px;margin:10px 0}.segmented button{font-size:12px;border:0}.bars{display:grid;gap:6px;padding:17px 0 0}.bar-row{display:grid;grid-template-columns:110px minmax(60px,1fr) 90px;gap:20px;align-items:center;border:0;text-align:left;padding:10px 6px}.bar-row strong{text-align:right;color:#344a65;font-size:14px;font-variant-numeric:tabular-nums}.bar-track{height:12px;background:#f1f4f8;border-radius:4px;overflow:hidden}.bar-track i{display:block;height:100%;background:#6d9dcd;border-radius:4px}.allocation-numbers{display:grid;grid-template-columns:repeat(3,1fr);gap:20px;margin:24px 0}.allocation-numbers span{color:#7b8ba1;font-size:13px;display:block}.allocation-numbers strong{font-size:24px;display:block;margin-top:9px}em{font-style:normal;font-size:11px;color:#967538;background:#faf3e5;border-radius:4px;padding:2px 5px;margin-left:5px;vertical-align:middle}details>summary{cursor:pointer;font-size:14px;color:#4d6685;padding:4px 0}details[open]>summary{margin-bottom:14px}details details{margin-top:14px}.table-scroll{overflow:auto}table{border-collapse:collapse;width:100%;font-size:13px;white-space:nowrap;text-align:left}td,th{padding:13px;border-bottom:1px solid #edf1f6}th{color:#7d8ba0;font-weight:500}td small{display:block}.alert{padding:12px 16px;background:#fff4e9;border:1px solid #f1ddc4;color:#93672f;border-radius:8px}.updated{display:flex;justify-content:space-between;margin-top:26px;color:#91a0b2;font-size:11px}.empty{padding:18px;color:#8b99ac}.access-page{display:grid;gap:16px}.device-drawer{position:fixed;left:auto;right:0;top:0;bottom:0;max-height:100dvh;height:100dvh;width:min(480px,100vw);max-width:100vw;box-sizing:border-box;margin:0;padding:28px;border:0;border-left:1px solid #dce4ed;background:#fff;color:#25354b;box-shadow:-12px 0 40px #25354b18;overflow:auto}.device-drawer::backdrop{background:#182b4440}.device-drawer header{display:flex;justify-content:space-between;align-items:center}.device-drawer h2{margin-top:8px}.drawer-stats{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin:25px 0}.drawer-stats strong{display:block;font-size:23px;margin:10px 0}.device-drawer details{margin:24px 0;padding:15px;background:#f6f8fb;border-radius:8px}.device-drawer .scope-note{margin:14px 0}.device-drawer code{overflow-wrap:anywhere;font-size:12px}.usage-page{max-width:1250px}
@media(max-width:1100px){.codex-page{padding:20px}.workspace{grid-template-columns:205px minmax(0,1fr)}.summary-grid>div{padding:16px}.heading-actions{gap:8px}.freshness{display:none}}
@media(max-width:760px){.codex-page{padding:15px}.page-heading{align-items:flex-start}.page-heading h1{font-size:22px}.heading-actions{flex-wrap:wrap;justify-content:flex-end}.heading-actions .primary{display:none}.account-strip{flex-wrap:wrap;padding:16px;gap:16px}.account-label{width:100%}.quota-window{max-width:none}.summary-grid{grid-template-columns:repeat(2,1fr);gap:9px}.summary-grid strong{font-size:23px}.summary-grid>div{padding:14px}.workspace{grid-template-columns:1fr}.people-panel{position:static}.person{width:100%}.people-panel{max-height:270px;overflow:auto}.member-totals{padding:16px;gap:10px}.member-totals strong{font-size:20px}.host-row{flex-wrap:wrap}.bar-row{grid-template-columns:65px minmax(40px,1fr) 70px;gap:10px}.allocation-numbers{gap:10px}.allocation-numbers strong{font-size:21px}.updated{display:block;line-height:1.8}.updated span{display:block}.surface{padding:16px}.page-tabs{gap:18px}.attention{flex-wrap:wrap}}
</style>

<style scoped>
.page-heading{margin-bottom:16px}.codex-page{padding-top:20px}.account-strip{padding:14px 22px}.quota-window strong{font-size:17px}.quota-window>div:first-child{margin-bottom:6px}.account-label small{margin-top:5px}.summary-grid{margin:12px 0}.summary-grid>div{padding:12px 20px}.summary-grid strong{font-size:23px;margin:5px 0 2px}.page-tabs{margin:18px 0 16px}.page-tabs button{padding-bottom:11px}.device-context{display:grid;grid-template-columns:minmax(140px,1fr) minmax(300px,1.8fr);align-items:center;border-bottom:1px solid #edf1f6}.device-context .panel-heading{padding:16px;border:0}.device-context .panel-heading p{font-size:12px;margin-bottom:0}.member-totals{padding:16px;border:0;gap:12px}.member-totals strong{font-size:20px;margin:7px 0 0}.member-totals>div>small{display:none}.member-totals span{font-size:12px}.host-row{margin-bottom:10px}.scope-note{margin-top:10px}
@media(max-width:1000px){.device-context{grid-template-columns:1fr}.device-context .panel-heading{padding-bottom:0}.member-totals{padding-top:12px}}
</style>
