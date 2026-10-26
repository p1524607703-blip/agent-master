<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { getJsonStrict, mutateJsonStrict } from '../api/client'
type Policy={revision:number;availableModels:string[];enabledModels:string[]}
const emit=defineEmits<{changed:[]}>()
const policy=ref<Policy|null>(null),busy=ref(false),error=ref(''),notice=ref('')
const label=(id:string)=>id==='gpt-6-astra'?'Astra':id==='gpt-6.1-sol'?'GPT-6.1 Sol':id
async function load(){try{policy.value=await getJsonStrict<Policy>('/codex/model-settings');error.value=''}catch{error.value='模型开放状态暂不可读取，请刷新。'}}
async function toggle(id:string){
 if(!policy.value||busy.value)return
 busy.value=true;error.value='';notice.value=''
 const enabled=policy.value.enabledModels.includes(id)
 try{
  await mutateJsonStrict('/codex/model-settings','PATCH',{revision:policy.value.revision,enabledModels:enabled?policy.value.enabledModels.filter(m=>m!==id):[...policy.value.enabledModels,id]})
  await load();notice.value=`${label(id)} 已${enabled?'关闭':'开放'}。`;emit('changed')
 }catch{error.value='设置未确认或已被其他管理员修改，请刷新核对。'}finally{busy.value=false}
}
onMounted(load)
</script>
<template>
 <section class="model-panel" aria-label="模型开放选择">
  <header><div><h2>模型开放选择</h2><p>对所有已批准的 API Key 生效，使用现有服务器地址即可选择模型。</p></div><button :disabled="busy" @click="load">刷新模型</button></header>
  <p v-if="error" role="alert" class="error">{{error}}</p><p v-if="notice" role="status">{{notice}}</p>
  <div class="model-grid"><article v-for="id in policy?.availableModels" :key="id"><div><strong>{{label(id)}}</strong><code>{{id}}</code><small>{{policy?.enabledModels.includes(id)?'已开放 · 客户端可选择':'已关闭 · 新请求不可使用'}}</small></div><button role="switch" :aria-label="`${label(id)} 模型开放`" :aria-checked="policy?.enabledModels.includes(id)" :class="{on:policy?.enabledModels.includes(id)}" :disabled="busy" @click="toggle(id)"><span></span></button></article></div>
  <p v-if="policy && !policy.enabledModels.length">当前没有开放模型。开启至少一个模型后，设备才能调用。</p>
  <p class="hint">关闭会阻止新请求和尚在排队的请求，正在执行的任务继续完成。模型共用上游账户额度；客户端列表未更新时，可刷新模型列表或填写上面的模型名。</p>
 </section>
</template>
<style scoped>
.model-panel{padding:22px;border:1px solid #dfe6ef;border-radius:14px;background:#fff}.model-panel header{display:flex;justify-content:space-between;align-items:center;gap:16px}h2{font-size:16px;margin:0}p{font-size:13px;line-height:1.7;color:#718096;margin:6px 0}.model-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px;margin:18px 0}.model-grid article{display:flex;align-items:center;justify-content:space-between;gap:16px;background:#f7f9fc;border:1px solid #e4eaf2;padding:18px;border-radius:10px}strong{font-size:17px}code,small{display:block;margin-top:8px;color:#6a7c91;font-size:12px}button{border:1px solid #d6e0ec;background:white;color:#3e5e87;border-radius:7px;padding:7px 12px;cursor:pointer}button:disabled{opacity:.5;cursor:default}button[role=switch]{width:40px;height:24px;border:0;border-radius:14px;padding:3px;background:#aab8c9;flex-shrink:0}button[role=switch] span{display:block;width:18px;height:18px;border-radius:50%;background:#fff;transition:transform .15s}.on{background:#28866b!important}.on span{transform:translateX(16px)}.error{color:#b44343}.hint{font-size:12px}
</style>
