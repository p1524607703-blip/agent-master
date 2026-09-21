<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { getJson, postBinary, postEmpty } from '../api/client'
import { NButton, NDatePicker, NIcon, NUpload, NUploadDragger, type UploadSettledFileInfo } from 'naive-ui'
import { Upload } from '@vicons/tabler'
import DataSkeleton from '../components/DataSkeleton.vue'

type SourceItem = { account:string; reportType:string; date:string; rows:number; status:'READY'|'MISSING'|'NOT_REQUIRED' }
type SourceStatus = { data_date:string; items:SourceItem[]; required:number; ready:number; blockers:string[] }
type UploadResult = { status:string; code?:string; message?:string; token?:string; rows?:number; loaded?:number; file_name?:string; actual_data_date?:string; detected_dates?:string[]; date_message?:string; target_date?:string; date_source?:string }
type ReportRow = { date:string }

const accounts = ['川鹏','欧德思','洁博利','AMS']
const selectedDate = ref('')
const loading = ref(true)
const status = ref<SourceStatus>({ data_date:'', items:[], required:7, ready:0, blockers:[] })
const uploadState = ref<Record<string,{busy:boolean;message:string;tone:'ok'|'warn'|'idle'}>>({})
const pendingConfirm = ref<Record<string,{token:string;message:string;actualDate:string;dates:string[];dateSource:string}>>({})

const keyOf = (account:string,type:string) => `${account}|${type}`

const loadStatus = async () => {
  if (!selectedDate.value) return
  loading.value = true
  status.value = await getJson<SourceStatus>(`/cpo/source-status?date=${selectedDate.value}`, { data_date:selectedDate.value, items:[], required:7, ready:0, blockers:accounts })
  loading.value = false
}

const init = async () => {
  const reports = await getJson<ReportRow[]>('/reports', [])
  const dates = reports.map(r=>r.date).filter(Boolean).sort()
  selectedDate.value = dates.at(-1) || new Date().toISOString().slice(0,10)
  await loadStatus()
}

const sourceFor = (account:string, reportType:string): SourceItem => {
  if (account==='AMS' && reportType==='业务报告') return { account,reportType,date:selectedDate.value,rows:0,status:'NOT_REQUIRED' }
  return status.value.items.find(x=>x.account===account && x.reportType===reportType) || { account,reportType,date:selectedDate.value,rows:0,status:'MISSING' }
}

const cardState = (account:string,type:string) => {
  const s=sourceFor(account,type)
  if (s.status==='NOT_REQUIRED') return {tone:'na',label:'无需上传',detail:'AMS 为广告子账户，不提供业务报告',rows:null as number|null,date:'—'}
  if (s.status==='READY') return {tone:'ready',label:'已识别',detail:'数据库中已存在当前日期数据',rows:s.rows,date:s.date}
  return {tone:'empty',label:'等待上传',detail:'当前日期数据库中没有该报告',rows:null as number|null,date:selectedDate.value}
}

const accountState = (account:string) => {
  const b=sourceFor(account,'业务报告'); const a=sourceFor(account,'CPO推广商品')
  return { business:cardState(account,'业务报告'), ads:cardState(account,'CPO推广商品'), ready: account==='AMS' ? a.status==='READY' : b.status==='READY' && a.status==='READY' }
}

const readySources = computed(()=>status.value.ready)
const requiredSources = computed(()=>status.value.required || 7)
const blockers = computed(()=>status.value.blockers || [])
const formatRows = (v:number|null) => v == null ? '—' : Number(v).toLocaleString()

