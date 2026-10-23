<script setup lang="ts">
import { ref,onUnmounted } from 'vue'
import { getJsonStrict } from '../api/client'
import type { Attribution } from '../utils/codexAttribution'
import { allocationLabel } from '../utils/codexAttribution'
const props=defineProps<{value?:Attribution; fresh:boolean;names?:Record<string,string>}>()
type Shares=Record<string,{userId:number;micros:number}>
type Revision={revision:number;recordedAt:string;reason:string;before:Shares;after:Shares;evidence:{partialMeasurement:boolean;weights:Record<string,number>}}
const history=ref<{batchId:string;revisions:Revision[]}|null>(null),error=ref(''),loading=ref(false)
let stopped=false
onUnmounted(()=>{stopped=true})
async function loadHistory(id:string){
  if(loading.value)return
  loading.value=true;error.value=''
  try{const result=await getJsonStrict<{batchId:string;revisions:Revision[]}>(`/codex/quota-batches/${encodeURIComponent(id)}/revisions`);if(!stopped)history.value=result}
  catch{if(!stopped)error.value='暂时无法读取修订记录，请稍后重试。'}
  finally{if(!stopped)loading.value=false}
}
function changes(row:Revision){
  return [...new Set([...Object.keys(row.before),...Object.keys(row.after)])].sort().map(id=>{
    const before=row.before[id],after=row.after[id]
    return `${props.names?.[id]||'历史设备'}：${before?allocationLabel(before.micros/1000000):'未分配'} → ${after?allocationLabel(after.micros/1000000):'待归属'}`
  }).join('；')||'暂无可归属金额，继续等待计量'
}
const status:Record<string,string>={'provisional':'暂估 · 自动回算','observed-estimate':'观察后估算 · 可修订','waiting':'等待计量 · 待归属','unattributed':'证据缺口 · 待归属'}
const time=(v:string)=>new Date(v).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false})
</script>
<template>
  <section v-if="value?.batchMonitoring" class="batch-panel" aria-label="额度暂估与迟到计量回算">
    <h2>额度暂估与自动回算</h2>
    <p v-if="!fresh">数据暂不可确认，以下批次为历史记录，等待采集恢复。</p>
    <div class="batch-summary">
      <span>已归属中的暂估 <b>{{fresh?allocationLabel(value.provisionalPercent??0):'—'}}</b></span>
      <span>批次待归属 <b>{{fresh?allocationLabel(value.batchMonitoring.pendingBatchPercent):'—'}}</b></span>
      <span>自动回算 <b>{{value.batchMonitoring.recalculationCount}}</b> 次</span>
    </div>
    <p>迟到计量按原请求时间归入对应观察组，并自动修订暂估批次；连续使用时继续显示暂估，无需停止全部任务。相邻 {{value.batchMonitoring.observationSeconds/60}} 分钟内的额度增量合并观察，稳定后仍可因补账修订。本人确认与升级前已结算记录保留。占比始终为估算，具体 Token 独立计量。</p>
    <p>新版统计起点：{{time(value.batchMonitoring.cutoverAt)}} · 最近核对：{{time(value.batchMonitoring.capturedAt)}}</p>
    <div class="batch-scroll"><table><thead><tr><th>批次 / 官方采样</th><th>额度增量</th><th>状态</th><th>待归属</th><th>版本 / 最近修订</th></tr></thead>
      <tbody><tr v-for="b in value.batchMonitoring.latestBatches" :key="b.batchId">
        <td>{{b.batchId.slice(0,8)}}<small>{{time(b.quotaCapturedAt)}}</small></td>
        <td>{{allocationLabel(b.points)}}</td><td>{{status[b.status]||'待核对'}}<small>依据完整性：{{b.confidence==='unavailable'?'不足':b.confidence==='low'?'有限':'较完整'}}；非官方逐设备账单</small></td>
        <td>{{allocationLabel(b.unattributedPercent)}}</td><td>v{{b.revision}}<small>{{time(b.updatedAt)}}</small><button :disabled="loading || !b.revision" @click="loadHistory(b.batchId)">查看修订</button></td>
      </tr><tr v-if="!value.batchMonitoring.latestBatches.length"><td colspan="5">新机制已启用，等待下一次官方额度增量；此前已计量 Token 保持显示。</td></tr></tbody>
    </table></div>
    <p v-if="error" role="alert">{{error}}</p>
    <div v-if="history" class="history"><h3>批次 {{history.batchId.slice(0,8)}} 的修订记录 <button @click="history=null">收起</button></h3>
      <p v-for="row in history.revisions" :key="row.revision"><b>v{{row.revision}}</b> · {{time(row.recordedAt)}}<br/>{{changes(row)}}<br/>依据：原请求时间及已计量 Token；{{row.evidence.partialMeasurement?'计量仍不完整，继续暂估':'已观察到计量，仍为额度估算'}}。</p>
    </div>
    <p>本区最多展示最近12个批次，完整修订记录在后台保留。暂估已包含在人员额度中，请勿再次相加；批次待归属包含在账户待归属中。</p>
  </section>
</template>
<style scoped>
.batch-panel{padding:16px 20px;margin:14px 0;border:1px solid #dce7f3;border-radius:14px;background:#fff}.batch-panel h2{font-size:16px;margin:0 0 10px}.batch-panel p{font-size:12px;line-height:1.7;color:#71829b}.batch-summary{display:flex;gap:24px;flex-wrap:wrap;font-size:13px;color:#60718b}.batch-summary b{color:#285e97;margin-left:6px}.batch-scroll{overflow:auto}table{width:100%;border-collapse:collapse;font-size:12px;text-align:left;min-width:660px}th,td{padding:10px;border-bottom:1px solid #edf1f6}th{color:#71829b}small{display:block;margin-top:5px;font-size:10px;color:#8190a5}
</style>
