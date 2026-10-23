<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { getJsonStrict, mutateJsonStrict } from '../api/client'
import CodexDeviceBinding from './CodexDeviceBinding.vue'

type Device = {deviceId:string; deviceName:string; platform:string; revoked:boolean; sourceKind?:string}
type Member = {userId:number; displayName:string; devices:Device[]}
type Credential = Device & {userId:number; displayName:string}
type Access = {baseUrl:string|null; models:string[]; modelsAvailable:boolean; protocol:string}
const props = defineProps<{members:Member[]; selectedId:number|null}>()
const emit = defineEmits<{changed:[]}>()
const access = ref<Access|null>(null)
const configLoading = ref(false)
const expanded = ref(false)
const mode = ref<'create'|'rename'|'revoke'|null>(null)
const editing = ref<Credential|null>(null)
const accessName = ref('')
const owner = ref<number|null>(null)
const platform = ref('windows')
const working = ref(false)
const error = ref('')
const notice = ref('')
const issued = ref<{deviceId:string; apiKey:string}|null>(null)
const reveal = ref(false)
const bindingRefresh = ref(0)
let stopped = false
const credentials = computed<Credential[]>(() => props.members.flatMap(m => m.devices
  .filter(d=>d.sourceKind!=='local-host').map(d=>({...d,userId:m.userId,displayName:m.displayName}))))
const heading = computed(() => issued.value ? 'API Key 已创建' : mode.value==='create' ? '创建 API Key' : mode.value==='rename' ? '修改接入名称' : '撤销 API Key')

async function load() {
  configLoading.value = true
  try { const result = await getJsonStrict<Access>('/codex/access-config'); if (!stopped) access.value = result }
  catch { if (!stopped) notice.value = '接入信息暂时无法读取，请稍后刷新。' }
  finally { configLoading.value = false }
}
function open(action:'create'|'rename'|'revoke', credential?:Credential) {
  error.value = ''; notice.value = ''; issued.value = null; reveal.value = false
  editing.value = credential || null; accessName.value = credential?.deviceName || ''
  owner.value = props.selectedId ?? props.members[0]?.userId ?? null
  platform.value = 'windows'; mode.value = action
}
function close() {
  if (working.value) return
  issued.value = null; reveal.value = false; editing.value = null; mode.value = null; error.value = ''
}
async function submit() {
  if (working.value) return
  const name = accessName.value.trim()
  if (mode.value!=='revoke' && (!name || name.length>80 || /[\x00-\x1f\x7f]/.test(name))) {
    error.value = '请填写 1–80 个字符的单行接入名称。'; return
  }
  if (mode.value==='create' && !owner.value) {error.value='请选择归属人员。';return}
  working.value = true; error.value = ''
  const action = mode.value
  try {
    if (action==='create') {
      const result = await mutateJsonStrict<{deviceId:string;apiKey:string}>('/codex/devices','POST',{
        userId:owner.value,deviceName:name,platform:platform.value,
      })
      if (stopped) return
      issued.value = result; expanded.value = true
    } else if (editing.value) {
      const id = encodeURIComponent(editing.value.deviceId)
      if (action==='rename') await mutateJsonStrict(`/codex/devices/${id}`,'PATCH',{deviceName:name})
      else await mutateJsonStrict(`/codex/devices/${id}`,'DELETE')
      if (stopped) return
      notice.value = action==='rename' ? '接入名称已更新，API Key 保持不变。' : 'API Key 已撤销，历史用量保留。'
      mode.value = null; editing.value = null
    }
    emit('changed')
    bindingRefresh.value++
  } catch (e) {
    if (!stopped) error.value = action==='create'
      ? '创建结果未确认，请刷新列表核对后再操作；已创建的密钥无法再次查看。'
      : e instanceof Error ? e.message : '操作未完成，请稍后重试。'
  } finally { working.value = false }
}
async function copy(text:string|undefined|null) {
  if (!text) return
  try {
    await navigator.clipboard.writeText(text)
    if (!stopped) notice.value = '已复制。'
  } catch { if (!stopped) notice.value = '浏览器未允许复制，请选中内容手动复制。' }
}
onMounted(()=>{void load()})
onUnmounted(()=>{stopped=true;issued.value=null;reveal.value=false})
</script>

