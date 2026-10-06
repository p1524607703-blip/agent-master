import type {
  CampaignMeta,
  CampaignRow,
  CandidateGate,
  CandidateLevel,
  DashboardProject,
  DataViewMode,
  EfficiencyClass,
  FilterState,
  HourMetric,
  HourSummary,
  ProductLineRow,
  RawQuadrant,
  SummaryMetrics,
  Thresholds,
  TibBand,
  TimeWindow,
} from "@/types";
import { periodIsExact } from "./dates";

const HOURS = Array.from({ length: 24 }, (_, index) => index);

function ratio(numerator: number, denominator: number): number | null {
  return denominator > 0 ? numerator / denominator : null;
}

export function applyFilters(
  rows: HourMetric[],
  filters: FilterState,
): HourMetric[] {
  return rows.filter((row) => {
    if (filters.operator && row.operator !== filters.operator) return false;
    if (filters.productLine && row.productLine !== filters.productLine) return false;
    if (filters.adType && row.adType !== filters.adType) return false;
    if (filters.campaignId && row.campaignId !== filters.campaignId) return false;
    if (filters.reportStart && row.date < filters.reportStart) return false;
    if (filters.reportEnd && row.date > filters.reportEnd) return false;
    return true;
  });
}

export function rowsForView(
  rows: HourMetric[],
  mode: DataViewMode,
): HourMetric[] {
  if (mode === "decision") {
    return rows.filter((row) => row.maturityStatus === "mature");
  }
  return rows.map((row) =>
    row.maturityStatus === "processing"
      ? { ...row, purchases: 0, adSales: 0 }
      : row,
  );
}

function stability(rows: HourMetric[]) {
  const calendarDays = new Set(rows.map((row) => row.date)).size;
  const matureRows = rows.filter((row) => row.maturityStatus === "mature");
  const matureDays = new Set(matureRows.map((row) => row.date)).size;
  const activeDays = new Set(
    matureRows
      .filter(
        (row) => row.impressions > 0 || row.clicks > 0 || row.spend > 0,
      )
      .map((row) => row.date),
  ).size;
  const clickDays = new Set(
    matureRows.filter((row) => row.clicks > 0).map((row) => row.date),
  ).size;
  const purchaseByDay = new Map<string, number>();
  for (const row of matureRows) {
    purchaseByDay.set(
      row.date,
      (purchaseByDay.get(row.date) ?? 0) + row.purchases,
    );
  }
  const purchaseDays = [...purchaseByDay.values()].filter(
    (purchases) => purchases > 0,
  ).length;
  const maturePurchases = [...purchaseByDay.values()].reduce(
    (sum, value) => sum + value,
    0,
  );
  const maxDailyOrderConcentration =
    maturePurchases > 0
      ? Math.max(0, ...purchaseByDay.values()) / maturePurchases
      : null;
  return {
    calendarDays,
    matureDays,
    activeDays,
    clickDays,
    purchaseDays,
    maxDailyOrderConcentration,
    matureFactShare: rows.length ? matureRows.length / rows.length : 0,
  };
}

export function summarizeRows(rows: HourMetric[]): SummaryMetrics {
  const totals = rows.reduce(
    (sum, row) => {
      sum.impressions += row.impressions;
      sum.clicks += row.clicks;
      sum.spend += row.spend;
      sum.purchases += row.purchases;
      sum.adSales += row.adSales;
      return sum;
    },
    { impressions: 0, clicks: 0, spend: 0, purchases: 0, adSales: 0 },
  );
  const conversionEligible = rows
    .filter((row) => row.maturityStatus !== "processing")
    .reduce(
      (sum, row) => {
        sum.clicks += row.clicks;
        sum.spend += row.spend;
        sum.purchases += row.purchases;
        sum.adSales += row.adSales;
        return sum;
      },
      { clicks: 0, spend: 0, purchases: 0, adSales: 0 },
    );
  return {
    ...totals,
    ...stability(rows),
    roas: ratio(conversionEligible.adSales, conversionEligible.spend),
    acos: ratio(conversionEligible.spend, conversionEligible.adSales),
    cpc: ratio(totals.spend, totals.clicks),
    cvr: ratio(conversionEligible.purchases, conversionEligible.clicks),
    weightedTib: null,
  };
}

