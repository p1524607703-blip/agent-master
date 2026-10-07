<script setup lang="ts">
import { computed, ref } from 'vue'
import { missingBusinessList, qualityLabel, qualityReasons, qualitySummary, type CpoQualityData } from '../diagnostics/cpoQuality'
import { browserTraceSnapshot, copyEvidence, downloadEvidence } from '../diagnostics/browserTrace'

const props = defineProps<{ data: CpoQualityData }>()
const traceFeedback = ref('')
async function copyTrace(): Promise<void> {
  try { await copyEvidence(browserTraceSnapshot()); traceFeedback.value = '本标签页加载记录已复制，可提供给排查人员。' }
  catch (error) { traceFeedback.value = error instanceof Error ? error.message : '复制失败，请下载记录。' }
}
const summary = computed(() => qualitySummary(props.data))
const missingProducts = computed(() => missingBusinessList(props.data))
const reasons = computed(() => qualityReasons(props.data))
const sources = computed(() => [
  { label: '业务报告', days: props.data.sourceCompleteness?.businessDays, missing: props.data.sourceCompleteness?.sourceMissingDates?.business, accounts: props.data.sourceCompleteness?.missingAccountsByDate?.business },
  { label: '推广的商品', days: props.data.sourceCompleteness?.advertisedProductDays, missing: props.data.sourceCompleteness?.sourceMissingDates?.advertisedProduct, accounts: props.data.sourceCompleteness?.missingAccountsByDate?.advertisedProduct },
  { label: '达成转化的商品', days: props.data.sourceCompleteness?.purchasedProductDays, missing: props.data.sourceCompleteness?.sourceMissingDates?.purchasedProduct, accounts: props.data.sourceCompleteness?.missingAccountsByDate?.purchasedProduct },
])
const sourceStatus = (days: number | undefined, missing?: string[]): string => {
  if (days == null || props.data.expectedDays == null) return '状态未提供'
  if (!props.data.expectedDays) return '无可计算区间'
  return days >= props.data.expectedDays && !missing?.length ? '日期覆盖完整' : '日期覆盖不完整'
}
const count = (value: number | null | undefined) => value == null ? '未提供' : value.toLocaleString()
const money = (value: number | null | undefined) => value == null ? '未提供' : `$${Number(value).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
</script>

<template>
  <section class="card quality-card" aria-label="数据质量">
    <div class="quality-head">
      <h2>数据质量</h2>
      <div class="quality-actions"><button class="link-btn" @click="copyTrace">复制加载记录</button><button class="link-btn" @click="downloadEvidence(browserTraceSnapshot(), 'cpo-browser-trace.json')">下载加载记录</button><span class="quality-state" :class="{ complete: data.final_cpo === true }">{{ qualityLabel(data) }}</span></div>
    </div>
    <p v-if="traceFeedback" class="quality-help" role="status">{{ traceFeedback }}</p>
    <div class="quality-metrics">
      <div><span>缺业务侧产品</span><strong>{{ count(summary.missingBusinessProducts) }}</strong></div>
      <div><span>未配对广告花费</span><strong>{{ money(summary.unpairedAdSpend) }}</strong></div>
      <div v-for="source in sources" :key="source.label"><span>{{ source.label }} · 日期覆盖</span><strong>{{ count(source.days) }}<small v-if="data.expectedDays != null"> / {{ data.expectedDays }} 天</small></strong><span class="source-state" :class="{ complete: sourceStatus(source.days, source.missing) === '日期覆盖完整' }">{{ sourceStatus(source.days, source.missing) }}</span><details v-if="source.missing?.length" class="source-missing"><summary>查看未覆盖日期（{{ source.missing.length }}）</summary><p v-for="date in source.missing" :key="date">{{ date }}<template v-if="source.accounts?.[date]?.length"> · 待补账户：{{ source.accounts[date].join('、') }}</template></p></details></div>
    </div>
    <p v-if="data.sourceCompleteness?.completeDays != null || data.coverageDays != null" class="quality-help">三源同时完整：{{ count(data.sourceCompleteness?.completeDays ?? data.coverageDays) }}<template v-if="data.expectedDays != null"> / {{ data.expectedDays }}</template> 天；仅这些日期进入 CPO 计算。</p>
    <ul class="quality-reasons"><li v-for="reason in reasons" :key="reason">{{ reason }}</li></ul>
    <p class="quality-help">三项来源按本次计算覆盖展示；产品缺业务侧记录不等同于整份业务报告未导入。加载记录仅保留在本标签页，不含令牌或请求正文。</p>
    <details v-if="missingProducts.length || (summary.missingBusinessProducts ?? 0) > 0" class="quality-missing">
      <summary>查看缺业务侧产品清单（{{ missingProducts.length }} 条已提供记录）</summary>
      <div v-if="missingProducts.length" class="table-wrap">
        <table><thead><tr><th>产品</th><th>父 ASIN</th><th>运营组</th><th>业务账户</th><th>广告花费</th><th>当前状态</th></tr></thead>
          <tbody><tr v-for="product in missingProducts" :key="`${product.code}-${product.parentAsin || ''}`">
            <td><strong>{{ product.code || '—' }}</strong></td><td>{{ product.parentAsin || '—' }}</td><td>{{ product.group || '—' }}</td>
            <td>{{ product.businessAccounts?.join('、') || '—' }}</td><td>{{ money(product.spend) }}</td><td>{{ product.dataStatus || '缺业务侧记录' }}</td>
          </tr></tbody>
        </table>
      </div>
      <p v-else class="quality-help">服务端返回了缺业务侧产品数量，但本次响应未提供相应产品清单。</p>
    </details>
  </section>
</template>

<style scoped>
.quality-card{padding:14px 16px;margin:12px 0}.quality-head{display:flex;align-items:center;justify-content:space-between;gap:12px}.quality-head h2{font-size:14px;margin:0}.quality-actions{display:flex;align-items:center;gap:6px;flex-wrap:wrap;justify-content:flex-end}.quality-actions button{font-size:10px}.quality-state{font-size:11px;padding:4px 9px;background:#fff3e6;color:#a45f16;border-radius:999px}.quality-state.complete{background:#edf8f1;color:#287a4b}.quality-metrics{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px;margin-top:12px}.quality-metrics>div{background:#f8fafc;border:1px solid #edf0f4;border-radius:7px;padding:10px}.quality-metrics span{display:block;font-size:11px;color:#7b8495}.quality-metrics strong{display:block;margin-top:5px;color:#344054;font-size:17px}.quality-metrics .source-state{font-size:10px;color:#a45f16;margin-top:6px}.quality-metrics .source-state.complete{color:#287a4b}.source-missing{font-size:10px;color:#667085;margin-top:7px}.source-missing summary{cursor:pointer}.source-missing p{line-height:1.7;overflow-wrap:anywhere;margin:6px 0 0}.quality-metrics small{font-weight:400;font-size:11px;color:#7b8495}.quality-reasons{padding-left:20px;margin:12px 0 7px;font-size:12px;color:#536276;line-height:1.7}.quality-help{font-size:11px;color:#8a93a2;line-height:1.7;margin:7px 0 0}.quality-missing{margin-top:12px;border-top:1px solid #edf0f4;padding-top:10px}.quality-missing summary{cursor:pointer;font-size:12px;color:#3268d8}.quality-missing table{margin-top:10px;min-width:720px}@media(max-width:1050px){.quality-metrics{grid-template-columns:repeat(3,minmax(0,1fr))}}@media(max-width:700px){.quality-metrics{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style>
