<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { getFrontendErrors, type FrontendErrorRecord } from '../api/diagnostics'
const filters = ref({username:'',user_id:'',page_path:'',client_commit:'',kind:'',since:'',until:'',limit:'100'})
const rows = ref<FrontendErrorRecord[]>([])
const loading = ref(false), error = ref(''), notice = ref('')
const labels: Record<string,string> = {vue_error:'页面渲染报错',javascript_error:'脚本报错',unhandled_rejection:'异步报错',resource_error:'资源加载失败',router_error:'导航报错',navigation_timeout:'导航卡住'}
const time = (value: string) => new Date(value).toLocaleString()
async function load() {
  loading.value=true;error.value='';notice.value=''
  try {
    const params={...filters.value}
    for (const key of ['since','until'] as const) if (params[key]) params[key]=new Date(params[key]).toISOString()
    if (params.since && params.until && params.since>params.until) throw new Error('开始时间应早于结束时间')
    const data=await getFrontendErrors(params)
    rows.value=data.items
    notice.value=!data.available?'前端异常日志存储当前不可用。':data.message || ''
  } catch(err) {rows.value=[];error.value=err instanceof Error?err.message:'前端异常读取失败'}
  finally {loading.value=false}
}
onMounted(load)
</script>
<template>
  <section class="card panel frontend-errors">
    <div class="panel-head"><div><h2>前端异常与导航卡住</h2><p>记录已登录账号的页面渲染、脚本、异步、资源和导航异常。浏览器版本是发生错误时运行的版本；服务端版本是接收日志的版本。</p></div><button class="btn compact" :disabled="loading" @click="load">{{ loading?'读取中…':'刷新前端日志' }}</button></div>
    <form class="error-filters" @submit.prevent="load">
      <label>账号<input v-model="filters.username" placeholder="如 op_lzz" /></label>
      <label>用户 ID<input v-model="filters.user_id" placeholder="全部用户" /></label>
      <label>页面<input v-model="filters.page_path" placeholder="如 /ad-allocation" /></label>
      <label>浏览器版本<input v-model="filters.client_commit" placeholder="完整提交或前缀" /></label>
      <label>异常类型<select v-model="filters.kind"><option value="">全部</option><option v-for="(label,key) in labels" :key="key" :value="key">{{ label }}</option></select></label>
      <label>开始时间<input v-model="filters.since" type="datetime-local" /></label><label>结束时间<input v-model="filters.until" type="datetime-local" /></label>
      <button class="btn primary" type="submit" :disabled="loading">查询前端异常</button>
    </form>
    <p v-if="error" class="error" role="alert">{{ error }}</p><p v-if="notice" role="status">{{ notice }}</p>
    <div class="table-wrap"><table><thead><tr><th>时间 / 追踪 ID</th><th>账号</th><th>异常</th><th>页面 / 目标页面</th><th>浏览器版本 / 服务端版本</th><th>定位</th></tr></thead>
    <tbody><tr v-for="row in rows" :key="row.event_id">
      <td>{{ time(row.timestamp) }}<small>{{ row.request_id }}</small></td><td>{{ row.username }}<small>ID {{ row.user_id }}</small></td>
      <td>{{ labels[row.kind] || row.kind }}<strong v-if="row.is_test"> · 验收测试</strong><small>{{ row.message }} · {{ row.exception_type }}</small><small v-if="row.duration_ms">持续 {{ (row.duration_ms/1000).toFixed(1) }} 秒</small></td>
      <td>{{ row.page_path }}<small v-if="row.target_path">前往 {{ row.target_path }}</small></td>
      <td><code>{{ row.client_commit }}</code><small>{{ row.commit }}</small></td>
      <td><details v-if="row.stack?.length"><summary>调用位置</summary><div v-for="(frame,index) in row.stack" :key="index"><code>{{ frame.file }}:{{ frame.line }}:{{ frame.column }}</code></div></details><span v-else>—</span></td>
    </tr><tr v-if="!rows.length"><td colspan="6">{{ loading?'正在读取前端异常…':error?'本次查询未成功。':'当前筛选范围内没有前端异常记录。' }}</td></tr></tbody></table></div>
    <p class="muted small">账号由服务端登录态确认；只记录错误类别与代码位置，不采集密码、令牌、报表正文或网址参数。重复错误短时去重并限流；未登录或网络断开时无法完成服务端上报。日志沿用服务端保留与轮转设置。</p>
  </section>
</template>
<style scoped>
.panel-head{display:flex;justify-content:space-between;align-items:flex-start;gap:12px}.panel-head p{font-size:12px;color:#7b8495;max-width:1000px}.error-filters{display:flex;gap:9px;align-items:flex-end;flex-wrap:wrap;margin:14px 0}.error-filters label{display:flex;flex-direction:column;font-size:11px;color:#7b8495;gap:5px}.error-filters input,.error-filters select{height:34px;border:1px solid var(--line);border-radius:7px;padding:0 9px;max-width:220px;background:white}table{min-width:1200px}td{vertical-align:top;max-width:300px;overflow-wrap:anywhere}small{display:block;font-size:11px;color:#7b8495;margin-top:5px}code{font-size:11px;overflow-wrap:anywhere}summary{cursor:pointer;color:#3268d8}.error{color:#a45f16}
</style>