<template>
  <section class="access-panel" aria-label="API 接入与密钥">
    <header><div><h2>API 接入与密钥</h2><p>管理员签发、批准独立 Key，按归属人员记录用量；普通接入无需安装连接器。</p></div><button class="primary" :disabled="!access?.baseUrl || !members.length" @click="open('create')">创建 API Key</button></header>
    <div class="connection-fields">
      <label><span>HTTPS 服务器地址</span><div class="copy-field"><input aria-label="HTTPS Base URL" readonly :value="access?.baseUrl || ''" :placeholder="configLoading ? '正在读取…' : '管理员尚未发布接入地址'" /><button :disabled="!access?.baseUrl" @click="copy(access?.baseUrl)">复制地址</button></div></label>
      <div class="model-info"><span>协议：Responses API</span><span>模型：{{ access?.models.join('、') || (configLoading ? '读取中…' : '暂未取得模型列表') }}</span><button @click="load" :disabled="configLoading">刷新接入信息</button></div>
    </div>
    <div class="key-toolbar"><span>Key 新建时仅显示一次；在下方批准后，将服务器地址和 Key 填入 Codex++。</span><button @click="expanded=!expanded">{{ expanded ? '收起密钥列表' : `管理 API Key（${credentials.length}）` }}</button></div>
    <p v-if="notice" class="notice" role="status">{{ notice }}</p>
    <div v-if="expanded" class="key-table-wrap"><table><thead><tr><th>接入名称</th><th>归属人员</th><th>系统</th><th>密钥状态</th><th>管理</th></tr></thead><tbody>
      <tr v-for="item in credentials" :key="item.deviceId"><td>{{ item.deviceName }}</td><td>{{ item.displayName }}</td><td>{{ item.platform }}</td><td>{{ item.revoked ? '已撤销' : '已签发 · 密钥已隐藏' }}</td><td class="row-actions"><button :disabled="item.revoked" @click="open('rename',item)">改名</button><button class="danger-text" :disabled="item.revoked" @click="open('revoke',item)">撤销</button></td></tr>
      <tr v-if="!credentials.length"><td colspan="5">尚未签发 API Key。</td></tr>
    </tbody></table></div>
  </section>

  <CodexDeviceBinding :refresh-key="bindingRefresh" />
  <div v-if="mode" class="access-overlay">
    <section role="dialog" aria-modal="true" aria-labelledby="access-dialog-title" class="access-dialog">
      <header><h2 id="access-dialog-title">{{ heading }}</h2><button aria-label="关闭密钥管理" :disabled="working" @click="close">关闭</button></header>
      <template v-if="issued">
        <p>请现在复制并保存此 Key。关闭后无法再次查看。</p>
        <label><span>接入名称</span><input readonly :value="accessName.trim()" /></label>
        <label><span>API Key</span><div class="copy-field"><input aria-label="新建 API Key" readonly autocomplete="off" :type="reveal?'text':'password'" :value="issued.apiKey" /><button @click="reveal=!reveal">{{ reveal?'隐藏':'显示' }}</button><button @click="copy(issued.apiKey)">复制 Key</button></div></label>
        <label><span>HTTPS Base URL</span><div class="copy-field"><input readonly :value="access?.baseUrl || ''" /><button @click="copy(access?.baseUrl)">复制地址</button></div></label>
        <p>此 Key 创建后处于待批准状态，请在接入审批区批准。普通 API 模式直接使用上述服务器地址和 Key，无需安装连接器；原有有效 Key 可继续沿用。</p>
        <p>模型：{{ access?.models.join('、') || '请刷新模型列表' }} · 协议：Responses API</p>
        <p v-if="notice" role="status" class="notice">{{ notice }}</p>
        <footer><button class="primary" @click="close">已保存，关闭</button></footer>
      </template>
      <form v-else @submit.prevent="submit">
        <template v-if="mode==='create'">
          <label><span>归属人员</span><select v-model="owner" required><option v-for="member in members" :key="member.userId" :value="member.userId">{{ member.displayName }}</option></select></label>
          <label><span>使用系统</span><select v-model="platform"><option value="windows">Windows</option><option value="macos">macOS</option><option value="linux">Linux</option></select></label>
        </template>
        <label v-if="mode!=='revoke'"><span>接入名称</span><input v-model="accessName" required maxlength="80" autocomplete="off" placeholder="例如：YE 的工作电脑" /></label>
        <p v-if="mode==='rename'">改名仅更新显示名称，API Key 和历史用量保持不变。</p>
        <p v-if="mode==='revoke'">撤销“{{ editing?.deviceName }}”后，该 Key 将无法发起新请求。已经记录的用量保留。</p>
        <p v-if="error" class="operation-error" role="alert">{{ error }}</p>
        <footer><button type="button" :disabled="working" @click="close">取消</button><button :class="mode==='revoke'?'danger':'primary'" :disabled="working">{{ working ? '处理中…' : mode==='revoke' ? '确认撤销' : mode==='rename' ? '保存名称' : '创建并显示 Key' }}</button></footer>
      </form>
    </section>
  </div>
