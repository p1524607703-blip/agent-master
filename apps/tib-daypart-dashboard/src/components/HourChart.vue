<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import type { EChartsOption, MarkAreaComponentOption } from "echarts";
import { BarChart, LineChart } from "echarts/charts";
import {
  GridComponent,
  LegendComponent,
  MarkAreaComponent,
  MarkLineComponent,
  TooltipComponent,
} from "echarts/components";
import { init, use, type EChartsType } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import type { HourSummary, TimeWindow } from "@/types";

use([
  BarChart,
  LineChart,
  GridComponent,
  LegendComponent,
  MarkAreaComponent,
  MarkLineComponent,
  TooltipComponent,
  CanvasRenderer,
]);

type ChartKind = "traffic" | "value" | "roas";
type BandMode = "none" | "industry" | "actual";

const props = defineProps<{
  kind: ChartKind;
  rows: HourSummary[];
  title: string;
  subtitle: string;
  bandMode: BandMode;
  windows: TimeWindow[];
  currency: string;
}>();

const root = ref<HTMLDivElement>();
let chart: EChartsType | undefined;
let observer: ResizeObserver | undefined;

const palette = {
  blue: "#2f67d8",
  blueOpen: "rgba(47, 103, 216, 0.14)",
  gold: "#d49a2a",
  orange: "#dc6a3a",
  olive: "#79864a",
  ink: "#243247",
  muted: "#718096",
  grid: "#e8edf3",
};

const actualBands = computed<MarkAreaComponentOption["data"]>(() =>
  props.windows
    .filter((window) => window.classification !== "insufficient")
    .map((window) => {
      const style =
        window.classification === "efficient"
          ? { color: "rgba(47, 103, 216, 0.08)" }
          : window.classification === "inefficient"
            ? { color: "rgba(220, 106, 58, 0.08)" }
            : { color: "rgba(121, 134, 74, 0.07)" };
      return [
        {
          name:
            window.signal === "isolated"
              ? "孤立信号"
              : window.signal === "sufficient"
                ? "样本充分"
                : "",
          xAxis: window.start,
          itemStyle:
            window.signal === "isolated"
              ? { ...style, opacity: 0.45 }
              : style,
          label: { color: palette.muted, fontSize: 10 },
        },
        { xAxis: window.end },
      ];
    }),
);

const industryBands: MarkAreaComponentOption["data"] = [
  [
    {
      name: "行业低谷",
      xAxis: 0,
      itemStyle: { color: "rgba(113, 128, 150, 0.07)" },
      label: { color: palette.muted, fontSize: 10 },
    },
    { xAxis: 5 },
  ],
  ...[
    [9, 10],
    [14, 15],
    [18, 20],
  ].map(([start, end]) => [
    {
      name: "行业高峰",
      xAxis: start,
      itemStyle: { color: "rgba(212, 154, 42, 0.08)" },
      label: { color: palette.muted, fontSize: 10 },
    },
    { xAxis: end },
  ]),
] as MarkAreaComponentOption["data"];

function bandSeries(): MarkAreaComponentOption | undefined {
  const data =
    props.bandMode === "industry"
      ? industryBands
      : props.bandMode === "actual"
        ? actualBands.value
        : [];
  if (!data?.length) return undefined;
  return {
    silent: true,
    data,
  };
}

function baseOption(): EChartsOption {
  return {
    animationDuration: 350,
    color: [palette.blue, palette.gold, palette.orange],
    textStyle: {
      fontFamily:
        'Inter, ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
      color: palette.ink,
    },
    grid: { left: 54, right: 30, top: 42, bottom: 40, containLabel: false },
    tooltip: {
      trigger: "axis",
      backgroundColor: "rgba(20, 29, 43, 0.94)",
      borderWidth: 0,
      textStyle: { color: "#fff", fontSize: 12 },
      axisPointer: { type: "line", lineStyle: { color: "#98a6b8" } },
      valueFormatter: (value) =>
        typeof value === "number" ? value.toLocaleString("zh-CN") : String(value),
    },
    legend: {
      top: 4,
      right: 8,
      itemWidth: 12,
      itemHeight: 7,
      textStyle: { color: palette.muted, fontSize: 11 },
    },
    xAxis: {
      type: "category",
      boundaryGap: props.kind !== "roas",
      data: props.rows.map((row) => row.hour),
      axisLabel: {
        color: palette.muted,
        interval: 1,
        formatter: (value: string) => `${String(value).padStart(2, "0")}时`,
      },
      axisLine: { lineStyle: { color: "#cbd5e1" } },
      axisTick: { show: false },
    },
  };
}