export function weightedTib(
  rows: HourMetric[],
  campaigns: CampaignMeta[],
): number | null {
  const includedIds = new Set(rows.map((row) => row.campaignId));
  const spendByCampaign = new Map<string, number>();
  for (const row of rows) {
    spendByCampaign.set(
      row.campaignId,
      (spendByCampaign.get(row.campaignId) ?? 0) + row.spend,
    );
  }
  let weighted = 0;
  let weight = 0;
  for (const campaign of campaigns) {
    if (!includedIds.has(campaign.campaignId) || campaign.tib === undefined) {
      continue;
    }
    const spend = spendByCampaign.get(campaign.campaignId) ?? 0;
    if (spend <= 0) continue;
    weighted += campaign.tib * spend;
    weight += spend;
  }
  return weight > 0 ? weighted / weight : null;
}

function classifyHour(
  summary: Omit<HourSummary, "classification" | "signal">,
  baseline: number | null,
  thresholds: Thresholds,
): Pick<HourSummary, "classification" | "signal"> {
  const enoughVolume =
    summary.clicks >= thresholds.minClicks &&
    summary.purchases >= thresholds.minPurchases &&
    summary.activeDays >= thresholds.minActiveDays;
  const hasSignal =
    summary.purchases > 0 ||
    summary.clicks >= Math.max(5, Math.floor(thresholds.minClicks / 2));
  const signal = enoughVolume
    ? "sufficient"
    : hasSignal
      ? "isolated"
      : "insufficient";
  if (signal === "insufficient" || baseline === null || summary.roas === null) {
    return { signal, classification: "insufficient" };
  }
  if (summary.roas >= baseline * (1 + thresholds.efficiencyDelta)) {
    return { signal, classification: "efficient" };
  }
  if (summary.roas <= baseline * (1 - thresholds.efficiencyDelta)) {
    return { signal, classification: "inefficient" };
  }
  return { signal, classification: "nearBaseline" };
}

export function hourlySummary(
  rows: HourMetric[],
  thresholds: Thresholds,
): HourSummary[] {
  const baseline = summarizeRows(rows).roas;
  return HOURS.map((hour) => {
    const hourRows = rows.filter((row) => row.hour === hour);
    const totals = summarizeRows(hourRows);
    const activeDays = new Set(
      hourRows
        .filter((row) => row.spend > 0 || row.clicks > 0 || row.impressions > 0)
        .map((row) => row.date),
    ).size;
    const base = {
      hour,
      impressions: totals.impressions,
      clicks: totals.clicks,
      spend: totals.spend,
      purchases: totals.purchases,
      adSales: totals.adSales,
      roas: totals.roas,
      acos: totals.acos,
      cpc: totals.cpc,
      cvr: totals.cvr,
      activeDays,
    };
    return { ...base, ...classifyHour(base, baseline, thresholds) };
  });
}

const LABELS: Record<EfficiencyClass, string> = {
  efficient: "高效",
  inefficient: "低效",
  nearBaseline: "基准附近",
  insufficient: "样本不足",
};

const SIGNAL_LABELS = {
  sufficient: "样本充分",
  isolated: "孤立信号",
  insufficient: "样本不足",
} as const;

export function mergeTimeWindows(hours: HourSummary[]): TimeWindow[] {
  const windows: TimeWindow[] = [];
  for (const item of hours) {
    const last = windows[windows.length - 1];
    if (
      last &&
      last.classification === item.classification &&
      last.signal === item.signal &&
      last.end + 1 === item.hour
    ) {
      last.end = item.hour;
      last.isolated = last.start === last.end;
    } else {
      windows.push({
        start: item.hour,
        end: item.hour,
        classification: item.classification,
        signal: item.signal,
        isolated: true,
        label: "",
      });
    }
  }
  return windows.map((window) => {
    const time = `${String(window.start).padStart(2, "0")}:00–${String(
      window.end,
    ).padStart(2, "0")}:59`;
    return {
      ...window,
      label: `${time} ${LABELS[window.classification]} · ${
        SIGNAL_LABELS[window.signal]
      }`,
    };
  });
}

export function tibBand(tib: number | undefined): TibBand {
  if (tib === undefined) return "unknown";
  if (tib < 0.6) return "low";
  if (tib < 0.9) return "middle";
  return "high";
}

function quadrant(
  band: TibBand,
  roas: number | null,
  target: number | null,
): RawQuadrant {
  if (band === "middle") return "conditional";
  if (band === "unknown" || roas === null || target === null) return "blocked";
  const highRoas = roas >= target;
  if (band === "low") {
    return highRoas ? "lowTibHighRoas" : "lowTibLowRoas";
  }
  return highRoas ? "highTibHighRoas" : "highTibLowRoas";
}

