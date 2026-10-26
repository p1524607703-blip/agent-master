<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from 'vue'
import { getJsonStrict, mutateJsonStrict } from '../api/client'
type Binding = {device_id:string;device_name:string;fingerprint:string|null;approved_at:string|null;claim_id:string|null;candidate_fingerprint:string|null;provider:string|null;auth_mode:'api_key'|'hardware';access_approved_at:string|null;access_revision:number}
const props = defineProps<{refreshKey?:number}>()
const items = ref<Binding[]>([])
const busy = ref(false), error = ref(''), selected = ref<Binding|null>(null), fingerprint = ref('')
let stopped = false, loadVersion = 0
async function load() {
  const version = ++loadVersion
  try { const r = await getJsonStrict<{items:Binding[]}>('/codex/device-bindings'); if (!stopped && version===loadVersion) {items.value=r.items;error.value=''} }
  catch { if (!stopped && version===loadVersion) error.value = '接入审批状态读取失败，请刷新重试。' }
}
async function updateAccess(item:Binding, authMode:'api_key'|'hardware', approved:boolean) {
  if (busy.value) return
  busy.value=true;error.value=''
  try {
    await mutateJsonStrict(`/codex/devices/${encodeURIComponent(item.device_id)}/access`,'PATCH',{
      revision:item.access_revision,authMode,approved,
    })
    await load()
  } catch {error.value='修改未完成或状态已改变，请刷新核对。'}
  finally {busy.value=false}
}
function changeMode(item:Binding, event:Event) {
  const value=(event.target as HTMLSelectElement).value as 'api_key'|'hardware'
  void updateAccess(item,value,!!item.access_approved_at)
}
async function approveHardware() {
  if (!selected.value?.claim_id || fingerprint.value.trim() !== selected.value.candidate_fingerprint) return
  busy.value = true; error.value = ''
  try {
    await mutateJsonStrict(`/codex/device-bindings/${encodeURIComponent(selected.value.claim_id)}/approve`, 'POST', {fingerprint:fingerprint.value.trim()})
    selected.value = null; fingerprint.value = ''; await load()
  } catch { error.value = '硬件绑定批准未完成，请刷新核对。' }
  finally { busy.value = false }
}
onMounted(load)
watch(()=>props.refreshKey,load)
onUnmounted(()=>{stopped=true;loadVersion++})
</script>
<template>
  <section class="binding-panel" aria-label="接入审批与验证方式">
    <header><div><h3>接入审批与验证方式</h3><p>批准后可直接使用原 Key 接入，硬件绑定按需选择。</p></div><button :disabled="busy" @click="load">刷新审批</button></header>

    <p v-if="error" role="alert">{{ error }}</p>
    <div class="scroll"><table><thead><tr><th>接入名称</th><th>验证方式</th><th>接入审批</th><th>操作</th><th>硬件绑定</th></tr></thead><tbody>
      <tr v-for="item in items" :key="item.claim_id || item.device_id">
        <td>{{ item.device_name }}</td>
        <td><select :value="item.auth_mode" :disabled="busy || item.access_revision==null" :aria-label="`${item.device_name} 验证方式`" @change="changeMode(item,$event)"><option value="api_key">普通 API Key</option><option value="hardware">硬件绑定</option></select></td>
        <td>{{ item.access_approved_at ? '已批准' : '待批准' }}</td>
        <td><button :disabled="busy || item.access_revision==null" @click="updateAccess(item,item.auth_mode,!item.access_approved_at)">{{ item.access_approved_at ? '取消批准' : '批准接入' }}</button></td>
        <td v-if="item.auth_mode==='hardware'"><span>{{ item.approved_at ? '已绑定 · 请求须签名' : item.claim_id ? '待指纹核对' : '待设备申请' }}</span><details><summary>查看／核对指纹</summary><code>{{ item.fingerprint || item.candidate_fingerprint || '尚无指纹' }}</code><button v-if="item.claim_id" :disabled="busy" @click="selected=item;fingerprint=''">核对硬件指纹</button></details></td>
        <td v-else>无需连接器</td>
      </tr>
      <tr v-if="!items.length"><td colspan="5">暂无接入记录。</td></tr>
    </tbody></table></div>
    <details><summary>可选：硬件绑定与连接器说明</summary><p>普通 Key 按接入记录识别归属；多个实体设备共用一个 Key 会合并统计。需要验证实体设备时，可选择硬件绑定，并核对设备指纹。</p><p>仅选择硬件绑定的设备需要。<a href="/codex-device-binding-rc.10.zip" download>下载连接器与操作说明</a>。批准前核对设备端显示的完整指纹。</p></details>
    <form v-if="selected" @submit.prevent="approveHardware"><p>为 {{ selected.device_name }} 批准硬件绑定并启用硬件验证：请从设备端取得完整指纹并粘贴。</p><input v-model="fingerprint" aria-label="设备端完整指纹" autocomplete="off" maxlength="64" placeholder="设备端显示的64位指纹" /><button :disabled="busy || fingerprint.trim() !== selected.candidate_fingerprint">批准硬件绑定</button><button type="button" :disabled="busy" @click="selected=null">取消</button></form>
  </section>
</template>
<style scoped>
.binding-panel{margin-top:12px;padding:16px 18px;border:1px solid #dfe6ef;border-radius:12px;background:white;color:#34465b;font-size:12px}header{display:flex;justify-content:space-between;align-items:center;gap:12px}h3{margin:0;font-size:14px}p{line-height:1.7;color:#77869a}button,select{padding:6px 10px;background:white;border:1px solid #ccd8e7;border-radius:6px;color:#34639a;cursor:pointer}button:disabled,select:disabled{opacity:.5}a{color:#2767ad}.scroll{overflow:auto;max-height:360px}table{border-collapse:collapse;width:100%;font-size:11px}td,th{padding:9px;text-align:left;border-top:1px solid #edf1f6}code{display:block;overflow-wrap:anywhere;max-width:340px}input{width:min(580px,100%);padding:8px;margin:0 8px 8px 0;border:1px solid #ccd8e7;border-radius:6px;box-sizing:border-box}details{margin-top:12px}summary{cursor:pointer}
</style>

<style scoped>.binding-panel{margin-top:0;padding:22px;font-size:13px}.binding-panel h3{font-size:16px}.binding-panel table{font-size:13px}.binding-panel .scroll{max-height:none}.binding-panel code{font-size:12px;margin:8px 0}.binding-panel td details{margin-top:6px}</style>
