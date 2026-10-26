<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { getJsonStrict, mutateJsonStrict } from '../api/client'

type Device = {deviceId:string;deviceName:string;displayName:string;platform:string;revoked:boolean;memberActive:boolean;enabled:boolean;maxConcurrent:number|null;activeRequests:number;queuedRequests:number}
type Control = {revision:number;globalMaxConcurrent:number|null;activeRequests:number;queuedRequests:number;queueLimit:number;queueWaitSeconds:number;updatedAt:string|null;sourceMaintenanceUntil?:number|null;devices:Device[]}
const props=defineProps<{refreshKey:number;visibleDeviceIds?:string[];usage?:Record<string,{today:string;last:string;activity:string}>}>()
const emit=defineEmits<{changed:[];detail:[id:string];state:[value:{activeRequests:number;queuedRequests:number}|null]}>()
const state=ref<Control|null>(null)
const loading=ref(false), working=ref(false), unavailable=ref(false)
const error=ref(''), notice=ref(''), search=ref('')
const selected=ref<string[]>([])
const totalMode=ref('custom'),totalValue=ref(6),totalDirty=ref(false)
const editing=ref<Device|null>(null),deviceMode=ref('unlimited'),deviceValue=ref(1)
let stopped=false
const devices=computed(()=>state.value?.devices || [])
const visible=computed(()=>devices.value.filter(d=>(!props.visibleDeviceIds || props.visibleDeviceIds.includes(d.deviceId)) && `${d.deviceName} ${d.displayName}`.toLowerCase().includes(search.value.toLowerCase())))
const selectable=computed(()=>visible.value.filter(d=>!d.revoked).map(d=>d.deviceId))
const allSelected=computed(()=>!!selectable.value.length && selectable.value.every(id=>selected.value.includes(id)))
const partialSelected=computed(()=>!allSelected.value && selectable.value.some(id=>selected.value.includes(id)))
const blocked=computed(()=>!state.value || unavailable.value || working.value)
const limitLabel=(value:number|null)=>value===null?'无限':`${value} 路`
function apply(next:Control) {
  if (stopped) return
  state.value=next;unavailable.value=false;emit('state',next)
  selected.value=selected.value.filter(id=>next.devices.some(d=>d.deviceId===id && !d.revoked))
  if (!totalDirty.value) {totalMode.value=next.globalMaxConcurrent===null?'unlimited':'custom';totalValue.value=next.globalMaxConcurrent??6}
}
async function load() {
  if (loading.value || working.value) return
  loading.value=true
  try {apply(await getJsonStrict<Control>('/codex/access-control'));error.value=''}
  catch {if(!stopped){unavailable.value=true;emit('state',null);error.value='设备控制状态暂时无法读取，请刷新后操作。'}}
  finally {loading.value=false}
}
async function mutate(path:string,body:Record<string,unknown>,message:string) {
  if (blocked.value || !state.value) return false
  working.value=true;error.value='';notice.value=''
  try {
    const next=await mutateJsonStrict<Control>(path,path.endsWith('/status')?'POST':'PATCH',{...body,revision:state.value.revision})
    apply(next);if(!stopped){notice.value=message;emit('changed')};return true
  } catch(e) {if(!stopped) error.value=e instanceof Error?e.message:'操作未完成，请刷新核对状态。';return false}
  finally {working.value=false}
}
function selectAll(checked:boolean) {
  selected.value=checked?[...new Set([...selected.value,...selectable.value])]:selected.value.filter(id=>!selectable.value.includes(id))
}
function selectOne(id:string,checked:boolean) {selected.value=checked?[...selected.value,id]:selected.value.filter(value=>value!==id)}
async function bulk(scope:'all'|'selected',enabled:boolean) {
  const ids=scope==='selected'?selected.value:[]
  if(scope==='selected' && !ids.length)return
  if(await mutate('/codex/devices/status',{scope,enabled,deviceIds:ids},`${scope==='all'?'全部已登记子设备':'所选设备'}已${enabled?'启用':'停用'}。`))selected.value=[]
}
async function toggle(d:Device) {await mutate(`/codex/devices/${d.deviceId}/control`,{enabled:!d.enabled},`${d.deviceName}已${d.enabled?'停用':'启用'}。`)}
function limit(mode:string,value:number) {
  if(mode==='unlimited')return null
  if(!Number.isInteger(value)||value<1||value>100000){error.value='请输入 1–100000 的整数，或选择无限。';return undefined}
  return value
}
async function saveTotal() {
  const value=limit(totalMode.value,Number(totalValue.value));if(value===undefined)return
  if(await mutate('/codex/access-control',{maxConcurrent:value},'设备总并发上限已保存。')){totalDirty.value=false;apply(state.value!)}
}
function editLimit(d:Device) {error.value='';editing.value=d;deviceMode.value=d.maxConcurrent===null?'unlimited':'custom';deviceValue.value=d.maxConcurrent??1}
async function saveDevice() {
  if(!editing.value)return
  const value=limit(deviceMode.value,Number(deviceValue.value));if(value===undefined)return
  if(await mutate(`/codex/devices/${editing.value.deviceId}/control`,{maxConcurrent:value},'单台设备并发上限已保存。'))editing.value=null
}
watch(selectable,ids=>{selected.value=selected.value.filter(id=>ids.includes(id))})
watch(()=>props.refreshKey,()=>{void load()})
onMounted(()=>{void load()})
onUnmounted(()=>{stopped=true})
</script>