function option(): EChartsOption {
  const base = baseOption();
  const markArea = bandSeries();
  if (props.kind === "traffic") {
    return {
      ...base,
      yAxis: [
        {
          type: "value",
          name: "展示量",
          min: 0,
          nameTextStyle: { color: palette.muted },
          axisLabel: { color: palette.muted },
          splitLine: { lineStyle: { color: palette.grid } },
        },
        {
          type: "value",
          name: "点击 / 购买",
          min: 0,
          nameTextStyle: { color: palette.muted },
          axisLabel: { color: palette.muted },
          splitLine: { show: false },
        },
      ],
      series: [
        {
          name: "展示量",
          type: "bar",
          data: props.rows.map((row) => row.impressions),
          itemStyle: {
            color: palette.blueOpen,
            borderColor: palette.blue,
            borderWidth: 1,
          },
          barMaxWidth: 22,
          markArea,
        },
        {
          name: "点击量",
          type: "line",
          yAxisIndex: 1,
          data: props.rows.map((row) => row.clicks),
          symbol: "circle",
          symbolSize: 5,
          lineStyle: { width: 2, color: palette.gold },
          itemStyle: { color: "#fff", borderColor: palette.gold, borderWidth: 2 },
        },
        {
          name: "购买量",
          type: "line",
          yAxisIndex: 1,
          data: props.rows.map((row) => row.purchases),
          symbol: "diamond",
          symbolSize: 6,
          lineStyle: { width: 2, type: "dashed", color: palette.orange },
          itemStyle: { color: "#fff", borderColor: palette.orange, borderWidth: 2 },
        },
      ],
    };
  }
  if (props.kind === "value") {
    return {
      ...base,
      yAxis: {
        type: "value",
        min: 0,
        name: props.currency,
        nameTextStyle: { color: palette.muted },
        axisLabel: { color: palette.muted },
        splitLine: { lineStyle: { color: palette.grid } },
      },
      series: [
        {
          name: "广告花费",
          type: "bar",
          data: props.rows.map((row) => Number(row.spend.toFixed(2))),
          itemStyle: { color: palette.blue, borderColor: "#204eaa", borderWidth: 1 },
          barMaxWidth: 18,
          markArea,
        },
        {
          name: "广告归因销售",
          type: "bar",
          data: props.rows.map((row) => Number(row.adSales.toFixed(2))),
          itemStyle: {
            color: "rgba(212, 154, 42, 0.58)",
            borderColor: palette.gold,
            borderWidth: 1,
          },
          barMaxWidth: 18,
        },
      ],
    };
  }
  const values = props.rows.map((row) => row.roas);
  const spend = props.rows.reduce((sum, row) => sum + row.spend, 0);
  const sales = props.rows.reduce((sum, row) => sum + row.adSales, 0);
  const baseline = spend > 0 ? sales / spend : null;
  return {
    ...base,
    yAxis: {
      type: "value",
      min: 0,
      name: "倍",
      nameTextStyle: { color: palette.muted },
      axisLabel: { color: palette.muted },
      splitLine: { lineStyle: { color: palette.grid } },
    },
    series: [
      {
        name: "ROAS",
        type: "line",
        data: values,
        connectNulls: false,
        symbol: "circle",
        symbolSize: 6,
        lineStyle: { width: 2.5, color: palette.blue },
        itemStyle: { color: "#fff", borderColor: palette.blue, borderWidth: 2 },
        markArea,
        markLine:
          baseline === null
            ? undefined
            : {
                silent: true,
                symbol: "none",
                lineStyle: { color: palette.ink, type: "dashed", width: 1.5 },
                label: {
                  formatter: `筛选基准 ${baseline.toFixed(2)}`,
                  color: palette.ink,
                  position: "insideEndTop",
                },
                data: [{ yAxis: baseline }],
              },
      },
    ],
  };
}

function render(): void {
  if (!root.value) return;
  if (!chart) chart = init(root.value, undefined, { renderer: "canvas" });
  chart.setOption(option(), true);
}

watch(
  () => [props.rows, props.kind, props.bandMode, props.windows, props.currency],
  () => nextTick(render),
  { deep: true },
);

onMounted(() => {
  render();
  if (root.value) {
    observer = new ResizeObserver(() => chart?.resize());
    observer.observe(root.value);
  }
});

onBeforeUnmount(() => {
  observer?.disconnect();
  chart?.dispose();
});
</script>

<template>
  <article class="chart-card">
    <header>
      <div>
        <h3>{{ title }}</h3>
        <p>{{ subtitle }}</p>
      </div>
    </header>
    <div ref="root" class="chart-canvas" role="img" :aria-label="title" />
  </article>
</template>
