<script setup lang="ts">
import { computed, onMounted, reactive, ref, shallowRef, watch } from "vue";
import FileDrop from "@/components/FileDrop.vue";
import HourChart from "@/components/HourChart.vue";
import MetricCard from "@/components/MetricCard.vue";
import {
  applyFilters,
  buildCampaignRows,
  buildProductRows,
  hourlySummary,
  mergeTimeWindows,
  quadrantCounts,
  rowsForView,
  summarizeRows,
  weightedTib,
} from "@/lib/analytics";
import {
  addDays,
  commonDecisionWindow,
  maturityStatus,
  observationWindow,
} from "@/lib/dates";
import { exportCampaignExceptions, exportHourly } from "@/lib/export";
import {
  checkHermes,
  exportReviewPackage,
  importReviewFile,
  reviewWithHermes,
} from "@/lib/hermes";
import {
  acceptLockedConflict,
  importAndMergeProject,
  keepLockedConflict,
} from "@/lib/importer";
import {
  clearProject,
  loadProject,
  loadThresholds,
  saveProject,
  saveThresholds,
} from "@/lib/storage";
import type {
  AiReviewAudit,
  CampaignRow,
  DashboardProject,
  DataViewMode,
  FilterState,
  MaturityStatus,
  Thresholds,
} from "@/types";

type BandMode = "none" | "industry" | "actual";
type RangePreset = "14" | "30" | "60" | "90" | "custom";

const DEFAULT_THRESHOLDS: Thresholds = {
  minClicks: 30,
  minPurchases: 5,
  minActiveDays: 5,
  efficiencyDelta: 0.1,
  minMatureDays: 7,
  minClickDays: 5,
  minPurchaseDays: 3,
  maxOrderConcentration: 0.6,
};

const TIMEZONES = [
  { value: "America/Los_Angeles", label: "美国太平洋时间（PST/PDT）" },
  { value: "America/New_York", label: "美国东部时间（EST/EDT）" },
  { value: "America/Chicago", label: "美国中部时间（CST/CDT）" },
  { value: "America/Denver", label: "美国山地时间（MST/MDT）" },
];

// 12万+小时事实不需要被Vue逐行深度代理；深度响应式会显著放大导入后的渲染成本。
const project = shallowRef<DashboardProject>();
const loading = ref(true);
const importOpen = ref(false);
const settingsOpen = ref(false);
const auditOpen = ref(false);
const adFile = ref<File>();
const tibFile = ref<File>();
const importError = ref("");
const importPhase = ref("");
const importProgress = ref(0);
const accountTimezone = ref("America/Los_Angeles");
const bandMode = ref<BandMode>("actual");
const selectedProductLine = ref("");
const viewMode = ref<DataViewMode>("observation");
const rangePreset = ref<RangePreset>("14");
const thresholds = reactive<Thresholds>({ ...DEFAULT_THRESHOLDS });
const hermesState = ref({ ok: false, message: "尚未检查" });
const reviewingIds = ref<string[]>([]);
const aiImportError = ref("");

const filters = reactive<FilterState>({
  reportStart: "",
  reportEnd: "",
  operator: "",
  productLine: "",
  adType: "",
  campaignId: "",
});

function refreshMaturity(current: DashboardProject): {
  project: DashboardProject;
  changed: boolean;
} {
  const now = new Date();
  const importedAt = now.toISOString();
  let changed = false;
  const hourly = current.hourly.map((fact) => {
    const status = maturityStatus(
      fact.date,
      fact.productKind,
      current.config.accountTimezone,
      now,
    );
    const lockedAt =
      status === "mature" ? fact.lockedAt ?? importedAt : fact.lockedAt;
    if (status !== fact.maturityStatus || lockedAt !== fact.lockedAt) {
      changed = true;
    }
    return {
      ...fact,
      maturityStatus: status,
      lockedAt,
    };
  });
  return {
    project: {
      ...current,
      hourly,
    },
    changed,
  };
}

onMounted(async () => {
  const [savedProject, savedThresholds] = await Promise.all([
    loadProject(),
    loadThresholds(),
  ]);
  if (savedThresholds) Object.assign(thresholds, savedThresholds);
  if (savedProject) {
    const refreshed = refreshMaturity(savedProject);
    project.value = refreshed.project;
    accountTimezone.value = refreshed.project.config.accountTimezone;
    Object.assign(thresholds, refreshed.project.config.thresholds);
    applyDefaultWindow();
    if (refreshed.changed) {
      globalThis.setTimeout(() => {
        if (project.value) void saveProject(project.value);
      }, 0);
    }
  } else {
    importOpen.value = true;
  }
  hermesState.value = await checkHermes();
  loading.value = false;
});

watch(
  thresholds,
  async (value) => {
    await saveThresholds({ ...value });
    if (project.value) {
      project.value = {
        ...project.value,
        config: {
          ...project.value.config,
          thresholds: { ...value },
        },
      };
      await saveProject(project.value);
    }
  },
  { deep: true },
);

const scopeCampaigns = computed(() => {
  if (!project.value) return [];
  return project.value.campaigns.filter(
    (row) =>
      (!filters.operator || row.operator === filters.operator) &&
      (!filters.productLine || row.productLine === filters.productLine) &&
      (!filters.adType || row.adType === filters.adType) &&
      (!filters.campaignId || row.campaignId === filters.campaignId),
  );
});

