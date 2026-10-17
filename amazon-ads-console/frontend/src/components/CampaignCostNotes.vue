<script setup lang="ts">
import { computed } from 'vue'
const props = defineProps<{ products: any[] }>()
const rows = computed(() => props.products.flatMap(p => p.campaignCostAllocations || []))
const total = computed(() => rows.value.reduce((sum, r) => sum + Number(r.spend || 0), 0))
const money = (value: number) => `$${value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
</script>

<template>
  <details v-if="rows.length" class="campaign-cost-notes">
    <summary>SB 混投费用已按确认主推款核算：{{ money(total) }}（已含总费用）</summary>
    <p>以下活动的费用及活动归因指标按确认主推款核算；实际成交商品与业务销量保持原有归属，不按成交占比分摊费用。</p>
    <ul>
      <li v-for="(row, index) in rows" :key="`${row.ruleId}-${row.date}-${index}`">
        {{ row.date }} · {{ row.campaignName }}：来源商品 {{ row.sourceProduct }} → 费用承担款 {{ row.targetProduct }}，{{ money(Number(row.spend)) }}
      </li>
    </ul>
  </details>
</template>

<style scoped>
.campaign-cost-notes{margin:0 16px 12px;padding:10px 12px;background:#f0f7ff;border:1px solid #d6e8ff;border-radius:8px;font-size:12px;line-height:1.7;color:#315277;overflow-wrap:anywhere}
summary{cursor:pointer;font-weight:600}p{margin:8px 0}ul{margin:0;padding-left:20px}
</style>
