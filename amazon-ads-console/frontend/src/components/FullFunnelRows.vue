<script setup lang="ts">
defineProps<{ ledger?: { rows?:any[]; spend?:number; unallocatedSpend?:number; note?:string } }>()
const money=(v:any)=>`$${Number(v || 0).toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2})}`
</script>
<template>
  <div v-if="ledger?.rows?.length" class="full-funnel-rows">
    <strong>全流域广告活动</strong>
    <p>{{ ledger.note }}</p>
    <table aria-label="全流域广告活动明细">
      <thead><tr><th>日期</th><th>运营／产品</th><th>活动</th><th>费用</th><th>状态</th></tr></thead>
      <tbody><tr v-for="r in ledger.rows" :key="`${r.date}-${r.account}-${r.campaignId}-${r.group}-${r.productCode}`">
        <td>{{ r.date }}</td><td>{{ r.operatorName ? `${r.operatorName}／${r.productCode}` : '跨产品活动' }}</td>
        <td class="campaign">{{ r.campaignName }}</td><td>{{ money(r.spend) }}</td><td>{{ r.status }}</td>
      </tr></tbody>
    </table>
    <p>全流域费用 {{ money(ledger.spend) }}<span v-if="ledger.unallocatedSpend">；待分摊 {{ money(ledger.unallocatedSpend) }}</span></p>
  </div>
</template>
<style scoped>
.full-funnel-rows{text-align:left;padding:12px;background:#f6f8fc;white-space:normal;color:#344054}.full-funnel-rows>strong{font-size:14px}.full-funnel-rows p{font-size:12px;margin:7px 0;line-height:1.6}.full-funnel-rows table{width:100%;table-layout:auto;border-collapse:collapse;min-width:700px}.full-funnel-rows th,.full-funnel-rows td{padding:7px 10px;font-size:12px;text-align:left;background:white;border-bottom:1px solid #e7ebf1;height:auto}.full-funnel-rows .campaign{white-space:normal;overflow-wrap:anywhere;min-width:220px}
</style>
