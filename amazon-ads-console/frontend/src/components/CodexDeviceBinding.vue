<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { getJsonStrict, mutateJsonStrict } from '../api/client'
type Binding = {device_id:string;device_name:string;fingerprint:string|null;approved_at:string|null;claim_id:string|null;candidate_fingerprint:string|null;provider:string|null}
const items = ref<Binding[]>([])
const busy = ref(false), error = ref(''), selected = ref<Binding|null>(null), fingerprint = ref('')
let stopped = false
async function load() {
  try { const r = await getJsonStrict<{items:Binding[]}>('/codex/device-bindings'); if (!stopped) items.value = r.items }
  catch { if (!stopped) error.value = '设备绑定状态读取失败，请刷新重试。' }
}
async function approve() {
  if (!selected.value?.claim_id || fingerprint.value.trim() !== selected.value.candidate_fingerprint) return
  busy.value = true; error.value = ''
  try {
    await mutateJsonStrict(`/codex/device-bindings/${encodeURIComponent(selected.value.claim_id)}/approve`, 'POST', {fingerprint:fingerprint.value.trim()})
    selected.value = null; fingerprint.value = ''; await load()
  } catch { error.value = '批准未完成或已被其他管理员处理，请刷新核对。' }
  finally { busy.value = false }
}
onMounted(load)
onUnmounted(()=>{stopped=true})
</script>
<template>
  <section class="binding-panel" aria-label="设备绑定">
    <header><div><h3>一设备一 Key · 设备绑定</h3><p>Key 须安装连接器并获批准；单独复制 Key 无法调用模型。换机请撤销旧 Key 后重新创建。</p></div><button :disabled="busy" @click="load">刷新绑定</button></header>
    <p>客户端使用本机连接器的供应商配置，并通过「Codex多开」启动，保留原窗口。<a href="/codex-device-binding-rc.10.zip" download>下载连接器与操作说明</a></p>
    <p>批准前，请核对设备端显示的完整指纹。首次申请不会自动获准；硬件密钥由受信安装器创建，此处不提供远程硬件证明。</p>
    <p v-if="error" role="alert">{{ error }}</p>
    <div class="scroll"><table><thead><tr><th>设备</th><th>状态</th><th>设备指纹</th><th>操作</th></tr></thead><tbody>
      <tr v-for="item in items" :key="item.claim_id || item.device_id"><td>{{ item.device_name }}</td><td>{{ item.approved_at ? '已绑定 · 签名必需' : item.claim_id ? '待管理员批准' : '待设备申请 · 已阻止直接接入' }}</td><td><code>{{ item.fingerprint || item.candidate_fingerprint || '—' }}</code></td><td><button v-if="item.claim_id" :disabled="busy" @click="selected=item;fingerprint=''">核对并批准</button></td></tr>
    </tbody></table></div>
    <form v-if="selected" @submit.prevent="approve"><p>批准 {{ selected.device_name }}：请从设备端取得指纹并粘贴。</p><input v-model="fingerprint" aria-label="设备端完整指纹" autocomplete="off" maxlength="64" placeholder="设备端显示的64位指纹" /><button :disabled="busy || fingerprint.trim() !== selected.candidate_fingerprint">批准绑定</button><button type="button" :disabled="busy" @click="selected=null">取消</button></form>
  </section>
</template>
<style scoped>
.binding-panel{margin-top:12px;padding:16px 18px;border:1px solid #dfe6ef;border-radius:12px;background:white;color:#34465b;font-size:12px}header{display:flex;justify-content:space-between;align-items:center;gap:12px}h3{margin:0;font-size:14px}p{line-height:1.7;color:#77869a}button{padding:6px 10px;background:white;border:1px solid #ccd8e7;border-radius:6px;color:#34639a;cursor:pointer}button:disabled{opacity:.5}a{color:#2767ad}.scroll{overflow:auto;max-height:300px}table{border-collapse:collapse;width:100%;font-size:11px}td,th{padding:9px;text-align:left;border-top:1px solid #edf1f6}code{overflow-wrap:anywhere}input{width:min(580px,100%);padding:8px;margin:0 8px 8px 0;border:1px solid #ccd8e7;border-radius:6px;box-sizing:border-box}
</style>