<template>
  <section class="control-panel" aria-label="设备启停与并发">

    <details class="global-settings"><summary>全局管理 · 所有已登记子设备</summary><div class="total-controls">
      <label>设备总并发上限<select v-model="totalMode" aria-label="设备总并发模式" :disabled="blocked" @change="totalDirty=true"><option value="unlimited">无限</option><option value="custom">自定义</option></select></label>
      <input v-if="totalMode==='custom'" v-model.number="totalValue" type="number" min="1" max="100000" step="1" aria-label="设备总并发数" :disabled="blocked" @input="totalDirty=true" />
      <button class="primary" :disabled="blocked || !totalDirty" @click="saveTotal">保存总上限</button>
      <div class="running"><span>当前上限 <b>{{state?limitLabel(state.globalMaxConcurrent):'—'}}</b></span><span>正在执行 <b>{{unavailable?'—':state?.activeRequests??'—'}}</b></span><span>排队 <b>{{unavailable?'—':state?.queuedRequests??'—'}}</b></span></div>
    </div>
    <p class="hint">“无限”表示不设置此层并发上限，仍受上游容量约束。单台上限与总上限同时生效；达到上限后最多排队 {{state?.queueWaitSeconds??120}} 秒。</p>
    <p v-if="state?.sourceMaintenanceUntil && state.sourceMaintenanceUntil*1000>Date.now()" class="notice" role="status">模型源正在更新，新请求暂时排队，已有任务继续完成。</p>
    <div class="bulk-actions"><button :disabled="blocked" @click="bulk('all',true)">全部启用（{{devices.filter(d=>!d.revoked).length}}台）</button><button :disabled="blocked" @click="bulk('all',false)">全部停用（{{devices.filter(d=>!d.revoked).length}}台）</button></div></details>
    <div class="bulk-toolbar"><div v-if="selected.length" class="bulk-actions"><span>已选 {{selected.length}} 台</span><button :disabled="blocked" @click="bulk('selected',true)">批量启用</button><button :disabled="blocked" @click="bulk('selected',false)">批量停用</button></div><span v-else>当前范围 {{visible.length}} 台 · 勾选设备可批量操作</span><div class="filter-actions"><input v-model="search" aria-label="筛选控制设备" placeholder="筛选设备" /><button :disabled="loading || working" @click="load">刷新设置</button></div></div>
    <p v-if="notice" class="notice" role="status">{{notice}}</p><p v-if="error && !editing" class="error" role="alert">{{error}}</p>
    <div class="control-table"><table><thead><tr><th><input type="checkbox" aria-label="选择全部可见设备" :checked="allSelected" :indeterminate="partialSelected" :disabled="blocked || !selectable.length" @change="selectAll(($event.target as HTMLInputElement).checked)" /></th><th>接入名称 / 人员</th><th>使用状态</th><th>启用状态</th><th>单台并发上限</th><th>正在执行</th><th>排队</th><th>今日 Token</th><th>最近使用</th><th></th></tr></thead><tbody>
      <tr v-for="d in visible" :key="d.deviceId"><td><input type="checkbox" :aria-label="`选择 ${d.deviceName}`" :checked="selected.includes(d.deviceId)" :disabled="blocked || d.revoked" @change="selectOne(d.deviceId,($event.target as HTMLInputElement).checked)" /></td><td><strong>{{d.deviceName}}</strong><small>{{d.displayName}} · {{d.platform}}<span v-if="!d.memberActive"> · 人员已停用</span></small></td><td>{{usage?.[d.deviceId]?.activity || '状态待确认'}}</td><td><div class="status-cell"><button role="switch" class="device-switch" :class="{on:d.enabled && !d.revoked}" :aria-label="`${d.deviceName} 启用开关`" :aria-checked="d.enabled && !d.revoked" :disabled="blocked || d.revoked" @click="toggle(d)"><span></span></button><span>{{d.revoked?'已撤销':d.enabled?'已启用':'已停用'}}</span></div></td><td><button class="limit-button" :aria-label="`${d.deviceName} 并发上限`" :disabled="blocked || d.revoked" @click="editLimit(d)">{{limitLabel(d.maxConcurrent)}} <span>设置</span></button></td><td>{{d.activeRequests}}</td><td>{{d.queuedRequests}}</td><td>{{usage?.[d.deviceId]?.today ?? '—'}}</td><td>{{usage?.[d.deviceId]?.last ?? '—'}}</td><td><button @click="emit('detail',d.deviceId)">详情</button></td></tr>
      <tr v-if="!visible.length"><td colspan="10">{{loading?'正在读取设备…':'没有匹配的已登记子设备。'}}</td></tr>
    </tbody></table></div>
  </section>
  <div v-if="editing" class="control-overlay"><form class="limit-dialog" role="dialog" aria-modal="true" aria-labelledby="limit-title" @submit.prevent="saveDevice"><h2 id="limit-title">{{editing.deviceName}} · 单台并发上限</h2><p>单台上限与总上限同时生效。降低上限会等待已有请求结束，再接收新请求。</p><label>并发上限<select v-model="deviceMode" aria-label="单台并发模式" :disabled="working"><option value="unlimited">无限</option><option value="custom">自定义</option></select></label><input v-if="deviceMode==='custom'" v-model.number="deviceValue" type="number" min="1" max="100000" step="1" aria-label="单台并发数" :disabled="working" /><p v-if="error" class="error" role="alert">{{error}}</p><footer><button type="button" :disabled="working" @click="editing=null">取消</button><button class="primary" :disabled="working">{{working?'保存中…':'保存单台上限'}}</button></footer></form></div>