function candidateGates(
  summary: SummaryMetrics,
  meta: CampaignMeta | undefined,
  target: number | null,
  expectedStart: string,
  expectedEnd: string,
  thresholds: Thresholds,
  standardDecisionWindow: boolean,
): CandidateGate[] {
  const concentration = summary.maxDailyOrderConcentration;
  const exact = periodIsExact(
    meta?.tibPeriod.start,
    meta?.tibPeriod.end,
    expectedStart,
    expectedEnd,
  );
  return [
    {
      key: "decisionWindow",
      label: "使用标准成熟14天窗口",
      passed: standardDecisionWindow,
      value: standardDecisionWindow ? "标准窗口" : "自定义/历史范围",
    },
    {
      key: "matureDays",
      label: "成熟完整数据≥7天",
      passed: summary.matureDays >= thresholds.minMatureDays,
      value: `${summary.matureDays}天`,
    },
    {
      key: "activeDays",
      label: "活跃天数≥5",
      passed: summary.activeDays >= thresholds.minActiveDays,
      value: `${summary.activeDays}天`,
    },
    {
      key: "clicks",
      label: "点击≥30",
      passed: summary.clicks >= thresholds.minClicks,
      value: `${Math.round(summary.clicks)}`,
    },
    {
      key: "purchases",
      label: "购买≥5",
      passed: summary.purchases >= thresholds.minPurchases,
      value: `${Math.round(summary.purchases)}`,
    },
    {
      key: "purchaseDays",
      label: "购买天数≥3",
      passed: summary.purchaseDays >= thresholds.minPurchaseDays,
      value: `${summary.purchaseDays}天`,
    },
    {
      key: "concentration",
      label: "单日订单集中度<60%",
      passed:
        concentration !== null &&
        concentration < thresholds.maxOrderConcentration,
      value:
        concentration === null
          ? "不可计算"
          : `${(concentration * 100).toFixed(1)}%`,
    },
    {
      key: "target",
      label: "产品线目标ROAS已填写",
      passed: target !== null && target > 0,
      value: target === null ? "未填写" : target.toFixed(2),
    },
    {
      key: "period",
      label: "TIB与成熟窗口完全一致",
      passed: exact,
      value: exact
        ? "完全一致"
        : meta?.tibPeriod.start && meta?.tibPeriod.end
          ? `${meta.tibPeriod.start}～${meta.tibPeriod.end}`
          : "周期未知",
    },
  ];
}

function candidateLevel(
  mode: DataViewMode,
  band: TibBand,
  gates: CandidateGate[],
): CandidateLevel {
  if (mode !== "decision") return "继续观察";
  if (band === "middle") return "条件候选";
  if (band === "unknown") return "暂不进入TIB优化";
  return gates.every((gate) => gate.passed)
    ? "正式候选"
    : "暂不进入TIB优化";
}

function median(values: number[]): number | null {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2
    ? sorted[middle]!
    : (sorted[middle - 1]! + sorted[middle]!) / 2;
}

