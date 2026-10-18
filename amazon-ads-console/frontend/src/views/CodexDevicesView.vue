<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { getJsonStrict, API_BASE, AUTH_TOKEN_KEY } from '../api/client'

type Device = { deviceId:string; deviceName:string; platform:string; online:boolean; revoked:boolean; lastHeartbeatAt:string|null; lastRequestAt:string|null; totalTokens:number|null; todayTokens:number|null; inputTokens:number|null; outputTokens:number|null; requests:number; unknownRequests:number }
type Member = { userId:number; displayName:string; username:string; groupCode:string; groupName:string; personCode:string|null; roleCode:string; devices:Device[] }
type Overview = { members:Member[]; serverTime:string; onlineTimeoutSeconds:number; timezone:string }
const data = ref<Overview|null>(null)
const selectedId = ref<number|null>(null)
const search = ref('')
const group = ref('all')
const error = ref('')
const loading = ref(false)
const updatedAt = ref(0)
const now = ref(Date.now())
const origin = window.location.origin
const adding = ref(false)
const deviceName = ref('')
const platform = ref('macOS')
const saving = ref(false)
const formError = ref('')
const credential = ref<{deviceId:string; heartbeatKey:string}|null>(null)
let timer: ReturnType<typeof setInterval>|undefined
let clock: ReturnType<typeof setInterval>|undefined
let stopped = false
const stale = computed(() => !!error.value || now.value - updatedAt.value > 45000)
// Expire green indicators locally even if a refresh fails or the tab resumes after sleep.
const isOnline = (d:Device) => !stale.value && !d.revoked && !!d.lastHeartbeatAt &&
  !!data.value && (Date.parse(data.value.serverTime) + now.value - updatedAt.value - Date.parse(d.lastHeartbeatAt)) <= data.value.onlineTimeoutSeconds * 1000 && d.online
const members = computed(() => data.value?.members || [])
const filtered = computed(() => members.value.filter(m => (group.value === 'all' || m.groupCode === group.value) &&
  `${m.displayName} ${m.personCode || ''} ${m.username} ${m.devices.map(d=>d.deviceName).join(' ')}`.toLowerCase().includes(search.value.toLowerCase())))
const selected = computed(() => members.value.find(m=>m.userId === selectedId.value))
const devices = computed(() => members.value.flatMap(m=>m.devices))
const onlineCount = computed(() => devices.value.filter(isOnline).length)
const sum = (items:Device[], key:'todayTokens'|'totalTokens') => {
  const measured = items.map(d=>d[key]).filter((x): x is number=>x !== null)
  return measured.length ? measured.reduce((a,b)=>a+b,0) : null
}
const number = (v:number|null) => v === null ? '—' : v.toLocaleString('zh-CN')
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
async function api(path:string, method:string, body?:unknown) {
  const response = await fetch(`${API_BASE}/codex${path}`, {method, headers:{
    'Content-Type':'application/json', Authorization:`Bearer ${localStorage.getItem(AUTH_TOKEN_KEY) || ''}`,
  }, ...(body ? {body:JSON.stringify(body)} : {})})
  if (!response.ok) throw new Error(`操作失败（${response.status}）`)
  return response.json()
}
function openAdd() { adding.value = true; credential.value = null; formError.value = ''; deviceName.value = ''; platform.value = 'macOS' }
function closeAdd() { if (!saving.value) { adding.value = false; credential.value = null } }
async function addDevice() {
  if (!selected.value || !deviceName.value.trim() || saving.value) return
  saving.value = true; formError.value = ''
  try { credential.value = await api('/devices','POST',{user_id:selected.value.userId,device_name:deviceName.value.trim(),platform:platform.value}); await refresh() }
  catch(e) { formError.value = e instanceof Error ? e.message : '添加失败' }
  finally { saving.value = false }
}
async function revoke(d:Device) {
  if (!window.confirm(`停用设备“${d.deviceName}”？停用后将不再接受该设备的心跳及用量上报。`)) return
  try { await api(`/devices/${d.deviceId}`,'DELETE'); await refresh() }
  catch(e) { error.value = e instanceof Error ? e.message : '停用失败' }
}
function onVisible() { now.value = Date.now(); if (!document.hidden) void refresh() }
onMounted(() => { void refresh(); timer = setInterval(()=>{ if (!document.hidden) void refresh() },30000); clock = setInterval(()=>{now.value=Date.now()},1000); document.addEventListener('visibilitychange',onVisible) })
onUnmounted(() => { stopped = true; clearInterval(timer); clearInterval(clock); document.removeEventListener('visibilitychange',onVisible); credential.value = null })
</script>