</template>

<style scoped>
.control-panel{margin-top:12px;padding:15px 18px;border:1px solid #dfe6ef;border-radius:12px;background:#fff;color:#34465b}header{display:flex;align-items:center;justify-content:space-between;gap:14px}h2{margin:0;font-size:14px;color:#1b2a3d}p{margin:6px 0;color:#7a899a;font-size:11px;line-height:1.7}button{border:1px solid #d6e0ec;border-radius:7px;background:#fff;padding:6px 11px;color:#48668b;cursor:pointer;font:inherit;font-size:11px;white-space:nowrap}button:disabled,input:disabled,select:disabled{opacity:.5;cursor:default}.primary{background:#2767ad;border-color:#2767ad;color:#fff}input,select{box-sizing:border-box;border:1px solid #dce4ee;border-radius:7px;padding:7px 9px;font:inherit;font-size:12px;background:#fbfcfe;color:#34465b}select{margin-left:10px}input[type=number]{width:94px}.total-controls{display:flex;flex-wrap:wrap;gap:9px;align-items:center;margin-top:14px;font-size:12px}.running{display:flex;flex-wrap:wrap;gap:18px;margin-left:auto;font-size:11px;color:#8290a1}.running b{font-size:13px;color:#34465b;margin-left:4px}.hint{margin:9px 0 14px}.bulk-toolbar,.bulk-actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap;font-size:11px}.bulk-toolbar{justify-content:space-between}.bulk-toolbar>input{width:190px}.separator{height:18px;width:1px;background:#e2e8ef;margin:0 4px}.notice{color:#2c8061}.error{color:#b34040}.control-table{overflow:auto;max-height:330px;margin-top:10px}table{width:100%;border-collapse:collapse;font-size:11px;white-space:nowrap}th,td{text-align:left;border-top:1px solid #edf1f6;padding:11px 9px}th{color:#8290a1;font-weight:500;position:sticky;top:0;background:#fff;z-index:1}td strong{font-weight:500;color:#34465b}td small{display:block;color:#8a97a8;font-size:10px;margin-top:3px}input[type=checkbox]{width:14px;height:14px;accent-color:#2767ad;cursor:pointer}.status-cell{display:flex;align-items:center;gap:8px}.device-switch{position:relative;width:34px;height:20px;padding:0;border:0;border-radius:12px;background:#b6c2cf;flex-shrink:0}.device-switch span{position:absolute;left:3px;top:3px;width:14px;height:14px;border-radius:50%;background:white;transition:transform .12s}.device-switch.on{background:#2d8a70}.device-switch.on span{transform:translateX(14px)}.device-switch:focus-visible{outline:2px solid #397ccc;outline-offset:3px}.limit-button{padding:4px 8px;min-width:86px;text-align:left}.limit-button span{float:right;font-size:10px;color:#8a97a8;margin-left:10px}.control-overlay{position:fixed;inset:0;z-index:1001;display:grid;place-items:center;background:#1c2a3c66;padding:20px}.limit-dialog{width:min(440px,100%);box-sizing:border-box;background:#fff;border-radius:14px;padding:22px;box-shadow:0 15px 70px #17233430}.limit-dialog label{display:block;font-size:12px;margin:18px 0 9px}.limit-dialog footer{display:flex;justify-content:flex-end;gap:8px;margin-top:22px}@media(max-width:750px){.running{margin-left:0;width:100%;margin-top:4px}.bulk-toolbar>input{width:100%;margin-top:5px}header{align-items:flex-start}}@media(prefers-reduced-motion:reduce){.device-switch span{transition:none}}
</style>

<style scoped>
.control-panel{margin-top:0;border:0;border-radius:0;padding:20px}.control-panel h2{font-size:16px}.control-panel p,.bulk-toolbar,.total-controls,table{font-size:13px}.control-panel button,.control-panel input,.control-panel select{font-size:12px}.control-table{max-height:none}.control-table th{position:static}.control-table td{padding:14px 10px}.control-table td small{font-size:12px}.global-settings{margin:12px 0 18px;border:1px solid #e5eaf2;border-radius:9px;padding:12px}.global-settings summary{cursor:pointer;color:#526b8a;font-size:13px}.global-settings .bulk-actions{margin-top:10px}.bulk-toolbar{color:#7a899a}.control-table td:nth-last-child(3){font-variant-numeric:tabular-nums;font-weight:600}
</style>

<style scoped>.control-panel{padding:16px}.global-settings{margin:0 0 12px;padding:9px 12px}.filter-actions{display:flex;gap:7px}.control-table td:nth-child(2){max-width:170px;overflow:hidden;text-overflow:ellipsis}.control-table th,.control-table td{padding:11px 8px}</style>