const standardWindow = computed(() => {
  const timezone =
    project.value?.config.accountTimezone ?? accountTimezone.value;
  if (viewMode.value === "observation") return observationWindow(timezone);
  const kinds = [...new Set(scopeCampaigns.value.map((row) => row.productKind))];
  return commonDecisionWindow(
    kinds.length ? kinds : ["SP"],
    timezone,
  );
});

function applyDefaultWindow(): void {
  rangePreset.value = "14";
  const window = standardWindow.value;
  filters.reportStart = window.start;
  filters.reportEnd = window.end;
}

function applyRangePreset(value: RangePreset): void {
  rangePreset.value = value;
  if (value === "custom") return;
  if (value === "14") {
    applyDefaultWindow();
    return;
  }
  const days = Number(value);
  filters.reportEnd = standardWindow.value.end;
  filters.reportStart = addDays(filters.reportEnd, -(days - 1));
}

watch(
  () => [
    viewMode.value,
    filters.operator,
    filters.productLine,
    filters.adType,
    filters.campaignId,
  ],
  () => {
    if (rangePreset.value === "14") applyDefaultWindow();
  },
);

const filteredSourceRows = computed(() =>
  project.value ? applyFilters(project.value.hourly, filters) : [],
);
const filteredRows = computed(() =>
  rowsForView(filteredSourceRows.value, viewMode.value),
);
const filteredCampaigns = computed(() => {
  if (!project.value) return [];
  const ids = new Set(filteredRows.value.map((row) => row.campaignId));
  return project.value.campaigns.filter((campaign) => ids.has(campaign.campaignId));
});
const summary = computed(() => {
  const value = summarizeRows(filteredRows.value);
  value.weightedTib = weightedTib(filteredRows.value, filteredCampaigns.value);
  return value;
});
const hours = computed(() =>
  project.value
    ? hourlySummary(filteredRows.value, project.value.config.thresholds)
    : [],
);
const windows = computed(() => mergeTimeWindows(hours.value));
const isStandardDecisionWindow = computed(
  () =>
    viewMode.value === "decision" &&
    rangePreset.value === "14" &&
    filters.reportStart === standardWindow.value.start &&
    filters.reportEnd === standardWindow.value.end,
);
const productRows = computed(() =>
  project.value
    ? buildProductRows(
        project.value,
        filteredRows.value,
        viewMode.value,
        standardWindow.value.start,
        standardWindow.value.end,
        isStandardDecisionWindow.value,
      )
    : [],
);
const campaignScopeRows = computed(() => {
  if (!project.value) return [];
  const productLine = selectedProductLine.value || filters.productLine;
  if (!productLine) return [];
  const scopeFilters = {
    ...filters,
    productLine,
    campaignId: "",
  };
  return rowsForView(
    applyFilters(project.value.hourly, scopeFilters),
    viewMode.value,
  );
});
const campaignRows = computed(() =>
  project.value
    ? buildCampaignRows(
        project.value,
        campaignScopeRows.value,
        viewMode.value,
        standardWindow.value.start,
        standardWindow.value.end,
        isStandardDecisionWindow.value,
      )
    : [],
);
const quadrants = computed(() => quadrantCounts(campaignRows.value));

const operators = computed(() =>
  project.value
    ? [...new Set(project.value.campaigns.map((row) => row.operator))].sort()
    : [],
);
const productLines = computed(() =>
  project.value
    ? [
        ...new Set(
          project.value.campaigns
            .filter(
              (row) => !filters.operator || row.operator === filters.operator,
            )
            .map((row) => row.productLine),
        ),
      ].sort()
    : [],
);
const adTypes = computed(() =>
  project.value
    ? [...new Set(project.value.campaigns.map((row) => row.adType))].sort()
    : [],
);
const campaignOptions = computed(() =>
  project.value
    ? project.value.campaigns
        .filter(
          (row) =>
            (!filters.operator || row.operator === filters.operator) &&
            (!filters.productLine || row.productLine === filters.productLine) &&
            (!filters.adType || row.adType === filters.adType),
        )
        .sort((a, b) => a.campaignName.localeCompare(b.campaignName))
    : [],
);

const currency = computed(() => project.value?.quality.currencies[0] ?? "USD");
const recognitionRate = computed(() => {
  const quality = project.value?.quality;
  return quality?.campaignCount
    ? quality.recognizedCampaignCount / quality.campaignCount
    : 0;
});
const tibRate = computed(() => {
  const quality = project.value?.quality;
  return quality?.campaignCount
    ? quality.tibMatchedCampaignCount / quality.campaignCount
    : 0;
});
const dateCoverage = computed(() => {
  const expected = 14;
  return Math.min(
    1,
    new Set(filteredSourceRows.value.map((row) => row.date)).size / expected,
  );
});
const maturityDates = computed(() => {
  const byDate = new Map<string, Set<MaturityStatus>>();
  for (const row of filteredSourceRows.value) {
    const statuses = byDate.get(row.date) ?? new Set<MaturityStatus>();
    statuses.add(row.maturityStatus);
    byDate.set(row.date, statuses);
  }
  return [...byDate.entries()]
    .map(([date, statuses]) => {
      const status: MaturityStatus = statuses.has("processing")
        ? "processing"
        : statuses.has("backfilling")
          ? "backfilling"
          : "mature";
      return { date, status };
    })
    .sort((a, b) => b.date.localeCompare(a.date));
});
const maturityCounts = computed(() =>
  maturityDates.value.reduce(
    (counts, row) => {
      counts[row.status] += 1;
      return counts;
    },
    { processing: 0, backfilling: 0, mature: 0 } as Record<MaturityStatus, number>,
  ),
);
const lastBatch = computed(() => {
  const batches = project.value?.importBatches ?? [];
  return batches[batches.length - 1];
});
const historyPeriod = computed(() => {
  const dates = (project.value?.hourly ?? []).map((row) => row.date).sort();
  return {
    start: dates[0] ?? "—",
    end: dates[dates.length - 1] ?? "—",
  };
});
const unresolvedConflicts = computed(
  () =>
    project.value?.lockedConflicts.filter(
      (conflict) => conflict.status === "unresolved",
    ) ?? [],
);

