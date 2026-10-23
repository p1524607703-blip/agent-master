<script setup lang="ts">
import { computed } from 'vue'
const props = defineProps<{ products: any[] }>()
const rows = computed(() => props.products.flatMap(p => p.campaignCostAllocations || []))
const total = computed(() => rows.value.reduce((sum, r) => sum + Number(r.spend || 0), 0))
const reviews = computed(() => props.products.flatMap(p => p.campaignCostReviews || []))
const reviewCount = computed(() => new Set(reviews.value.map(r => `${r.account}-${r.campaignId}`)).size)
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
  <details v-if="reviews.length" class="campaign-cost-notes review-notes">
    <summary>{{ reviewCount }} 个 SB 活动的费用承担款待核验，费用保留当前商品口径</summary>
    <p>商品运营归属已识别，但活动名称与费用行商品不同。请核验活动主推款与混投费用规则；成交商品可作佐证，不能直接按成交占比分费。以下为待核验候选，不表示费用一定归错。</p>
    <ul>
      <li v-for="(row, index) in reviews" :key="`${row.campaignId}-${row.date}-${index}`">
        {{ row.date }} · {{ row.campaignName }}：费用行商品 {{ row.sourceProduct }}，名称指向 {{ row.nameProduct }}，{{ money(Number(row.spend)) }}
      </li>
    </ul>
  </details>
</template>

<style scoped>
.campaign-cost-notes{margin:0 16px 12px;padding:10px 12px;background:#f0f7ff;border:1px solid #d6e8ff;border-radius:8px;font-size:12px;line-height:1.7;color:#315277;overflow-wrap:anywhere}
summary{cursor:pointer;font-weight:600}p{margin:8px 0}ul{margin:0;padding-left:20px}
.review-notes{background:#fff8ed;border-color:#f4d9a8;color:#825514}
</style>
