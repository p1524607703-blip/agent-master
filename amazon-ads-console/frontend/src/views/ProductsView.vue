<script setup lang="ts">
import { onMounted, ref } from 'vue'
import FilterBar from '../components/FilterBar.vue'
import { getJson } from '../api/client'
import DataSkeleton from '../components/DataSkeleton.vue'

const fallback = { data_source:'offline', data_date:'—', allocation_status:'—', final_cpo:false, rows:[], warning:'接口未连接' }
const data = ref<any>(fallback)
const query = ref({ accountId:'amzn1.ads-account.g.42jh8psyvhiiiitpm4rnj4qhh', date:'2026-08-26' })
const loading = ref(true)
const load = async () => {
  loading.value = true
  try {
    data.value = await getJson(`/products?account_id=${encodeURIComponent(query.value.accountId)}&date=${query.value.date}&limit=100`, fallback as any)
  } finally {
    loading.value = false
  }
}
const runQuery = async (p:{accountId:string;date:string}) => { query.value=p; await load() }
const money = (v:any) => v == null ? '—' : `$${Number(v).toLocaleString(undefined,{maximumFractionDigits:2})}`
const num = (v:any) => v == null ? '—' : Number(v).toLocaleString()
const ratio = (v:any,s='') => v == null ? '—' : `${Number(v).toFixed(2)}${s}`
onMounted(load)
</script>

<template>
  <section class="page">
    <div class="page-head"><div><h1>产品明细</h1><p>当前读取 RDS 的 Product × Date 预览结果。</p></div></div>
    <FilterBar @query="runQuery" />
    <DataSkeleton v-if="loading" variant="table" :rows="8" />
    <div v-if="!loading" class="attribution-notice"><strong>当前口径：</strong>{{ data.warning }} 数据日 {{ data.data_date }}；自然单不做“全部订单 − 广告单”倒算。</div>
    <div v-if="!loading" class="card panel">
      <div class="table-wrap">
        <table>
          <thead><tr><th>运营组</th><th>产品</th><th>父 ASIN</th><th>广告花费</th><th>广告单</th><th>全部订单</th><th>综合 CPO</th><th>ROAS</th><th>TACOS</th></tr></thead>
          <tbody>
            <tr v-for="r in data.rows" :key="`${r.group_code}-${r.parent_asin}`">
              <td>{{ r.group_code || '—' }}</td><td><strong>{{ r.code }}</strong></td><td>{{ r.parent_asin }}</td>
              <td>{{ money(r.spend) }}</td><td>{{ num(r.ad_orders) }}</td><td>{{ num(r.total_orders) }}</td>
              <td>{{ money(r.cpo) }}</td><td>{{ ratio(r.roas) }}</td><td>{{ ratio(r.tacos,'%') }}</td>
            </tr>
            <tr v-if="!data.rows?.length"><td colspan="9" class="muted">该日期没有可连接的业务报告产品数据。</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  </section>
</template>