function formatMoney(value: number, digits = 0): string {
  return new Intl.NumberFormat("zh-CN", {
    style: "currency",
    currency: currency.value === "USD" ? "USD" : "CNY",
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(value);
}

function formatCpc(value: number | null): string {
  return value === null ? "不可计算" : formatMoney(value, 2);
}

function formatNumber(value: number): string {
  return new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 0 }).format(value);
}

function formatRatio(value: number | null, kind: "multiple" | "percent"): string {
  if (value === null || !Number.isFinite(value)) return "不可计算";
  return kind === "multiple"
    ? `${value.toFixed(2)}×`
    : `${(value * 100).toFixed(1)}%`;
}

function maturityLabel(status: MaturityStatus): string {
  return {
    processing: "处理中",
    backfilling: "归因回填中",
    mature: "已锁定",
  }[status];
}

function quadrantLabel(value: CampaignRow["rawQuadrant"]): string {
  return {
    lowTibHighRoas: "低TIB × 高ROAS",
    lowTibLowRoas: "低TIB × 低ROAS",
    highTibHighRoas: "高TIB × 高ROAS",
    highTibLowRoas: "高TIB × 低ROAS",
    conditional: "中TIB条件带",
    blocked: "不可判定",
  }[value];
}

function latestReview(campaignId: string): AiReviewAudit | undefined {
  return [...(project.value?.aiReviews ?? [])]
    .reverse()
    .find((audit) => audit.campaignId === campaignId);
}

async function importData(): Promise<void> {
  importError.value = "";
  if (!adFile.value || !tibFile.value) {
    importError.value = "请同时选择广告小时报告和TIB活动报告。";
    return;
  }
  if (!accountTimezone.value) {
    importError.value = "首次导入必须选择广告账户时区。";
    return;
  }
  try {
    importProgress.value = 0;
    const next = await importAndMergeProject(
      adFile.value,
      tibFile.value,
      {
        accountTimezone: accountTimezone.value,
        thresholds: { ...thresholds },
        productRoasTargets: project.value?.config.productRoasTargets ?? {},
      },
      project.value,
      (phase, progress) => {
        importPhase.value = phase;
        importProgress.value = progress;
      },
    );
    importPhase.value = `正在保存 ${next.hourly.length.toLocaleString("zh-CN")} 条聚合事实`;
    importProgress.value = 0.95;
    await saveProject(next);
    importPhase.value = "生成看板";
    importProgress.value = 1;
    project.value = next;
    selectedProductLine.value = "";
    filters.operator = "";
    filters.productLine = "";
    filters.adType = "";
    filters.campaignId = "";
    applyDefaultWindow();
    importOpen.value = false;
  } catch (error) {
    importError.value =
      error instanceof Error ? error.message : "导入失败，请检查CSV字段。";
  }
}

async function clearData(): Promise<void> {
  if (!window.confirm("确定清除本机滚动历史库吗？原始CSV不会受影响。")) return;
  await clearProject();
  project.value = undefined;
  adFile.value = undefined;
  tibFile.value = undefined;
  importOpen.value = true;
}

function selectProductLine(productLine: string): void {
  selectedProductLine.value = productLine;
  filters.productLine = productLine;
  filters.campaignId = "";
  document
    .querySelector("#campaign-detail")
    ?.scrollIntoView({ behavior: "smooth", block: "start" });
}

function selectCampaign(campaignId: string): void {
  filters.campaignId = campaignId;
  document
    .querySelector("#hour-charts")
    ?.scrollIntoView({ behavior: "smooth", block: "start" });
}

async function setTarget(productLine: string, raw: string): Promise<void> {
  if (!project.value) return;
  const value = Number(raw);
  if (Number.isFinite(value) && value > 0) {
    project.value.config.productRoasTargets[productLine] = value;
  } else {
    delete project.value.config.productRoasTargets[productLine];
  }
  project.value = { ...project.value };
  await saveProject(project.value);
}

function reviewEvidence(row: CampaignRow) {
  const productRows = campaignScopeRows.value.filter(
    (fact) => fact.productLine === row.productLine,
  );
  return {
    campaign: row,
    productLine: {
      ...summarizeRows(productRows),
      productLine: row.productLine,
      campaignIds: [...new Set(productRows.map((fact) => fact.campaignId))],
    },
    viewMode: viewMode.value,
    window: {
      start: filters.reportStart,
      end: filters.reportEnd,
    },
  };
}

