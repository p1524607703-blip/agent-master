<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'

type PieItem = { name: string; value: number }

const props = defineProps<{
  data: PieItem[]
}>()

const el = ref<HTMLDivElement>()
let chart: echarts.ECharts | undefined

const render = () => {
  if (!el.value) return
  chart ||= echarts.init(el.value)
  const total = props.data.reduce((sum, item) => sum + item.value, 0)

  chart.setOption({
    tooltip: {
      trigger: 'item',
      formatter: (params: any) => {
        const value = Number(params.value || 0)
        return `${params.name}<br/>花费 $${value.toLocaleString()}<br/>占比 ${params.percent}%`
      },
    },
    legend: {
      bottom: 0,
      left: 'center',
      itemWidth: 10,
      itemHeight: 10,
      textStyle: { color: '#667085', fontSize: 11 },
    },
    graphic: [
      {
        type: 'text',
        left: 'center',
        top: '42%',
        style: {
          text: `总花费\n$${total.toLocaleString()}`,
          textAlign: 'center',
          fill: '#1f2937',
          fontSize: 13,
          fontWeight: 600,
          lineHeight: 21,
        },
      },
    ],
    series: [
      {
        type: 'pie',
        radius: ['48%', '72%'],
        center: ['50%', '43%'],
        avoidLabelOverlap: true,
        itemStyle: { borderColor: '#fff', borderWidth: 3, borderRadius: 5 },
        label: {
          show: true,
          formatter: '{b}\n{d}%',
          color: '#475467',
          fontSize: 11,
          lineHeight: 16,
        },
        labelLine: { length: 10, length2: 8 },
        data: props.data,
      },
    ],
  }, true)
}

const resize = () => chart?.resize()
onMounted(() => {
  render()
  window.addEventListener('resize', resize)
})
watch(() => props.data, render, { deep: true })
onBeforeUnmount(() => {
  window.removeEventListener('resize', resize)
  chart?.dispose()
})
</script>

<template>
  <div ref="el" class="ad-pie-chart"></div>
</template>
