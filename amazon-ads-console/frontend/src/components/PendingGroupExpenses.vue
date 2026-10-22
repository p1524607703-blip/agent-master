<script setup lang="ts">
import { computed } from 'vue'

type PendingExpense = {
  date: string; account: string; campaignId: string; campaignName: string
  group: string; operatorName: string; spend: number; reason: string; status: string
}
const props = defineProps<{
  entries?: PendingExpense[]
  total?: number | null
  operatorName?: string
  allGroups?: boolean
}>()
// The API enforces group scope. Filter again here so a scoped page can never
// render campaign details from another group, even with mixed input entries.
const rows = computed(() => (props.entries || []).filter(row =>
  row.status === 'GROUP_KNOWN_PRODUCT_PENDING' &&
  (props.allGroups === true || (props.operatorName && row.operatorName === props.operatorName)),
))
const visible = computed(() => rows.value.length > 0 && Number(props.total) > 0)
const money = (value: number) => `$${Number(value).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
const reasons: Record<string,string> = {
  MULTIPLE_NAMED_PRODUCTS: '命中多个款式，待确认分配规则',
  CONFIRMED_ALIAS_REQUIRED: '组合名称待确认款式映射',
}
const reason = (value: string) => reasons[value] || '款式归属待确认'
</script>

<template>
  <section v-if="visible" class="pending-group-expenses" aria-label="组内待分摊费用">
    <h3>组内待分摊费用：{{ money(Number(total)) }}</h3>
    <p>{{ allGroups ? '已计入各运营组总费用' : '已计入本组总费用' }}，尚未拆到具体款式；最终 CPO 待确认。以下金额为总费用中的子项，请勿重复加总。</p>
    <details>
      <summary>查看 {{ rows.length }} 条费用明细</summary>
      <div class="table-wrap">
        <table>
          <thead><tr><th>日期</th><th>运营组</th><th>广告活动</th><th>费用</th><th>待确认原因</th></tr></thead>
          <tbody>
            <tr v-for="(row,index) in rows" :key="`${row.date}-${row.account}-${row.campaignId}-${index}`">
              <td>{{ row.date }}</td><td>{{ row.group }} · {{ row.operatorName }}</td>
              <td>{{ row.campaignName }}</td><td>{{ money(row.spend) }}</td><td>{{ reason(row.reason) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </details>
  </section>
</template>

<style scoped>
.pending-group-expenses{margin:12px 0;padding:12px 14px;border:1px solid #f0d2a1;border-radius:8px;background:#fff8ed;color:#825514;font-size:12px;line-height:1.7}
h3{font-size:13px;margin:0 0 4px}p{margin:0 0 8px}summary{cursor:pointer;font-weight:600}
table{min-width:650px;margin-top:8px}th{background:#fff9f0}td,th{font-size:11px}td:nth-child(3){white-space:normal;overflow-wrap:anywhere}
</style>