async function runHermesReview(row: CampaignRow): Promise<void> {
  if (!project.value || reviewingIds.value.includes(row.campaignId)) return;
  reviewingIds.value.push(row.campaignId);
  const audit = await reviewWithHermes(reviewEvidence(row));
  project.value.aiReviews.push(audit);
  project.value = { ...project.value };
  await saveProject(project.value);
  reviewingIds.value = reviewingIds.value.filter((id) => id !== row.campaignId);
  hermesState.value =
    audit.status === "success"
      ? { ok: true, message: "Hermes复核完成" }
      : { ok: false, message: audit.errorMessage ?? "Hermes复核失败" };
}

async function resolveConflict(
  id: string,
  action: "accept" | "keep",
): Promise<void> {
  if (!project.value) return;
  project.value =
    action === "accept"
      ? acceptLockedConflict(project.value, id)
      : keepLockedConflict(project.value, id);
  await saveProject(project.value);
}

async function importAiReview(event: Event): Promise<void> {
  aiImportError.value = "";
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file || !project.value) return;
  try {
    const audit = await importReviewFile(file);
    if (!project.value.campaigns.some((row) => row.campaignId === audit.campaignId)) {
      throw new Error("AI结果中的Campaign ID不属于当前历史库。");
    }
    project.value.aiReviews.push(audit);
    await saveProject(project.value);
  } catch (error) {
    aiImportError.value =
      error instanceof Error ? error.message : "AI结果导入失败。";
  } finally {
    input.value = "";
  }
}
</script>

