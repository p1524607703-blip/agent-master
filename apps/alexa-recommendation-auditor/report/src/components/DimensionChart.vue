<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import * as echarts from "echarts";
import type { ScoreDimensions } from "@alexa-auditor/contracts";

const props = defineProps<{ dimensions: ScoreDimensions }>();
const root = ref<HTMLDivElement>();
let chart: echarts.ECharts | null = null;

function render() {
  if (!root.value) return;
  chart ||= echarts.init(root.value);
  chart.setOption({
    grid: { top: 8, right: 48, bottom: 8, left: 78 },
    xAxis: { type: "value", min: 0, max: 100, splitLine: { lineStyle: { color: "#edf1f5" } }, axisLabel: { color: "#7d8796" } },
    yAxis: { type: "category", inverse: true, data: ["列表进入", "标准化排名", "竞品比较", "证据承接", "重复稳定"], axisTick: { show: false }, axisLine: { show: false }, axisLabel: { color: "#394457" } },
    series: [{ type: "bar", barWidth: 16, data: [props.dimensions.inclusion, props.dimensions.rank, props.dimensions.comparison, props.dimensions.evidence, props.dimensions.consistency], itemStyle: { color: "#1668dc", borderRadius: [0, 8, 8, 0] }, label: { show: true, position: "right", formatter: "{c}" } }],
    tooltip: { trigger: "axis", axisPointer: { type: "shadow" } }
  });
}

onMounted(() => { render(); window.addEventListener("resize", render); });
watch(() => props.dimensions, render, { deep: true });
onBeforeUnmount(() => { window.removeEventListener("resize", render); chart?.dispose(); });
</script>

<template><div ref="root" class="dimension-chart" /></template>