</template>

<style scoped>
.access-panel{margin-top:12px;padding:14px 18px;border:1px solid #dfe6ef;border-radius:12px;background:#fff;color:#34465b}
header{display:flex;justify-content:space-between;align-items:center;gap:16px}h2{margin:0;font-size:14px;color:#1b2a3d}p{margin:5px 0;color:#7a899a;font-size:11px;line-height:1.7}
button{border:1px solid #d6e0ec;border-radius:7px;background:white;padding:6px 11px;color:#48668b;cursor:pointer;font:inherit;font-size:11px;white-space:nowrap}button:disabled{opacity:.5;cursor:default}.primary{background:#2767ad;border-color:#2767ad;color:white}.danger{background:#b44040;border-color:#b44040;color:white}.danger-text{color:#ad4444}
.connection-fields{display:grid;grid-template-columns:minmax(240px,1.4fr) minmax(180px,1fr);gap:18px;margin-top:12px}label{display:block;font-size:11px}label>span{display:block;color:#8290a1;margin-bottom:5px}.copy-field{display:flex;gap:6px;align-items:center;min-width:0}input,select{min-width:0;width:100%;padding:8px 9px;border:1px solid #dce4ee;border-radius:7px;background:#fbfcfe;color:#34465b;font:inherit;font-size:12px;box-sizing:border-box}.copy-field input{flex:1}.model-info{display:flex;gap:6px;flex-wrap:wrap;align-items:center;font-size:11px;color:#8290a1}.model-info span{margin-right:8px;overflow-wrap:anywhere}
.key-toolbar{display:flex;justify-content:space-between;align-items:center;gap:14px;margin-top:10px;font-size:10px;color:#8a97a8}.notice{color:#2c8061;margin-top:7px}.key-table-wrap{overflow:auto;max-height:240px;margin-top:10px}table{width:100%;border-collapse:collapse;font-size:11px;white-space:nowrap}th,td{text-align:left;border-top:1px solid #edf1f6;padding:9px}th{color:#8290a1;font-weight:500}.row-actions{display:flex;gap:7px}.row-actions button{padding:3px 8px}
.access-overlay{position:fixed;inset:0;z-index:1000;display:grid;place-items:center;padding:24px;background:rgba(28,42,60,.4)}.access-dialog{width:min(540px,100%);max-height:85vh;overflow:auto;background:#fff;border-radius:14px;padding:22px;box-shadow:0 15px 70px #17233430}.access-dialog label{margin-top:14px}.access-dialog footer{display:flex;justify-content:flex-end;gap:9px;margin-top:20px}.operation-error{color:#b34040}
@media(max-width:750px){.connection-fields{grid-template-columns:1fr}.key-toolbar{align-items:flex-start}.access-panel header{align-items:flex-start}.access-overlay{padding:12px}}
</style>