const processUpload = async (account:string, reportType:string, file?:File) => {
  if (!file || !selectedDate.value) return
  const k=keyOf(account,reportType)
  if (uploadState.value[k]?.busy) return
  if (!file.name.toLowerCase().endsWith('.csv')) {
    uploadState.value[k]={busy:false,message:'当前仅支持 CSV 报告文件',tone:'warn'}
    return
  }
  uploadState.value[k]={busy:true,message:`正在校验 ${file.name}…`,tone:'idle'}
  const qs=`?account=${encodeURIComponent(account)}&report_type=${encodeURIComponent(reportType)}&date=${selectedDate.value}`
  const validation=await postBinary<UploadResult>(`/cpo/imports/validate${qs}`,file,{'X-File-Name':encodeURIComponent(file.name)},{status:'BLOCKED',message:'无法连接导入接口'})
  if (validation.status==='DUPLICATE') {
    delete pendingConfirm.value[k]
    uploadState.value[k]={busy:false,message:validation.message || '该文件已导入，无需重复提交',tone:'ok'}
    await loadStatus(); return
  }
  if (validation.status==='CONFIRM_REQUIRED' && validation.token) {
    pendingConfirm.value[k]={
      token:validation.token,
      message:validation.date_message || validation.message || '检测到历史/跨日期报告，需要确认',
      actualDate:validation.actual_data_date || '',
      dates:validation.detected_dates || [],
      dateSource:validation.date_source || 'file_name',
    }
    uploadState.value[k]={busy:false,message:pendingConfirm.value[k].message,tone:'warn'}
    return
  }
  if (validation.status!=='READY' || !validation.token) {
    delete pendingConfirm.value[k]
    uploadState.value[k]={busy:false,message:validation.message || '文件校验未通过',tone:'warn'}
    return
  }
  delete pendingConfirm.value[k]
  uploadState.value[k]={busy:true,message:`校验通过，正在入库 ${validation.rows ?? ''} 行…`,tone:'idle'}
  const committed=await postEmpty<UploadResult>(`/cpo/imports/${validation.token}/commit`,{status:'BLOCKED',message:'提交入库失败'})
  if (committed.status==='IMPORTED' || committed.status==='DUPLICATE') {
    uploadState.value[k]={busy:false,message:committed.status==='IMPORTED' ? `导入成功 · ${committed.loaded ?? validation.rows ?? 0} 行` : '文件已由其他入口导入',tone:'ok'}
    await loadStatus()
  } else {
    uploadState.value[k]={busy:false,message:committed.message || '导入失败',tone:'warn'}
  }
}

const confirmReportDate = async (account:string, reportType:string) => {
  const k=keyOf(account,reportType)
  const pending=pendingConfirm.value[k]
  if (!pending) return
  const usesTargetDate=pending.dateSource==='explicit_target_date'
  uploadState.value[k]={busy:true,message:usesTargetDate ? '正在按已确认的目标日期入库…' : '正在按文件实际日期补录…',tone:'idle'}
  const committed=await postEmpty<UploadResult>(`/cpo/imports/${pending.token}/commit?confirm_historical=true`,{status:'BLOCKED',message:'日期确认入库失败'})
  if (committed.status==='IMPORTED' || committed.status==='DUPLICATE') {
    const success=usesTargetDate ? '确认日期入库成功' : '历史补录成功'
    uploadState.value[k]={busy:false,message:committed.status==='IMPORTED' ? `${success} · 数据日期 ${committed.actual_data_date || pending.actualDate || '已确认日期'} · ${committed.loaded ?? 0} 行` : (committed.message || '文件已导入'),tone:'ok'}
    delete pendingConfirm.value[k]
    await loadStatus()
  } else {
    uploadState.value[k]={busy:false,message:committed.message || '日期确认入库失败',tone:'warn'}
  }
}

const cancelHistorical = (account:string, reportType:string) => {
  const k=keyOf(account,reportType)
  delete pendingConfirm.value[k]
  uploadState.value[k]={busy:false,message:'已取消本次历史补录',tone:'idle'}
}

const handleUploadChange = async (account:string, reportType:string, data:{ file:UploadSettledFileInfo }) => {
  await processUpload(account, reportType, data.file.file || undefined)
}

watch(selectedDate, async (n,o)=>{ if(n && o && n!==o) await loadStatus() })
onMounted(init)
</script>