export function buildCampaignRows(
  project: DashboardProject,
  filteredRows: HourMetric[],
  mode: DataViewMode,
  expectedStart: string,
  expectedEnd: string,
  standardDecisionWindow = true,
): CampaignRow[] {
  const totals = summarizeRows(filteredRows);
  const rowsByCampaign = new Map<string, HourMetric[]>();
  for (const row of filteredRows) {
    const campaignRows = rowsByCampaign.get(row.campaignId) ?? [];
    campaignRows.push(row);
    rowsByCampaign.set(row.campaignId, campaignRows);
  }
  return [...rowsByCampaign.entries()]
    .map(([campaignId, rows]) => {
      const meta = project.campaigns.find(
        (campaign) => campaign.campaignId === campaignId,
      );
      const summary = summarizeRows(rows);
      const productLine = meta?.productLine ?? rows[0]?.productLine ?? "未识别";
      const target = project.config.productRoasTargets[productLine] ?? null;
      const gates = candidateGates(
        summary,
        meta,
        target,
        expectedStart,
        expectedEnd,
        project.config.thresholds,
        standardDecisionWindow,
      );
      const band = tibBand(meta?.tib);
      const level = candidateLevel(mode, band, gates);

      const byDate = new Map<string, HourMetric[]>();
      for (const row of rows) {
        const values = byDate.get(row.date) ?? [];
        values.push(row);
        byDate.set(row.date, values);
      }
      const lastHours: number[] = [];
      const distribution: Record<string, number> = {};
      let handoffDays = 0;
      for (const [date, dayRows] of byDate) {
        const active = dayRows
          .filter(
            (row) => row.impressions > 0 || row.clicks > 0 || row.spend > 0,
          )
          .map((row) => row.hour);
        if (!active.length) continue;
        const last = Math.max(...active);
        lastHours.push(last);
        distribution[String(last)] = (distribution[String(last)] ?? 0) + 1;
        const otherAfter = filteredRows.some(
          (row) =>
            row.date === date &&
            row.productLine === productLine &&
            row.campaignId !== campaignId &&
            row.hour > last &&
            row.clicks > 0,
        );
        if (last < 23 && otherAfter) handoffDays += 1;
      }
      const medianLastActiveHour = median(lastHours);
      return {
        ...(meta ?? {
          advertiserAccountId:
            rows[0]?.advertiserAccountId ?? "unknown-account",
          campaignId,
          campaignName: rows[0]?.campaignName ?? campaignId,
          canonicalName: rows[0]?.campaignName ?? campaignId,
          operator: rows[0]?.operator ?? "未识别",
          product: rows[0]?.product ?? "未识别",
          productLine,
          recognized: false,
          adType: rows[0]?.adType ?? "未知类型",
          productKind: rows[0]?.productKind ?? "OTHER",
          currency: rows[0]?.currency ?? "USD",
          tibMatched: false,
          tibPeriod: {
            source: "none" as const,
            matchStatus: "unknown" as const,
          },
        }),
        ...summary,
        weightedTib: meta?.tib ?? null,
        tibBand: band,
        rawQuadrant: quadrant(band, summary.roas, target),
        candidateLevel: level,
        actionEligible: level === "正式候选",
        gates,
        medianLastActiveHour,
        lastActiveDistribution: distribution,
        activeHourCount: new Set(rows.map((row) => row.hour)).size,
        spendShare: totals.spend > 0 ? summary.spend / totals.spend : 0,
        purchaseShare:
          totals.purchases > 0 ? summary.purchases / totals.purchases : 0,
        sameDayHandoffDays: handoffDays,
        flowHandoff: handoffDays > 0,
        targetRoas: target,
        periodExact: gates.find((gate) => gate.key === "period")?.passed ?? false,
      };
    })
    .sort((a, b) => b.spend - a.spend);
}

export function buildProductRows(
  project: DashboardProject,
  filteredRows: HourMetric[],
  mode: DataViewMode,
  expectedStart: string,
  expectedEnd: string,
  standardDecisionWindow = true,
): ProductLineRow[] {
  const rowsByProductLine = new Map<string, HourMetric[]>();
  for (const row of filteredRows) {
    const rows = rowsByProductLine.get(row.productLine) ?? [];
    rows.push(row);
    rowsByProductLine.set(row.productLine, rows);
  }
  return [...rowsByProductLine.entries()]
    .map(([productLine, rows]) => {
      const ids = new Set(rows.map((row) => row.campaignId));
      const campaigns = project.campaigns.filter((campaign) =>
        ids.has(campaign.campaignId),
      );
      const summary = summarizeRows(rows);
      const candidateRows = buildCampaignRows(
        project,
        rows,
        mode,
        expectedStart,
        expectedEnd,
        standardDecisionWindow,
      );
      return {
        ...summary,
        weightedTib: weightedTib(rows, campaigns),
        operator: rows[0]?.operator ?? "未识别",
        product: rows[0]?.product ?? "未识别",
        productLine,
        campaignCount: ids.size,
        tibCoverage:
          campaigns.length > 0
            ? campaigns.filter((campaign) => campaign.tibMatched).length /
              campaigns.length
            : 0,
        targetRoas: project.config.productRoasTargets[productLine] ?? null,
        eligibleCampaigns: candidateRows.filter((row) => row.actionEligible).length,
        blockedCampaigns: candidateRows.filter(
          (row) => row.candidateLevel === "暂不进入TIB优化",
        ).length,
        windows: mergeTimeWindows(
          hourlySummary(rows, project.config.thresholds),
        ),
      };
    })
    .sort((a, b) => b.spend - a.spend);
}

export function quadrantCounts(rows: CampaignRow[]) {
  return rows.reduce(
    (result, row) => {
      result[row.rawQuadrant] += 1;
      return result;
    },
    {
      lowTibHighRoas: 0,
      lowTibLowRoas: 0,
      highTibHighRoas: 0,
      highTibLowRoas: 0,
      conditional: 0,
      blocked: 0,
    } satisfies Record<RawQuadrant, number>,
  );
}