<template>
  <main class="codex-page">
    <header class="page-heading"><div><span class="eyebrow">CODEX · 团队设备</span><h1>分发人员 &amp; 设备</h1><p>按人员查看设备连接与 Token 用量</p></div><button class="refresh" :disabled="loading" @click="refresh">{{ loading ? '刷新中…' : '刷新状态' }}</button></header>
    <div v-if="error" class="error" role="alert">{{ error }}。状态暂不可确认，已暂停显示在线绿点。<button @click="refresh">重试</button></div>
    <div class="summary-grid">
      <div><span>分发成员</span><strong>{{ data ? members.length : '—' }}<small> 人</small></strong></div>
      <div><span>已登记设备</span><strong>{{ data ? devices.length : '—' }}<small> 台</small></strong></div>
      <div><span><i class="dot green"></i>在线设备</span><strong>{{ data && !stale ? onlineCount : '—' }}<small> 台</small></strong></div>
      <div><span>今日已计量 Token</span><strong>{{ number(sum(devices,'todayTokens')) }}</strong></div>
    </div>
    <p class="collection-note">绿点表示最近 120 秒内收到设备心跳；灰点表示离线、未接入或状态待确认。用量只统计代理已回传的数据，“—”表示暂无计量。</p>
    <div class="workspace">
      <section class="people-panel" aria-label="分发人员">
        <div class="panel-heading"><h2>分发人员</h2><span>{{ filtered.length }} 人</span></div>
        <div class="people-filters"><input v-model="search" aria-label="搜索成员或设备" placeholder="搜索姓名、编码或设备" /><div class="group-tabs"><button v-for="g in [{key:'all',name:'全部'},{key:'operations',name:'运营组'},{key:'ai',name:'AI 小组'}]" :key="g.key" :class="{active:group===g.key}" @click="group=g.key">{{ g.name }}</button></div></div>
        <div class="people-list"><button v-for="m in filtered" :key="m.userId" class="person" :class="{selected:m.userId===selectedId}" @click="selectedId=m.userId"><span class="avatar">{{ m.displayName.slice(-2) }}</span><span class="person-info"><strong>{{ m.displayName }} <small>{{ m.personCode || '管理层' }}</small></strong><span>{{ m.groupName }} · {{ m.devices.length }} 台设备</span></span><i class="dot" :class="{green:m.devices.some(isOnline)}" :aria-label="m.devices.some(isOnline)?'在线':'离线或未接入'"></i></button><p v-if="!filtered.length" class="empty">{{ loading ? '正在读取人员名单…' : '没有匹配的成员' }}</p></div>
      </section>
      <section class="devices-panel" aria-label="人员设备与用量">
        <template v-if="selected">
          <div class="panel-heading device-heading"><div><h2>{{ selected.displayName }}<span class="group-badge">{{ selected.groupName }}</span></h2><p>{{ selected.username }}<span v-if="selected.personCode"> · {{ selected.personCode }}</span><span v-if="selected.roleCode==='management'"> · 保留管理权限</span></p></div><button class="add" @click="openAdd">添加设备</button></div>
          <div class="member-totals"><div><span>今日已计量</span><strong>{{ number(sum(selected.devices,'todayTokens')) }} <small>Token</small></strong></div><div><span>累计已计量</span><strong>{{ number(sum(selected.devices,'totalTokens')) }} <small>Token</small></strong></div></div>
          <div v-if="!selected.devices.length" class="empty-device"><div class="monitor-icon">▱</div><h3>尚未接入设备</h3><p>为 {{ selected.displayName }} 登记设备，并安装心跳组件后，<br />即可在这里查看连接状态；代理接入后开始统计用量。</p><button class="add" @click="openAdd">添加第一台设备</button></div>
          <div v-else class="device-list"><article v-for="d in selected.devices" :key="d.deviceId" class="device-card"><header><div><h3>{{ d.deviceName }}</h3><p>{{ d.platform || '未填写系统' }}</p></div><span class="connection"><i class="dot" :class="{green:isOnline(d)}"></i>{{ d.revoked ? '已停用' : stale ? '状态待确认' : isOnline(d) ? '在线' : d.lastHeartbeatAt ? '离线' : '未接入' }}</span></header><div class="device-stats"><div><span>今日 Token</span><strong>{{ number(d.todayTokens) }}</strong></div><div><span>累计 Token</span><strong>{{ number(d.totalTokens) }}</strong></div><div><span>累计请求</span><strong>{{ d.requests }}</strong></div></div><footer><span>最近心跳：{{ time(d.lastHeartbeatAt) }}<br />最近调用：{{ time(d.lastRequestAt) }}<br v-if="d.unknownRequests" /><span v-if="d.unknownRequests">{{ d.unknownRequests }} 次请求未返回 Token 数据，暂未计入用量</span></span><button v-if="!d.revoked" class="revoke" @click="revoke(d)">停用</button></footer></article></div>
        </template><p v-else class="empty">{{ loading ? '正在加载…' : '请选择一位成员' }}</p>
      </section>
    </div>
    <p class="updated">每 30 秒刷新 · 时间以北京时间显示<span v-if="data"> · 最近更新 {{ time(data.serverTime) }}</span></p>
    <div v-if="adding" class="modal-mask" @click.self="closeAdd"><section class="device-modal" role="dialog" aria-modal="true" aria-labelledby="device-modal-title"><header><h2 id="device-modal-title">为 {{ selected?.displayName }} 添加设备</h2><button :disabled="saving" aria-label="关闭" @click="closeAdd">×</button></header><template v-if="!credential"><label>设备名称<input v-model="deviceName" maxlength="128" placeholder="例如：Pan-公司-M4" /></label><label>设备系统<input v-model="platform" maxlength="64" /></label><p>登记后需在该设备安装心跳组件。设备密码和模型接口凭据不受影响。</p><p v-if="formError" class="error">{{ formError }}</p><button class="add" :disabled="saving || !deviceName.trim()" @click="addDevice">{{ saving ? '登记中…' : '登记设备' }}</button></template><template v-else><p>设备已登记。请安全保存以下心跳配置，密钥仅在本次窗口展示。</p><textarea readonly aria-label="设备心跳配置" :value="JSON.stringify({url:API_BASE.startsWith('/') ? origin+API_BASE : API_BASE,deviceId:credential.deviceId,heartbeatKey:credential.heartbeatKey},null,2)" /><p>此密钥仅用于在线心跳；Token 用量由主代理单独回传。</p><button class="add" @click="closeAdd">已保存，关闭</button></template></section></div>
  </main>