<template>
  <section class="page cpo-page">
    <div class="page-head cpo-head">
      <div>
        <h1>CPO 处理中心</h1>
        <p>自动化负责日常入库；这里负责查看数据是否齐全，以及手动补传缺失报告。</p>
      </div>
      <div class="date-box">
        <label>目标数据日</label>
        <NDatePicker
          :formatted-value="selectedDate || null"
          value-format="yyyy-MM-dd"
          type="date"
          clearable
          style="width:160px"
          @update:formatted-value="v => selectedDate = v || ''"
        />
      </div>
    </div>

    <DataSkeleton v-if="loading" variant="cards" :rows="6" />

    <div v-if="!loading" class="daily-summary card">
      <div class="summary-copy">
        <span class="eyebrow">每日数据准备</span>
        <strong>{{ readySources }} / {{ requiredSources }}</strong>
        <span>个必需数据源已入库</span>
      </div>
      <div class="summary-status" :class="blockers.length ? 'blocked' : 'ready'">
        {{ blockers.length ? `${blockers.length} 个账户尚未就绪` : '全部账户已就绪' }}
      </div>
    </div>

    <div v-if="!loading" class="account-stack">
      <section v-for="account in accounts" :key="account" class="account-row">
        <div class="account-label">
          <div>
            <h2>{{ account }}</h2>
            <span :class="['account-state', accountState(account).ready ? 'ready' : 'blocked']">
              {{ accountState(account).ready ? '可计算' : '待补数据' }}
            </span>
          </div>
        </div>

        <div class="source-grid">
          <div class="source-card card" :class="accountState(account).business.tone">
            <div class="source-card-head">
              <div><span class="source-kicker">业务侧</span><h3>子 ASIN 业务报告</h3></div>
              <span class="source-status">{{ accountState(account).business.label }}</span>
            </div>
            <div class="source-main" v-if="account !== 'AMS'">
              <strong>{{ accountState(account).business.date }}</strong>
              <span>{{ formatRows(accountState(account).business.rows) }} 行</span>
            </div>
            <div class="source-main" v-else><strong>无需上传</strong><span>广告子账户</span></div>
            <p>{{ accountState(account).business.detail }}</p>
            <NUpload v-if="account !== 'AMS'"
              class="cpo-upload"
              accept=".csv,text/csv"
              :default-upload="false"
              :show-file-list="false"
              :file-list="[]"
              :max="1"
              :disabled="uploadState[keyOf(account,'业务报告')]?.busy"
              @change="data => handleUploadChange(account,'业务报告',data)">
              <NUploadDragger>
                <div class="upload-content">
                  <NIcon :size="24"><Upload /></NIcon>
                  <div class="upload-copy">
                    <strong>{{ uploadState[keyOf(account,'业务报告')]?.busy ? '处理中…' : '拖拽 CSV 到这里' }}</strong>
                    <small>{{ ['READY','CHILD_READY','LEGACY_PARENT_READY'].includes(sourceFor(account,'业务报告').status) ? '或点击补充 / 重传' : '或点击选择文件' }}</small>
                  </div>
                </div>
              </NUploadDragger>
            </NUpload>
            <div v-if="uploadState[keyOf(account,'业务报告')]?.message" class="upload-message" :class="uploadState[keyOf(account,'业务报告')]?.tone">{{ uploadState[keyOf(account,'业务报告')]?.message }}</div>
            <div v-if="pendingConfirm[keyOf(account,'业务报告')]" class="historical-confirm">
              <NButton size="tiny" type="primary" @click="confirmReportDate(account,'业务报告')">{{ pendingConfirm[keyOf(account,'业务报告')]?.dateSource === 'explicit_target_date' ? '确认按目标日期入库' : '按文件日期补录' }}</NButton>
              <NButton size="tiny" @click="cancelHistorical(account,'业务报告')">取消</NButton>
            </div>
          </div>

          <div class="source-card card" :class="accountState(account).ads.tone">
            <div class="source-card-head">
              <div><span class="source-kicker">广告侧</span><h3>CPO 推广商品</h3></div>
              <span class="source-status">{{ accountState(account).ads.label }}</span>
            </div>
            <div class="source-main"><strong>{{ accountState(account).ads.date }}</strong><span>{{ formatRows(accountState(account).ads.rows) }} 行</span></div>
            <p>{{ accountState(account).ads.detail }}</p>
            <NUpload
              class="cpo-upload"
              accept=".csv,text/csv"
              :default-upload="false"
              :show-file-list="false"
              :file-list="[]"
              :max="1"
              :disabled="uploadState[keyOf(account,'CPO推广商品')]?.busy"
              @change="data => handleUploadChange(account,'CPO推广商品',data)">
              <NUploadDragger>
                <div class="upload-content">
                  <NIcon :size="24"><Upload /></NIcon>
                  <div class="upload-copy">
                    <strong>{{ uploadState[keyOf(account,'CPO推广商品')]?.busy ? '处理中…' : '拖拽 CSV 到这里' }}</strong>
                    <small>{{ sourceFor(account,'CPO推广商品').status==='READY' ? '或点击补充 / 重传' : '或点击选择文件' }}</small>
                  </div>
                </div>
              </NUploadDragger>
            </NUpload>
            <div v-if="uploadState[keyOf(account,'CPO推广商品')]?.message" class="upload-message" :class="uploadState[keyOf(account,'CPO推广商品')]?.tone">{{ uploadState[keyOf(account,'CPO推广商品')]?.message }}</div>
            <div v-if="pendingConfirm[keyOf(account,'CPO推广商品')]" class="historical-confirm">
              <NButton size="tiny" type="primary" @click="confirmReportDate(account,'CPO推广商品')">按文件日期补录</NButton>
              <NButton size="tiny" @click="cancelHistorical(account,'CPO推广商品')">取消</NButton>
            </div>
          </div>
        </div>
      </section>
    </div>

    <div v-if="!loading" class="publish-bar card">
      <div>
        <strong v-if="blockers.length">当前数据源未齐</strong>
        <strong v-else>数据已齐，可以进入 CPO 计算</strong>
        <p v-if="blockers.length">待处理：{{ blockers.join('、') }}</p>
        <p v-else>下一步进入产品范围、Campaign 归属、守恒校验与发布。</p>
      </div>
      <NButton type="primary" disabled>开始 CPO 计算</NButton>
    </div>

    <p v-if="!loading" class="dev-note">业务报告正式口径为子 ASIN 日报；父 ASIN 报告仅作兼容 fallback。日期仍由规范文件名或人工确认的目标数据日确定，不使用下载时间或文件 mtime 推断。</p>
  </section>
