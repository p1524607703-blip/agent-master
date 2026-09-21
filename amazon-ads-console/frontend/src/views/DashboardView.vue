<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import FilterBar from '../components/FilterBar.vue'
import KpiCard from '../components/KpiCard.vue'
import AdTypeCard from '../components/AdTypeCard.vue'
import AdSpendPieChart from '../components/AdSpendPieChart.vue'
import CpoTrendChart from '../components/CpoTrendChart.vue'
import { getJson } from '../api/client'
import DataSkeleton from '../components/DataSkeleton.vue'
import { dashboardOverview, dashboardTrend } from '../api/mock'

const data = ref<any>(dashboardOverview)
const trend = ref<any[]>(dashboardTrend)
const query = ref({ accountId: 'amzn1.ads-account.g.42jh8psyvhiiiitpm4rnj4qhh', date: '2026-08-26' })
const selected = ref<'SP' | 'SB' | 'SD' | 'STV'>('SP')
const loading = ref(true)

const load = async () => {
  loading.value = true
  try {
    const q = `?account_id=${encodeURIComponent(query.value.accountId)}&date=${query.value.date}`
    data.value = await getJson(`/dashboard/overview${q}`, dashboardOverview as any)
    trend.value = await getJson(`/dashboard/trend?account_id=${encodeURIComponent(query.value.accountId)}&end_date=${query.value.date}&days=14`, dashboardTrend as any)
  } finally {
    loading.value = false
  }
}
const runQuery = async (payload: { accountId: string; date: string }) => { query.value = payload; await load() }
onMounted(load)
const money = (v: any) => v == null ? '—' : `$${Number(v).toLocaleString(undefined, { maximumFractionDigits: 2 })}`
const num = (v: any) => v == null ? '—' : Number(v).toLocaleString()
const ratio = (v: any, suffix = '') => v == null ? '—' : `${Number(v).toFixed(2)}${suffix}`

const primaryPieData = computed(() =>
  data.value.ad_types.map((item: any) => ({ name: item.l1, value: item.spend })),
)

const current = computed<any>(() => data.value.ad_types.find((x: any) => x.l1 === selected.value) || { l1: selected.value, spend: 0, orders: 0, cpo: null, children: [] })

const secondaryPieData = computed(() =>
  current.value.children.map((item: any) => ({ name: item.name, value: item.spend })),
)

const selectSecondary = (adType: string) => {
  if (adType === 'SP' || adType === 'SB' || adType === 'SD' || adType === 'STV') {
    selected.value = adType
  }
}
</script>

<template>
  <section class="page">
    <div class="page-head">
      <div>
        <h1>广告投放概览</h1>
        <p>管理层先发现异常，再按产品、广告类型逐层下钻。</p>
      </div>
      <button class="btn">导出 CSV</button>
    </div>

    <FilterBar @query="runQuery" />

    <DataSkeleton v-if="loading" variant="dashboard" />

    <div v-if="!loading" class="data-audit-bar">RDS · {{ data.store || data.account_name }} · 数据日 {{ data.data_date || query.date }} · CPO事实 {{ data.ad_fact_rows ?? '—' }} 行 · 业务报告 {{ data.business_report_rows ?? '—' }} 行</div>

    <div v-if="!loading" class="kpi-grid">
      <KpiCard label="广告花费" :value="money(data.ad_spend)" desc="CPO推广商品总成本" />
      <KpiCard label="全部订单" :value="num(data.total_orders)" desc="业务报告已订购商品数量" />
      <KpiCard label="广告单" :value="num(data.ad_orders)" desc="已售商品数量" />
      <KpiCard label="综合 CPO" :value="money(data.cpo)" desc="广告花费 / 全部订单" />
      <KpiCard label="ROAS" :value="ratio(data.roas)" desc="广告归因销售额 / 广告花费" />
      <KpiCard label="TACOS" :value="ratio(data.tacos_pct, '%')" desc="广告花费 / 总销售额" />
    </div>

    <div v-if="!loading" class="two-col ad-overview-grid revised-layout">
      <div class="card panel primary-type-panel">
        <div class="panel-head">
          <div>
            <h2>一级广告类型花费结构</h2>
            <p>SP / SB / SD / STV 总花费占比</p>
          </div>
        </div>
        <AdSpendPieChart :data="primaryPieData" />

        <div class="primary-card-section">
          <div class="section-title-row">
            <div>
              <h2>一级广告类型表现</h2>
              <p>点击任一一级类型，在右侧查看对应二级结构与明细</p>
            </div>
          </div>
          <div class="ad-grid">
            <AdTypeCard
              v-for="a in data.ad_types"
              :key="a.l1"
              :name="a.l1"
              :spend="a.spend"
              :orders="a.orders"
              :active="selected === a.l1"
              @select="selectSecondary(a.l1)"
            />
          </div>
        </div>
      </div>

      <div class="card panel secondary-type-panel">
        <div class="panel-head secondary-head">
          <div>
            <h2>{{ selected }} 二级广告类型花费结构</h2>
            <p>SP / SB / SD / STV 均可查看二级分类</p>
          </div>
          <div class="secondary-switch">
            <button class="tab" :class="{ active: selected === 'SP' }" @click="selected = 'SP'">SP</button>
            <button class="tab" :class="{ active: selected === 'SB' }" @click="selected = 'SB'">SB</button>
            <button class="tab" :class="{ active: selected === 'SD' }" @click="selected = 'SD'">SD</button>
            <button class="tab" :class="{ active: selected === 'STV' }" @click="selected = 'STV'">STV</button>
          </div>
        </div>
        <AdSpendPieChart :data="secondaryPieData" />

        <div class="secondary-detail-table">
          <div class="secondary-detail-head">
            <span>二级类型</span>
            <span>费用</span>
            <span>广告单</span>
            <span>单均广告费</span>
            <span>费用占比</span>
          </div>
          <div v-for="item in current.children" :key="item.name" class="secondary-detail-row">
            <strong>{{ item.name }}</strong>
            <span>${{ item.spend.toLocaleString() }}</span>
            <span>{{ item.orders }}</span>
            <span>{{ item.cpo == null ? '—' : `$${item.cpo.toFixed(2)}` }}</span>
            <span>{{ ((item.spend / current.spend) * 100).toFixed(1) }}%</span>
          </div>
          <div class="secondary-detail-total">
            <strong>{{ selected }} 合计</strong>
            <span>${{ current.spend.toLocaleString() }}</span>
            <span>{{ current.orders }}</span>
            <span>{{ current.cpo == null ? '—' : `$${current.cpo.toFixed(2)}` }}</span>
            <span>100%</span>
          </div>
        </div>
      </div>
    </div>

    <div v-if="!loading" class="card panel">
      <div class="panel-head">
        <div>
          <h2>综合 CPO / 广告单 / 自然单趋势</h2>
          <p>自然单按 V3.5 暂不倒算，缺少可靠口径的日期显示为“—”</p>
        </div>
      </div>
      <CpoTrendChart :data="trend" />
    </div>

  </section>
</template>