</template>

<style scoped>
.codex-page{padding:28px 30px 36px;max-width:1600px;margin:auto;color:#233247;text-align:left}.page-heading{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-bottom:24px}.eyebrow{font-size:11px;letter-spacing:1.4px;color:#8190a5}.page-heading h1{font-size:27px;letter-spacing:-.6px;margin:7px 0 6px}.page-heading p,.device-heading p{color:#7b8798;font-size:13px;margin:0}.refresh,.add{padding:9px 16px;border:1px solid #d5dfec;background:white;border-radius:999px;color:#3e5e87;cursor:pointer;font-size:12px}.add{background:#edf5ff;border-color:#c8dff9;color:#1761be}.refresh:disabled,.add:disabled{opacity:.5;cursor:default}.summary-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}.summary-grid>div{padding:18px 22px;background:white;border:1px solid #e2e8f0;border-radius:18px}.summary-grid span{font-size:12px;color:#7a899a;display:flex;align-items:center;gap:7px}.summary-grid strong{display:block;font-size:28px;line-height:1.4;margin-top:8px;font-weight:600}.summary-grid small{font-size:12px;color:#8a96a7;font-weight:400}.collection-note{font-size:12px;color:#8590a0;line-height:1.8;margin:16px 2px 20px}.workspace{display:grid;grid-template-columns:330px minmax(0,1fr);gap:20px;align-items:start}.people-panel,.devices-panel{background:#fff;border:1px solid #dfe6ef;border-radius:24px;overflow:hidden;min-width:0}.panel-heading{display:flex;align-items:center;justify-content:space-between;padding:22px 24px 17px;gap:12px}.panel-heading h2{margin:0;font-size:17px}.panel-heading>span{font-size:12px;color:#8b96a5}.people-filters{padding:0 18px 14px;border-bottom:1px solid #edf0f5}.people-filters input,.device-modal input{border:1px solid #e1e7ee;border-radius:10px;background:#f8fafc;padding:11px 12px;width:100%;box-sizing:border-box;font-size:12px;outline:none}.people-filters input:focus,.device-modal input:focus{border-color:#86b6f3}.group-tabs{display:flex;gap:4px;padding-top:12px}.group-tabs button{border:0;background:transparent;color:#7a8798;cursor:pointer;padding:7px 12px;border-radius:999px;font-size:12px}.group-tabs button.active{background:#eaf3ff;color:#2568ba}.people-list{padding:8px;max-height:670px;overflow-y:auto}.person{display:flex;align-items:center;gap:11px;width:100%;text-align:left;background:white;border:1px solid transparent;border-radius:15px;padding:13px 12px;cursor:pointer;margin:3px 0}.person:hover{background:#f6f9fd}.person.selected{background:#f0f6ff;border-color:#d3e4fc}.avatar{width:37px;height:37px;display:grid;place-items:center;border-radius:13px;background:#edf1f6;color:#60758d;font-size:12px;flex-shrink:0}.person.selected .avatar{background:#dfeaff;color:#3169b4}.person-info{flex:1;min-width:0}.person-info strong{display:block;font-size:13px;color:#34465b;font-weight:600}.person-info strong small{font-size:10px;color:#8e9aae;font-weight:400;margin-left:4px}.person-info>span{display:block;font-size:11px;color:#97a1ae;margin-top:5px}.dot{display:inline-block;width:8px;height:8px;border-radius:50%;background:#aeb7c3;flex-shrink:0}.dot.green{background:#34b774;box-shadow:0 0 0 3px #34b77412}.device-heading{border-bottom:1px solid #edf0f5;padding:24px}.device-heading p{margin-top:9px;font-size:11px}.group-badge{font-size:10px;font-weight:400;display:inline-block;background:#f0f4fa;color:#7689a1;border-radius:999px;padding:4px 10px;margin-left:12px;vertical-align:middle}.member-totals{display:flex;gap:55px;padding:24px;border-bottom:1px solid #edf0f5}.member-totals span,.device-stats span{display:block;font-size:11px;color:#95a0af}.member-totals strong{display:block;font-size:25px;margin-top:7px;font-weight:600}.member-totals small{font-size:10px;font-weight:400;color:#94a0af}.empty-device{min-height:310px;display:flex;align-items:center;justify-content:center;flex-direction:column;padding:35px}.monitor-icon{height:55px;width:65px;display:grid;place-items:center;border:1px solid #e8edf5;background:#f8fafd;border-radius:18px;font-size:35px;color:#b6c4d8}.empty-device h3{font-size:15px;font-weight:500;margin:20px 0 9px;color:#66778e}.empty-device p{font-size:12px;line-height:1.9;color:#94a0b0;text-align:center;margin:0 0 21px}.device-list{padding:20px;display:grid;gap:14px}.device-card{border:1px solid #e5ebf3;border-radius:17px;padding:18px}.device-card header{display:flex;justify-content:space-between;align-items:center;gap:12px}.device-card h3{font-size:14px;margin:0}.device-card header p{font-size:11px;color:#96a0af;margin:5px 0 0}.connection{display:flex;align-items:center;gap:8px;font-size:11px;color:#7c8a9b}.device-stats{display:grid;grid-template-columns:repeat(3,1fr);padding:19px 0;gap:12px}.device-stats strong{display:block;margin-top:6px;font-size:19px;font-weight:500}.device-card footer{display:flex;justify-content:space-between;gap:12px;border-top:1px solid #f0f3f7;padding-top:12px;font-size:10px;line-height:1.9;color:#8f9aac;overflow-wrap:anywhere}.revoke{border:0;background:transparent;color:#9b6870;cursor:pointer;font-size:11px}.updated{font-size:10px;color:#a3adba;text-align:right;margin-top:16px}.error{border:1px solid #edd2bc;background:#fff9f0;border-radius:12px;font-size:12px;color:#a3773c;padding:13px 16px;margin-bottom:15px}.error button{background:none;border:0;color:#98692a;cursor:pointer;margin-left:8px}.empty{padding:35px 20px;text-align:center;color:#99a4b3;font-size:12px}.modal-mask{position:fixed;inset:0;background:#1a2b4855;z-index:1000;display:flex;align-items:center;justify-content:center;padding:20px}.device-modal{background:white;border-radius:22px;padding:25px;width:460px;max-width:100%}.device-modal header{display:flex;justify-content:space-between;align-items:center;margin-bottom:22px}.device-modal h2{font-size:16px;margin:0}.device-modal header button{background:none;border:0;font-size:24px;cursor:pointer;color:#97a3b4}.device-modal label{display:block;font-size:12px;margin:15px 0;color:#65788f}.device-modal input{margin-top:8px}.device-modal p{font-size:12px;line-height:1.8;color:#8491a4}.device-modal textarea{width:100%;box-sizing:border-box;height:160px;font-size:11px;border:1px solid #e3e9f2;border-radius:10px;padding:12px;resize:vertical}.device-modal .add{margin-top:10px}@media(max-width:1050px){.workspace{grid-template-columns:280px minmax(0,1fr)}.codex-page{padding:22px 20px}.summary-grid>div{padding:16px}.summary-grid strong{font-size:23px}}@media(max-width:760px){.workspace{grid-template-columns:1fr}.people-list{max-height:290px}.summary-grid{grid-template-columns:repeat(2,1fr)}.page-heading h1{font-size:23px}.codex-page{padding:18px 12px}.member-totals{gap:25px}.device-heading{flex-wrap:wrap}.updated{text-align:left;line-height:1.8}}
</style>