</template>

<style scoped>
.cpo-page{position:relative;min-width:0;isolation:isolate}.cpo-page::before,.cpo-page::after{content:"";position:fixed;pointer-events:none;z-index:-1;border-radius:999px;filter:blur(18px);opacity:.42}.cpo-page::before{width:420px;height:420px;right:7vw;top:110px;background:radial-gradient(circle,rgba(129,178,255,.38) 0%,rgba(129,178,255,.10) 48%,rgba(129,178,255,0) 72%)}.cpo-page::after{width:360px;height:360px;left:18vw;bottom:3vh;background:radial-gradient(circle,rgba(190,153,255,.30) 0%,rgba(190,153,255,.08) 48%,rgba(190,153,255,0) 72%)}.cpo-head{align-items:flex-end}.date-box{display:flex;flex-direction:column;gap:5px}.date-box label{font-size:12px;color:#6b7280}.daily-summary,.source-card,.publish-bar{background:linear-gradient(135deg,rgba(255,255,255,.76),rgba(255,255,255,.50));border:1px solid rgba(255,255,255,.72);backdrop-filter:blur(24px) saturate(155%);-webkit-backdrop-filter:blur(24px) saturate(155%);box-shadow:inset 0 1px 0 rgba(255,255,255,.88),0 12px 34px rgba(31,41,55,.08),0 2px 8px rgba(31,41,55,.04)}.daily-summary{display:flex;justify-content:space-between;align-items:center;padding:16px 18px;margin:14px 0 16px;border-radius:16px}.summary-copy{display:flex;align-items:baseline;gap:10px}.eyebrow{font-size:12px;color:#6b7280;margin-right:4px}.summary-copy strong{font-size:25px;color:#111827}.summary-copy>span:last-child{font-size:13px;color:#687181}.summary-status{font-size:13px;font-weight:600;padding:6px 10px;border-radius:999px;border:1px solid rgba(255,255,255,.68);box-shadow:inset 0 1px 0 rgba(255,255,255,.65)}.summary-status.ready{background:rgba(234,248,240,.72);color:#287a4b}.summary-status.blocked{background:rgba(255,242,232,.72);color:#a65b19}.account-stack{display:flex;flex-direction:column;gap:14px}.account-row{display:grid;grid-template-columns:110px minmax(0,1fr);gap:14px}.account-label{display:flex;align-items:center}.account-label h2{font-size:18px;margin:0 0 7px}.account-state{display:inline-block;font-size:12px;padding:3px 8px;border-radius:999px;border:1px solid rgba(255,255,255,.55);box-shadow:inset 0 1px 0 rgba(255,255,255,.55)}.account-state.ready{background:rgba(234,248,240,.66);color:#287a4b}.account-state.blocked{background:rgba(255,242,232,.66);color:#a65b19}.source-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.source-card{padding:15px 16px;border-left:3px solid rgba(223,228,236,.92);border-radius:16px;transition:transform .18s ease,box-shadow .18s ease,background .18s ease}.source-card:hover{transform:translateY(-1px);background:linear-gradient(135deg,rgba(255,255,255,.82),rgba(255,255,255,.57));box-shadow:inset 0 1px 0 rgba(255,255,255,.92),0 16px 38px rgba(31,41,55,.10),0 3px 10px rgba(31,41,55,.05)}.source-card.ready{border-left-color:rgba(62,156,104,.82)}.source-card.empty{border-left-color:rgba(200,206,216,.90)}.source-card.na{border-left-color:rgba(154,163,178,.86);background:linear-gradient(135deg,rgba(250,251,252,.72),rgba(245,247,250,.48))}.source-card-head{display:flex;align-items:flex-start;justify-content:space-between;gap:10px}.source-kicker{display:block;font-size:11px;color:#8a93a1;margin-bottom:2px}.source-card h3{font-size:15px;margin:0;color:#202631}.source-status{font-size:12px;font-weight:600;white-space:nowrap;color:#626b78;padding:3px 7px;border-radius:999px;background:rgba(255,255,255,.38)}.ready .source-status{color:#287a4b}.source-main{display:flex;align-items:baseline;gap:9px;margin:18px 0 5px}.source-main strong{font-size:20px;color:#151b26}.source-main span{font-size:12px;color:#7b8492}.source-card p{font-size:12px;color:#6e7785;margin:0 0 12px}.cpo-upload{width:100%}.cpo-upload :deep(.n-upload-dragger){padding:9px 11px;border-radius:11px;background:rgba(255,255,255,.42);min-height:56px}.cpo-upload :deep(.n-upload-dragger:hover){background:rgba(255,255,255,.68)}.upload-content{display:flex;align-items:center;justify-content:flex-start;gap:10px;text-align:left;color:#5587c5}.upload-copy{display:flex;flex-direction:column;gap:2px;min-width:0}.upload-copy strong{font-size:12px;color:#425166}.upload-copy small{font-size:11px;color:#8a93a1;font-weight:400}.upload-message{margin-top:8px;font-size:11px;color:#7b8492}.upload-message.ok{color:#287a4b}.upload-message.warn{color:#a65b19}.historical-confirm{display:flex;gap:6px;margin-top:8px}.publish-bar{margin-top:16px;padding:15px 18px;display:flex;align-items:center;justify-content:space-between;gap:20px;border-radius:16px}.publish-bar strong{font-size:14px}.publish-bar p{margin:4px 0 0;color:#727b88;font-size:12px}.publish-bar .btn:disabled{opacity:.45;cursor:not-allowed}.dev-note{font-size:12px;color:#8a93a1;margin:10px 2px 0}@media(max-width:900px){.account-row{grid-template-columns:1fr}.source-grid{grid-template-columns:1fr}.daily-summary,.publish-bar,.cpo-head{align-items:flex-start;flex-direction:column;gap:10px}.cpo-page::before{right:-120px}.cpo-page::after{left:-120px}}
</style>