<template>
  <div v-if="loading" class="loading-screen">正在恢复本机滚动历史库…</div>
  <div v-else class="app-shell">
    <header class="topbar">
      <div class="brand">
        <span class="brand__mark">TI</span>
        <div>
          <strong>TIB 分时投放分析</strong>
          <small>滚动历史库 · 成熟度管理 · 规则先于AI</small>
        </div>
      </div>
      <div class="topbar__actions">
        <span v-if="project" class="save-state"><i /> 历史库已保存在本机</span>
        <button class="button button--ghost" @click="importOpen = true">
          导入最新报表
        </button>
        <button v-if="project" class="button button--ghost" @click="auditOpen = true">
          导入审计
          <span v-if="unresolvedConflicts.length">({{ unresolvedConflicts.length }})</span>
        </button>
        <button class="button button--ghost" @click="settingsOpen = true">
          判断阈值
        </button>
        <button v-if="project" class="button button--danger" @click="clearData">
          清除历史库
        </button>
      </div>
    </header>

    <main v-if="project" class="dashboard">
      <section class="hero">
        <div>
          <p class="eyebrow">DECISION-SAFE OVERVIEW</p>
          <h1>广告分时观察与成熟决策</h1>
          <p>
            历史库 {{ historyPeriod.start }} 至
            {{ historyPeriod.end }} · {{ project.quality.campaignCount }}
            条活动 · {{ project.config.accountTimezone }}
          </p>
        </div>
        <div class="hero__status">
          <span>Schema v2</span>
          <span>{{ project.hourly.length.toLocaleString("zh-CN") }} 个日期×小时事实</span>
          <span :class="{ warn: project.quality.tibPeriodMatch !== 'exact' }">
            TIB周期：
            {{ project.quality.tibPeriodMatch === "exact" ? "一致" : "未通过" }}
          </span>
        </div>
      </section>

      <section class="view-switch">
        <button
          :class="{ active: viewMode === 'observation' }"
          @click="
            viewMode = 'observation';
            applyDefaultWindow();
          "
        >
          <strong>最新14天观察表</strong>
          <span>D-15至D-2 · 流量、预算覆盖、候选发现</span>
        </button>
        <button
          :class="{ active: viewMode === 'decision' }"
          @click="
            viewMode = 'decision';
            applyDefaultWindow();
          "
        >
          <strong>成熟14天决策表</strong>
          <span>SP D-21至D-8 · 只用已锁定数据</span>
        </button>
      </section>

      <section class="filter-panel">
        <label>
          <span>开始日期</span>
          <input
            v-model="filters.reportStart"
            type="date"
            @change="rangePreset = 'custom'"
          />
        </label>
        <label>
          <span>结束日期</span>
          <input
            v-model="filters.reportEnd"
            type="date"
            @change="rangePreset = 'custom'"
          />
        </label>
        <label>
          <span>历史范围</span>
          <select
            :value="rangePreset"
            @change="applyRangePreset(($event.target as HTMLSelectElement).value as RangePreset)"
          >
            <option value="14">默认14天</option>
            <option value="30">最近30天</option>
            <option value="60">最近60天</option>
            <option value="90">最近90天</option>
            <option value="custom">自定义</option>
          </select>
        </label>
        <label>
          <span>运营名</span>
          <select
            v-model="filters.operator"
            @change="
              filters.productLine = '';
              filters.campaignId = '';
            "
          >
            <option value="">全部运营</option>
            <option v-for="item in operators" :key="item" :value="item">
              {{ item }}
            </option>
          </select>
        </label>
        <label>
          <span>产品线</span>
          <select
            v-model="filters.productLine"
            @change="
              selectedProductLine = filters.productLine;
              filters.campaignId = '';
            "
          >
            <option value="">全部产品线</option>
            <option v-for="item in productLines" :key="item" :value="item">
              {{ item }}
            </option>
          </select>
        </label>
        <label>
          <span>广告类型</span>
          <select v-model="filters.adType" @change="filters.campaignId = ''">
            <option value="">全部类型</option>
            <option v-for="item in adTypes" :key="item" :value="item">
              {{ item }}
            </option>
          </select>
        </label>
        <label class="filter-panel__campaign">
          <span>广告活动</span>
          <select v-model="filters.campaignId">
            <option value="">全部活动</option>
            <option
              v-for="item in campaignOptions"
              :key="item.campaignId"
              :value="item.campaignId"
            >
              {{ item.campaignName }}
            </option>
          </select>
        </label>
      </section>

      <section
        class="mode-notice"
        :class="`mode-notice--${viewMode}`"
      >
        <strong>
          {{ viewMode === "observation" ? "观察口径" : "正式决策口径" }}
        </strong>
        <span>
          <template v-if="viewMode === 'observation'">
            处理中日期只计展示、点击、花费；回填中购买和ROAS仍可能增加。
          </template>
          <template v-else-if="isStandardDecisionWindow">
            只汇总已成熟记录；仍需目标ROAS、样本门槛和TIB周期全部通过才能进入正式四象限。
          </template>
          <template v-else>
            当前不是标准成熟14天窗口，仅供历史查看，正式候选已暂停。
          </template>
        </span>
      </section>

      <section class="metric-grid">
        <MetricCard label="广告花费" :value="formatMoney(summary.spend)" />
        <MetricCard label="广告归因销售" :value="formatMoney(summary.adSales)" />
        <MetricCard label="购买量" :value="formatNumber(summary.purchases)" />
        <MetricCard
          :label="viewMode === 'observation' ? '观察ROAS' : '最终ROAS'"
          :value="formatRatio(summary.roas, 'multiple')"
          hint="汇总销售额 ÷ 汇总花费"
        />
        <MetricCard
          label="ACOS"
          :value="formatRatio(summary.acos, 'percent')"
          hint="花费 ÷ 广告归因销售"
        />
        <MetricCard label="CPC" :value="formatCpc(summary.cpc)" hint="固定保留两位小数" />
        <MetricCard
          label="CVR"
          :value="formatRatio(summary.cvr, 'percent')"
          hint="购买量 ÷ 点击量"
        />
        <MetricCard
          label="加权TIB"
          :value="formatRatio(summary.weightedTib, 'percent')"
          hint="只对当前活动按花费加权"
        />
      </section>

      <section class="trust-panel trust-panel--expanded">
        <div>
          <p class="eyebrow">END-TO-END QUALITY</p>
          <h2>端到端数据可信度</h2>
          <p>从表内日期、唯一键、活动匹配、成熟度到正式准入逐层检查。</p>
        </div>
        <div class="trust-panel__meter">
          <span>标准窗口日期覆盖</span>
          <strong>{{ (dateCoverage * 100).toFixed(1) }}%</strong>
          <progress :value="dateCoverage" max="1" />
        </div>
        <div class="trust-panel__meter">
          <span>活动名结构识别</span>
          <strong>{{ (recognitionRate * 100).toFixed(1) }}%</strong>
          <progress :value="recognitionRate" max="1" />
        </div>
        <div class="trust-panel__meter">
          <span>TIB活动精确匹配</span>
          <strong>{{ (tibRate * 100).toFixed(1) }}%</strong>
          <progress :value="tibRate" max="1" />
        </div>
        <div class="trust-panel__meter">
          <span>成熟事实占比</span>
          <strong>{{ (summary.matureFactShare * 100).toFixed(1) }}%</strong>
          <progress :value="summary.matureFactShare" max="1" />
        </div>
        <ul>
          <li v-for="warning in project.quality.warnings" :key="warning">
            {{ warning }}
          </li>
          <li>
            本批次内部合并 {{ project.quality.duplicateRowsCollapsed }} 条重复唯一键；
            拒绝 {{ project.quality.rejectedAdRows }} 行。
          </li>
          <li>TACOS、搜索词和广告位本轮未纳入，不生成相关估算。</li>
        </ul>
      </section>

      <section id="hour-charts" class="section-heading">
        <div>
          <p class="eyebrow">24-HOUR DRILLDOWN</p>
          <h2>24小时分时证据</h2>
          <p>“孤立信号”表示有方向但样本未达门槛，不再使用含义模糊的“待验证”。</p>
        </div>
        <div class="section-actions">
          <div class="segmented">
            <button :class="{ active: bandMode === 'none' }" @click="bandMode = 'none'">无背景</button>
            <button :class="{ active: bandMode === 'industry' }" @click="bandMode = 'industry'">行业参考</button>
            <button :class="{ active: bandMode === 'actual' }" @click="bandMode = 'actual'">数据实际</button>
          </div>
          <button class="button button--secondary" @click="exportHourly(hours)">导出小时聚合</button>
        </div>
      </section>
      <section class="chart-grid">
        <HourChart kind="traffic" :rows="hours" title="展示、点击与广告购买量" subtitle="处理中日期的购买量不计入图表" :band-mode="bandMode" :windows="windows" :currency="currency" />
        <HourChart kind="value" :rows="hours" title="广告花费与广告归因销售额" :subtitle="viewMode === 'observation' ? '观察销售额，回填中仍可能增加' : '已成熟销售额'" :band-mode="bandMode" :windows="windows" :currency="currency" />
        <HourChart kind="roas" :rows="hours" :title="viewMode === 'observation' ? '小时观察ROAS' : '小时最终ROAS'" subtitle="汇总销售额÷汇总花费；零花费不计算" :band-mode="bandMode" :windows="windows" :currency="currency" />
      </section>
      <section class="window-panel">
        <div class="window-panel__chips">
          <span v-for="window in windows" :key="`${window.start}-${window.end}-${window.signal}`" :class="`chip chip--${window.classification}`">
            {{ window.label }}
          </span>
        </div>
        <p>小时信号要求点击≥{{ thresholds.minClicks }}、购买≥{{ thresholds.minPurchases }}、活跃日≥{{ thresholds.minActiveDays }}。孤立信号只展示方向，不生成调价动作。</p>
      </section>

      <section class="maturity-layout">
        <article class="maturity-card">
          <p class="eyebrow">DATE MATURITY</p>
          <h2>日期成熟状态</h2>
          <div class="maturity-summary">
            <div class="status status--processing">
              <strong>{{ maturityCounts.processing }}</strong><span>处理中</span>
              <small>最近48小时，仅用流量与花费</small>
            </div>
            <div class="status status--backfilling">
              <strong>{{ maturityCounts.backfilling }}</strong><span>回填中</span>
              <small>购买与ROAS尚未锁定</small>
            </div>
            <div class="status status--mature">
              <strong>{{ maturityCounts.mature }}</strong><span>已成熟</span>
              <small>允许进入正式判断</small>
            </div>
          </div>
          <div class="date-chip-list">
            <span
              v-for="row in maturityDates"
              :key="row.date"
              :class="`date-chip date-chip--${row.status}`"
            >
              {{ row.date }} · {{ maturityLabel(row.status) }}
            </span>
            <span v-if="!maturityDates.length" class="empty-inline">
              当前筛选范围没有数据
            </span>
          </div>
        </article>
        <article class="import-card">
          <p class="eyebrow">ROLLING IMPORT</p>
          <h2>最近导入批次</h2>
          <template v-if="lastBatch">
            <strong>{{ lastBatch.adPeriod.start }} 至 {{ lastBatch.adPeriod.end }}</strong>
            <dl>
              <div><dt>新增</dt><dd>{{ lastBatch.inserted }}</dd></div>
              <div><dt>回填覆盖</dt><dd>{{ lastBatch.updated }}</dd></div>
              <div><dt>成熟锁定跳过</dt><dd>{{ lastBatch.lockedSkipped }}</dd></div>
              <div><dt>锁定冲突</dt><dd>{{ lastBatch.conflicts }}</dd></div>
            </dl>
            <small>导入时间 {{ new Date(lastBatch.importedAt).toLocaleString("zh-CN") }}</small>
          </template>
        </article>
      </section>

      <section class="section-heading">
        <div>
          <p class="eyebrow">CANDIDATE FUNNEL</p>
          <h2>四象限前置筛查</h2>
          <p>先过成熟度、样本、目标ROAS和TIB周期；未过门槛的活动不进入正式四象限。</p>
        </div>
        <span :class="`hermes-state ${hermesState.ok ? 'ok' : 'warn'}`">
          {{ hermesState.message }}
        </span>
      </section>

      <section class="quadrant-grid">
        <article>
          <span>低TIB × 高ROAS</span>
          <strong>{{ quadrants.lowTibHighRoas }}</strong>
          <small>优先检查预算截断，但不自动加价</small>
        </article>
        <article>
          <span>低TIB × 低ROAS</span>
          <strong>{{ quadrants.lowTibLowRoas }}</strong>
          <small>先查流量质量与预算消耗</small>
        </article>
        <article>
          <span>高TIB × 高ROAS</span>
          <strong>{{ quadrants.highTibHighRoas }}</strong>
          <small>稳定参照活动</small>
        </article>
        <article>
          <span>高TIB × 低ROAS</span>
          <strong>{{ quadrants.highTibLowRoas }}</strong>
          <small>覆盖充分但效率不足</small>
        </article>
        <article class="quadrant-grid__muted">
          <span>中TIB条件带 / 不可判定</span>
          <strong>{{ quadrants.conditional + quadrants.blocked }}</strong>
          <small>不强行塞入四象限</small>
        </article>
      </section>

      <section class="section-heading">
        <div>
          <p class="eyebrow">PRODUCT LINES</p>
          <h2>产品线候选入口</h2>
          <p>先填写产品线目标ROAS，再下钻活动；TIB不会用产品线平均值补齐。</p>
        </div>
      </section>
      <section class="table-card">
        <div class="table-scroll">
          <table>
            <thead>
              <tr>
                <th>产品线</th><th>活动数</th><th>花费</th><th>ROAS</th>
                <th>目标ROAS</th><th>加权TIB</th><th>TIB覆盖</th>
                <th>正式候选</th><th>被拦截</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="row in productRows"
                :key="row.productLine"
                class="clickable-row"
                @click="selectProductLine(row.productLine)"
              >
                <td><strong>{{ row.productLine }}</strong><small>{{ row.operator }} · {{ row.product }}</small></td>
                <td>{{ row.campaignCount }}</td>
                <td>{{ formatMoney(row.spend) }}</td>
                <td>{{ formatRatio(row.roas, "multiple") }}</td>
                <td @click.stop>
                  <input
                    class="target-input"
                    type="number"
                    min="0.01"
                    step="0.1"
                    :value="row.targetRoas ?? ''"
                    placeholder="必填"
                    @change="setTarget(row.productLine, ($event.target as HTMLInputElement).value)"
                  />
                </td>
                <td>{{ formatRatio(row.weightedTib, "percent") }}</td>
                <td>{{ (row.tibCoverage * 100).toFixed(0) }}%</td>
                <td><span class="badge badge--ok">{{ row.eligibleCampaigns }}</span></td>
                <td><span class="badge badge--warn">{{ row.blockedCampaigns }}</span></td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section id="campaign-detail" class="section-heading">
        <div>
          <p class="eyebrow">CAMPAIGN SCREENING</p>
          <h2>活动候选明细 <span v-if="selectedProductLine">· {{ selectedProductLine }}</span></h2>
          <p>最后流量小时按日期计算中位数；承接证据必须来自同一天、同产品线其他活动。</p>
        </div>
        <button class="button button--secondary" @click="exportCampaignExceptions(campaignRows)">
          导出候选与拦截原因
        </button>
      </section>
      <section class="table-card">
        <div class="table-scroll">
          <table class="campaign-table">
            <thead>
              <tr>
                <th>广告活动</th><th>TIB / 分层</th><th>ROAS / 目标</th>
                <th>CPC</th><th>样本稳定性</th><th>流量截止</th>
                <th>表面位置</th><th>候选等级</th><th>Hermes复核</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in campaignRows" :key="row.campaignId">
                <td class="campaign-name" @click="selectCampaign(row.campaignId)">
                  <strong>{{ row.campaignName }}</strong>
                  <small>ID {{ row.campaignId }} · {{ row.adType }}</small>
                </td>
                <td>
                  {{ formatRatio(row.tib ?? null, "percent") }}
                  <small>{{ row.tibBand === "low" ? "低TIB" : row.tibBand === "middle" ? "中TIB" : row.tibBand === "high" ? "高TIB" : "未匹配" }}</small>
                </td>
                <td>{{ formatRatio(row.roas, "multiple") }}<small>目标 {{ row.targetRoas?.toFixed(2) ?? "未填" }}</small></td>
                <td>{{ formatCpc(row.cpc) }}</td>
                <td class="stability-cell">
                  <span>成熟{{ row.matureDays }}天 / 活跃{{ row.activeDays }}天</span>
                  <span>点击{{ formatNumber(row.clicks) }} / 购买{{ formatNumber(row.purchases) }}</span>
                  <span>购买日{{ row.purchaseDays }}天 / 集中度{{ formatRatio(row.maxDailyOrderConcentration, "percent") }}</span>
                </td>
                <td>
                  {{ row.medianLastActiveHour === null ? "无有效流量" : `${row.medianLastActiveHour.toFixed(1)}时（中位数）` }}
                  <small>同日承接 {{ row.sameDayHandoffDays }} 天</small>
                </td>
                <td>{{ quadrantLabel(row.rawQuadrant) }}</td>
                <td>
                  <span :class="`badge candidate candidate--${row.actionEligible ? 'ok' : 'blocked'}`">{{ row.candidateLevel }}</span>
                  <details>
                    <summary>查看{{ row.gates.filter((gate) => !gate.passed).length }}项拦截</summary>
                    <ul class="gate-list">
                      <li v-for="gate in row.gates" :key="gate.key" :class="{ passed: gate.passed }">
                        {{ gate.passed ? "✓" : "×" }} {{ gate.label }}：{{ gate.value }}
                      </li>
                    </ul>
                  </details>
                </td>
                <td class="ai-cell">
                  <button
                    class="button button--tiny"
                    :disabled="reviewingIds.includes(row.campaignId)"
                    @click="runHermesReview(row)"
                  >
                    {{ reviewingIds.includes(row.campaignId) ? "复核中…" : "Hermes复核" }}
                  </button>
                  <button class="text-button" @click="exportReviewPackage(reviewEvidence(row), latestReview(row.campaignId))">
                    导出分析包
                  </button>
                  <small v-if="latestReview(row.campaignId)">
                    {{ latestReview(row.campaignId)?.status }} ·
                    {{ latestReview(row.campaignId)?.review?.candidateLevel ?? latestReview(row.campaignId)?.errorCode }}
                  </small>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

    </main>

    <main v-else class="empty-state">
      <p class="eyebrow">SCHEMA V2 REIMPORT REQUIRED</p>
      <h1>重新导入带日期的小时报告</h1>
      <p>旧版累计小时聚合无法恢复日期与归因成熟度，因此不迁移。新版本只从表内日期字段识别周期。</p>
      <button class="button button--primary" @click="importOpen = true">选择报表</button>
    </main>

    <div v-if="importOpen" class="modal-backdrop" @click.self="project && (importOpen = false)">
      <section class="modal modal--wide">
        <header class="modal__header">
          <div>
            <p class="eyebrow">ROLLING IMPORT</p>
            <h2>写入滚动历史库</h2>
            <p>系统读取表内最小/最大日期；不读取文件名，也不把活动生命周期当统计周期。</p>
          </div>
          <button v-if="project" class="icon-button" @click="importOpen = false">×</button>
        </header>
        <div class="file-grid">
          <FileDrop title="广告日期×小时报告" description="必须包含日期、小时、账户ID、活动ID、广告产品与指标" :file="adFile" @change="adFile = $event" />
          <FileDrop title="TIB活动报告" description="TIB值可导入；正式四象限还要求明确报表周期" :file="tibFile" @change="tibFile = $event" />
        </div>
        <div class="date-grid">
          <label>
            <span>广告账户时区（首次必选）</span>
            <select v-model="accountTimezone">
              <option v-for="timezone in TIMEZONES" :key="timezone.value" :value="timezone.value">{{ timezone.label }}</option>
            </select>
          </label>
          <div class="import-rule">
            <strong>唯一键</strong>
            <span>账户ID + Campaign ID + 日期 + 小时 + 广告产品</span>
          </div>
          <p>成熟数据默认锁定；新值不同会进入冲突审计，不会静默覆盖。</p>
        </div>
        <div v-if="importPhase" class="progress-row"><span>{{ importPhase }}</span><progress :value="importProgress" max="1" /></div>
        <p v-if="importError" class="error-message">{{ importError }}</p>
        <footer class="modal__footer">
          <button v-if="project" class="button button--ghost" @click="importOpen = false">取消</button>
          <button class="button button--primary" @click="importData">校验并合并</button>
        </footer>
      </section>
    </div>

    <div v-if="settingsOpen" class="modal-backdrop" @click.self="settingsOpen = false">
      <section class="modal">
        <header class="modal__header"><div><p class="eyebrow">DECISION GATES</p><h2>判断阈值</h2></div><button class="icon-button" @click="settingsOpen = false">×</button></header>
        <div class="settings-grid">
          <label><span>最低成熟天数</span><input v-model.number="thresholds.minMatureDays" type="number" min="1" /></label>
          <label><span>最低活跃天数</span><input v-model.number="thresholds.minActiveDays" type="number" min="1" /></label>
          <label><span>最低点击量</span><input v-model.number="thresholds.minClicks" type="number" min="1" /></label>
          <label><span>最低购买量</span><input v-model.number="thresholds.minPurchases" type="number" min="1" /></label>
          <label><span>最低购买天数</span><input v-model.number="thresholds.minPurchaseDays" type="number" min="1" /></label>
          <label><span>单日订单集中度上限（%）</span><input :value="thresholds.maxOrderConcentration * 100" type="number" min="1" max="100" @input="thresholds.maxOrderConcentration = Number(($event.target as HTMLInputElement).value) / 100" /></label>
          <label><span>小时ROAS偏离基准（%）</span><input :value="thresholds.efficiencyDelta * 100" type="number" min="1" max="100" @input="thresholds.efficiencyDelta = Number(($event.target as HTMLInputElement).value) / 100" /></label>
        </div>
        <p class="modal-note">TIB分层固定为：低于60%、60%至不足90%、90%及以上。网页只给规则位置与风险，不自动生成调价动作。</p>
        <footer class="modal__footer"><button class="button button--primary" @click="settingsOpen = false">保存</button></footer>
      </section>
    </div>

    <div v-if="auditOpen && project" class="modal-backdrop" @click.self="auditOpen = false">
      <section class="modal modal--audit">
        <header class="modal__header"><div><p class="eyebrow">IMPORT & AI AUDIT</p><h2>导入、回填与冲突审计</h2></div><button class="icon-button" @click="auditOpen = false">×</button></header>
        <div class="audit-grid">
          <article><strong>{{ project.importBatches.length }}</strong><span>导入批次</span></article>
          <article><strong>{{ project.backfillChanges.length }}</strong><span>归因回填变化</span></article>
          <article><strong>{{ unresolvedConflicts.length }}</strong><span>待处理锁定冲突</span></article>
          <article><strong>{{ project.aiReviews.length }}</strong><span>AI审计记录</span></article>
        </div>
        <section v-if="unresolvedConflicts.length" class="conflict-list">
          <h3>成熟数据冲突</h3>
          <article v-for="conflict in unresolvedConflicts" :key="conflict.id">
            <div><strong>{{ conflict.date }} · {{ conflict.hour }}时 · ID {{ conflict.campaignId }}</strong><small>购买 {{ conflict.lockedPurchases }}→{{ conflict.incomingPurchases }}；销售 {{ formatMoney(conflict.lockedSales, 2) }}→{{ formatMoney(conflict.incomingSales, 2) }}</small></div>
            <div><button class="button button--ghost" @click="resolveConflict(conflict.id, 'keep')">保留锁定值</button><button class="button button--secondary" @click="resolveConflict(conflict.id, 'accept')">人工解锁并采用新值</button></div>
          </article>
        </section>
        <section class="ai-import">
          <h3>Hermes JSON备用回导</h3>
          <label class="button button--secondary">选择AI结果JSON<input class="sr-only" type="file" accept=".json,application/json" @change="importAiReview" /></label>
          <p v-if="aiImportError" class="error-message">{{ aiImportError }}</p>
        </section>
      </section>
    </div>
  </div>
</template>
