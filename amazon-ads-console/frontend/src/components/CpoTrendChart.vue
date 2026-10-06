<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'

type TrendPoint = {
  date: string
  cpo: number | null
  adOrders: number | null
  organicOrders: number | null
}

const props = defineProps<{ data: TrendPoint[] }>()
const el = ref<HTMLDivElement>()
let chart: echarts.ECharts | undefined

const render = () => {
  if (!el.value) return
  chart ||= echarts.init(el.value)
  chart.setOption({
    grid: { left: 52, right: 58, top: 48, bottom: 34 },
    tooltip: {
      trigger: 'axis',
      formatter: (params: any[]) => {
        const date = params?.[0]?.axisValue ?? ''
        const lines = params.map(item => {
          const missing = item.value === null || item.value === undefined || item.value === '-'
          const value = missing ? '—' : item.seriesName === '综合 CPO'
            ? `$${Number(item.value).toFixed(2)}`
            : `${Number(item.value).toLocaleString()} 单`
          return `${item.marker}${item.seriesName}：${value}`
        })
        return [date, ...lines].join('<br/>')
      },
    },
    legend: { top: 4, right: 8, itemWidth: 18, itemHeight: 8, textStyle: { color: '#667085', fontSize: 11 }, data: ['综合 CPO', '广告单', '估算自然单'] },
    xAxis: { type: 'category', data: props.data.map(x => x.date), boundaryGap: false, axisLine: { lineStyle: { color: '#e5e7eb' } }, axisTick: { show: false }, axisLabel: { color: '#8a93a2' } },
    yAxis: [
      { type: 'value', name: 'CPO ($)', nameTextStyle: { color: '#8a93a2', fontSize: 10 }, axisLabel: { color: '#8a93a2', formatter: '${value}' }, splitLine: { lineStyle: { color: '#eef0f3' } } },
      { type: 'value', name: '订单量', nameTextStyle: { color: '#8a93a2', fontSize: 10 }, axisLabel: { color: '#8a93a2' }, splitLine: { show: false } },
    ],
    series: [
      { name: '综合 CPO', type: 'line', yAxisIndex: 0, smooth: true, connectNulls: false, data: props.data.map(x => x.cpo), symbol: 'circle', symbolSize: 6, lineStyle: { width: 3 }, areaStyle: { opacity: 0.04 } },
      { name: '广告单', type: 'line', yAxisIndex: 1, smooth: true, connectNulls: false, data: props.data.map(x => x.adOrders), symbol: 'circle', symbolSize: 5, lineStyle: { width: 2 } },
      { name: '估算自然单', type: 'line', yAxisIndex: 1, smooth: true, connectNulls: false, data: props.data.map(x => x.organicOrders), symbol: 'circle', symbolSize: 5, lineStyle: { width: 2 } },
    ],
  }, true)
}
const resize = () => chart?.resize()
onMounted(() => { render(); window.addEventListener('resize', resize) })
watch(() => props.data, render, { deep: true })
onBeforeUnmount(() => { window.removeEventListener('resize', resize); chart?.dispose() })
</script>
<template><div ref="el" class="trend-chart"></div></template>
