<script setup lang="ts">
defineProps<{ ledger?: { modules?: any[]; rows?: any[]; spend?: number; note?: string } }>()
const money = (value: any) => `$${Number(value || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
</script>

<template>
  <details v-if="ledger?.modules?.length" class="card full-funnel-panel">
    <summary class="full-funnel-heading"><span>全流域广告活动</span><small>点击展开／收起</small></summary>
    <p class="full-funnel-note">{{ ledger.note }}</p>
    <div class="brand-modules">
      <section v-for="brand in ledger.modules" :key="brand.account" class="brand-module">
        <div class="brand-heading">
          <div class="brand-title"><h3>{{ brand.brandName }}</h3><span>{{ brand.visibilityLabel }}</span></div>
          <div class="brand-total">记录费用 <strong>{{ money(brand.spend) }}</strong><span v-if="brand.unallocatedSpend"> · 待分摊 {{ money(brand.unallocatedSpend) }}</span></div>
        </div>
        <p v-if="brand.brandName === '待核验账户'" class="account-note">{{ brand.account }} · 账户品牌权限待配置</p>
        <div v-if="brand.rows.length" class="funnel-table-wrap">
          <table :aria-label="`${brand.brandName}全流域广告活动明细`">
            <thead><tr><th>日期</th><th>运营／产品</th><th>活动</th><th>费用</th><th>状态</th></tr></thead>
            <tbody>
              <tr v-for="(row, index) in brand.rows" :key="`${row.date}-${row.campaignId}-${index}`">
                <td>{{ row.date }}</td>
                <td>{{ row.operatorName ? `${row.operatorName}／${row.productCode}` : '跨产品活动' }}</td>
                <td class="campaign">{{ row.campaignName }}</td>
                <td class="amount">{{ money(row.spend) }}</td>
                <td class="status">{{ row.status }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p v-else class="empty-brand">所选可计算日期没有全流域记录。</p>
      </section>
    </div>
  </details>
</template>

<style scoped>
.full-funnel-panel{margin:12px 0 16px;min-width:0;text-align:left;color:#344054}
.full-funnel-heading{padding:14px 18px;cursor:pointer;color:#243247;font-size:16px;font-weight:600}
.full-funnel-heading small{margin-left:12px;font-size:12px;font-weight:400;color:#667085}
.full-funnel-panel[open]>.full-funnel-heading{border-bottom:1px solid #e7ebf1}
.full-funnel-note{margin:0;padding:12px 18px 0;font-size:12px;line-height:1.7;color:#667085}
.brand-modules{display:flex;flex-direction:column;gap:14px;padding:16px}
.brand-module{min-width:0;border:1px solid #e3e9f2;border-radius:9px;overflow:hidden;background:#fff}
.brand-heading{display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap;padding:11px 13px;background:#f5f8fc}
.brand-title{display:flex;align-items:center;gap:9px}.brand-title h3{margin:0;font-size:14px;color:#243247}
.brand-title>span{font-size:11px;color:#61758d;background:#e9eff7;padding:2px 7px;border-radius:999px}
.brand-total{font-size:12px;color:#667085}.brand-total strong{color:#344054;font-size:14px}
.funnel-table-wrap{overflow-x:auto}.full-funnel-panel table{width:100%;min-width:720px;border-collapse:collapse;table-layout:auto}
.full-funnel-panel th,.full-funnel-panel td{padding:9px 12px;font-size:12px;text-align:left;vertical-align:top;border-bottom:1px solid #edf0f5;background:#fff;white-space:nowrap;height:auto}
.full-funnel-panel th{color:#667085;font-weight:500}.full-funnel-panel tr:last-child td{border-bottom:0}
.full-funnel-panel .campaign{white-space:normal;overflow-wrap:anywhere;min-width:230px}
.full-funnel-panel .status{white-space:normal;min-width:150px}.full-funnel-panel .amount{font-variant-numeric:tabular-nums}
.empty-brand,.account-note{margin:0;padding:13px;font-size:12px;color:#7b8492}
@media(max-width:800px){.brand-modules{padding:10px}.full-funnel-heading{padding:13px}.brand-total{width:100%}}
</style>
