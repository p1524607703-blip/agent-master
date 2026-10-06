import type {
  BackfillChange,
  CampaignIdentity,
  CampaignMeta,
  DashboardProject,
  DataQuality,
  HourMetric,
  ImportBatch,
  LockedConflict,
  PeriodMatchStatus,
  ProjectConfig,
  ReportPeriod,
} from "@/types";
import { campaignKey, parseCampaignName } from "./campaign";
import {
  maturityStatus,
  normalizeProductKind,
  parseDateRange,
  parseFlexibleDate,
} from "./dates";
import {
  canonicalText,
  cleanHeader,
  getField,
  parseCsvFile,
  parseNumber,
  parseTib,
  type CsvRow,
} from "./parse";

const AD_FIELDS = {
  accountId: ["广告主账户 ID", "广告主账户ID", "advertiser account id"],
  hour: ["小时", "hour"],
  campaignId: ["广告活动编号", "campaign id", "campaign_id"],
  campaignName: ["广告活动名称", "campaign name", "campaign"],
  adType: ["广告产品", "类型", "ad product", "campaign type"],
  currency: ["预算货币", "货币", "currency"],
  impressions: ["展示量", "impressions"],
  viewableImpressions: ["可见展示量", "viewable impressions"],
  clicks: ["点击量", "clicks"],
  spend: ["总成本", "花费", "spend", "cost"],
  purchases: ["购买量", "订单量", "purchases", "orders"],
  adSales: ["销售额", "广告归因销售额", "sales", "attributed sales"],
} as const;

const DATE_FIELDS = {
  dateColumn: ["日期", "date"],
  reportDateColumn: ["报告日期", "report date"],
  statisticsDateColumn: ["统计日期", "statistics date"],
  explicitRangeColumn: ["报告日期范围", "统计日期范围", "date range"],
} as const;

const REPORT_START_FIELDS = ["报告开始日期", "统计开始日期", "report start date"];
const REPORT_END_FIELDS = ["报告结束日期", "统计结束日期", "report end date"];

const TIB_FIELDS = {
  campaignName: ["广告活动名称", "campaign name", "campaign"],
  status: ["状态", "status"],
  adType: ["类型", "广告产品", "type"],
  targeting: ["投放", "targeting"],
  biddingStrategy: ["广告活动竞价方案", "bidding strategy"],
  budget: ["广告活动预算金额", "广告活动预算金额 (转换)", "budget"],
  tib: ["平均预算内活跃时间", "TIB", "time in budget"],
} as const;

export interface ImportedAd {
  hourly: HourMetric[];
  identities: Map<string, CampaignIdentity>;
  rows: number;
  rejected: number;
  period: ReportPeriod;
  duplicateRowsCollapsed: number;
}

export interface ImportedTib {
  byName: Map<string, Partial<CampaignMeta>>;
  rows: number;
  rejected: number;
  period: ReportPeriod;
}

interface MergeStats {
  facts: HourMetric[];
  changes: BackfillChange[];
  conflicts: LockedConflict[];
  inserted: number;
  updated: number;
  lockedSkipped: number;
}

function fieldKey(
  row: CsvRow,
  aliases: readonly string[],
): string | undefined {
  return Object.keys(row).find((candidate) =>
    aliases.some(
      (alias) => cleanHeader(candidate).toLowerCase() === alias.toLowerCase(),
    ),
  );
}

export function extractReportPeriod(rows: CsvRow[]): ReportPeriod {
  const explicitStarts = rows
    .map((row) => parseFlexibleDate(getField(row, REPORT_START_FIELDS)))
    .filter((date): date is string => Boolean(date))
    .sort();
  const explicitEnds = rows
    .map((row) => parseFlexibleDate(getField(row, REPORT_END_FIELDS)))
    .filter((date): date is string => Boolean(date))
    .sort();
  if (explicitStarts.length && explicitEnds.length) {
    return {
      start: explicitStarts[0],
      end: explicitEnds[explicitEnds.length - 1],
      source: "explicitRangeColumn",
      sourceField: "报告开始日期＋报告结束日期",
      matchStatus: "unknown",
    };
  }
  for (const [source, aliases] of Object.entries(DATE_FIELDS) as Array<
    [keyof typeof DATE_FIELDS, readonly string[]]
  >) {
    const key = rows.map((row) => fieldKey(row, aliases)).find(Boolean);
    if (!key) continue;
    const dates: string[] = [];
    for (const row of rows) {
      const raw = row[key] ?? "";
      const range = parseDateRange(raw);
      if (range) dates.push(range.start, range.end);
    }
    if (dates.length) {
      dates.sort();
      return {
        start: dates[0],
        end: dates[dates.length - 1],
        source,
        sourceField: cleanHeader(key),
        matchStatus: "unknown",
      };
    }
  }
  return { source: "none", matchStatus: "unknown" };
}

function rowDate(row: CsvRow): string | undefined {
  for (const aliases of [
    DATE_FIELDS.dateColumn,
    DATE_FIELDS.reportDateColumn,
    DATE_FIELDS.statisticsDateColumn,
  ]) {
    const value = getField(row, aliases);
    const date = parseFlexibleDate(value);
    if (date) return date;
  }
  return undefined;
}

function factKey(
  advertiserAccountId: string,
  campaignId: string,
  date: string,
  hour: number,
  adType: string,
): string {
  return [advertiserAccountId, campaignId, date, hour, canonicalText(adType)]
    .map((value) => encodeURIComponent(String(value)))
    .join("|");
}

export function importAdRows(
  rows: CsvRow[],
  timezone = "America/Los_Angeles",
  importedAt = new Date().toISOString(),
  requirePeriod = true,
): ImportedAd {
  const aggregate = new Map<string, HourMetric>();
  const identities = new Map<string, CampaignIdentity>();
  let rejected = 0;
  let acceptedRows = 0;
  const period = extractReportPeriod(rows);

  for (const row of rows) {
    const date = rowDate(row);
    const hour = Math.trunc(parseNumber(getField(row, AD_FIELDS.hour)));
    const campaignName = getField(row, AD_FIELDS.campaignName);
    if (!campaignName || !date || hour < 0 || hour > 23) {
      rejected += 1;
      continue;
    }
    acceptedRows += 1;
    const parsed = parseCampaignName(campaignName);
    const campaignId =
      getField(row, AD_FIELDS.campaignId) || parsed.canonicalName.toLowerCase();
    const advertiserAccountId =
      getField(row, AD_FIELDS.accountId) || "unknown-account";
    const adType = getField(row, AD_FIELDS.adType) || "未知类型";
    const productKind = normalizeProductKind(adType);
    const identity: CampaignIdentity = {
      advertiserAccountId,
      campaignId,
      campaignName,
      canonicalName: parsed.canonicalName,
      operator: parsed.operator,
      product: parsed.product,
      productLine: parsed.productLine,
      recognized: parsed.recognized,
      adType,
      productKind,
      currency: getField(row, AD_FIELDS.currency) || "USD",
    };
    identities.set(
      `${advertiserAccountId}|${campaignKey(identity)}`,
      identity,
    );
    const uniqueKey = factKey(
      advertiserAccountId,
      campaignId,
      date,
      hour,
      adType,
    );
    const previous = aggregate.get(uniqueKey);
    const current: HourMetric = previous ?? {
      uniqueKey,
      advertiserAccountId,
      date,
      hour,
      campaignId,
      campaignName,
      operator: identity.operator,
      product: identity.product,
      productLine: identity.productLine,
      adType,
      productKind,
      currency: identity.currency,
      impressions: 0,
      viewableImpressions: 0,
      clicks: 0,
      spend: 0,
      purchases: 0,
      adSales: 0,
      sourceRows: 0,
      maturityStatus: maturityStatus(date, productKind, timezone),
      firstImportedAt: importedAt,
      lastImportedAt: importedAt,
    };
    current.impressions += parseNumber(getField(row, AD_FIELDS.impressions));
    current.viewableImpressions += parseNumber(
      getField(row, AD_FIELDS.viewableImpressions),
    );
    current.clicks += parseNumber(getField(row, AD_FIELDS.clicks));
    current.spend += parseNumber(getField(row, AD_FIELDS.spend));
    current.purchases += parseNumber(getField(row, AD_FIELDS.purchases));
    current.adSales += parseNumber(getField(row, AD_FIELDS.adSales));
    current.sourceRows += 1;
    aggregate.set(uniqueKey, current);
  }

  if (requirePeriod && (!period.start || !period.end)) {
    throw new Error(
      "广告小时报告缺少可识别的“日期/报告日期/统计日期”字段。系统不会从文件名推断日期。",
    );
  }

  return {
    hourly: [...aggregate.values()].sort(
      (a, b) =>
        a.date.localeCompare(b.date) ||
        a.hour - b.hour ||
        a.campaignName.localeCompare(b.campaignName),
    ),
    identities,
    rows: rows.length,
    rejected,
    period,
    duplicateRowsCollapsed: Math.max(0, acceptedRows - aggregate.size),
  };
}

async function yieldToBrowser(): Promise<void> {
  await new Promise<void>((resolve) => {
    if (typeof requestAnimationFrame === "function") {
      requestAnimationFrame(() => resolve());
    } else {
      setTimeout(resolve, 0);
    }
  });
}

export async function importAdRowsResponsive(
  rows: CsvRow[],
  timezone: string,
  importedAt: string,
  onProgress?: (progress: number) => void,
): Promise<ImportedAd> {
  const aggregate = new Map<string, HourMetric>();
  const identities = new Map<string, CampaignIdentity>();
  const chunkSize = 4_000;
  let rejected = 0;
  let accepted = 0;
  let start: string | undefined;
  let end: string | undefined;
  let source: ReportPeriod["source"] = "none";
  let sourceField: string | undefined;

  for (let offset = 0; offset < rows.length; offset += chunkSize) {
    const chunk = rows.slice(offset, offset + chunkSize);
    const imported = importAdRows(
      chunk,
      timezone,
      importedAt,
      false,
    );
    rejected += imported.rejected;
    accepted += chunk.length - imported.rejected;
    for (const [key, identity] of imported.identities) {
      identities.set(key, identity);
    }
    for (const fact of imported.hourly) {
      const previous = aggregate.get(fact.uniqueKey);
      if (!previous) {
        aggregate.set(fact.uniqueKey, fact);
      } else {
        previous.impressions += fact.impressions;
        previous.viewableImpressions += fact.viewableImpressions;
        previous.clicks += fact.clicks;
        previous.spend += fact.spend;
        previous.purchases += fact.purchases;
        previous.adSales += fact.adSales;
        previous.sourceRows += fact.sourceRows;
      }
    }
    if (imported.period.start) {
      start =
        start === undefined || imported.period.start < start
          ? imported.period.start
          : start;
    }
    if (imported.period.end) {
      end =
        end === undefined || imported.period.end > end
          ? imported.period.end
          : end;
    }
    if (source === "none" && imported.period.source !== "none") {
      source = imported.period.source;
      sourceField = imported.period.sourceField;
    }
    onProgress?.(Math.min(1, (offset + chunk.length) / rows.length));
    await yieldToBrowser();
  }

  if (!start || !end) {
    throw new Error(
      "广告小时报告缺少可识别的“日期/报告日期/统计日期”字段。系统不会从文件名推断日期。",
    );
  }
  return {
    hourly: [...aggregate.values()].sort(
      (a, b) =>
        a.date.localeCompare(b.date) ||
        a.hour - b.hour ||
        a.campaignName.localeCompare(b.campaignName),
    ),
    identities,
    rows: rows.length,
    rejected,
    period: {
      start,
      end,
      source,
      sourceField,
      matchStatus: "unknown",
    },
    duplicateRowsCollapsed: Math.max(0, accepted - aggregate.size),
  };
}

export function importTibRows(rows: CsvRow[]): ImportedTib {
  const byName = new Map<string, Partial<CampaignMeta>>();
  let rejected = 0;
  const period = extractReportPeriod(rows);
  for (const row of rows) {
    const campaignName = getField(row, TIB_FIELDS.campaignName);
    if (!campaignName) {
      rejected += 1;
      continue;
    }
    const canonicalName = canonicalText(campaignName);
    byName.set(canonicalName.toLowerCase(), {
      status: getField(row, TIB_FIELDS.status),
      adType: getField(row, TIB_FIELDS.adType),
      targeting: getField(row, TIB_FIELDS.targeting),
      biddingStrategy: getField(row, TIB_FIELDS.biddingStrategy),
      budget: parseNumber(getField(row, TIB_FIELDS.budget)),
      tib: parseTib(getField(row, TIB_FIELDS.tib)),
      tibPeriod: period,
    });
  }
  return { byName, rows: rows.length, rejected, period };
}

function periodMatch(ad: ReportPeriod, tib: ReportPeriod): PeriodMatchStatus {
  if (!tib.start || !tib.end || !ad.start || !ad.end) return "unknown";
  if (ad.start === tib.start && ad.end === tib.end) return "exact";
  if (tib.end < ad.start || tib.start > ad.end) return "mismatch";
  return "partial";
}

function metricsDiffer(a: HourMetric, b: HourMetric): boolean {
  return (
    a.impressions !== b.impressions ||
    a.clicks !== b.clicks ||
    Math.abs(a.spend - b.spend) > 0.00001 ||
    a.purchases !== b.purchases ||
    Math.abs(a.adSales - b.adSales) > 0.00001
  );
}

export function mergeHourlyFacts(
  existing: HourMetric[],
  incoming: HourMetric[],
  timezone: string,
  importedAt: string,
): MergeStats {
  const current = new Map<string, HourMetric>();
  for (const fact of existing) {
    const status = maturityStatus(fact.date, fact.productKind, timezone);
    current.set(fact.uniqueKey, {
      ...fact,
      maturityStatus: status,
      lockedAt:
        status === "mature" ? fact.lockedAt ?? importedAt : fact.lockedAt,
    });
  }
  const changes: BackfillChange[] = [];
  const conflicts: LockedConflict[] = [];
  let inserted = 0;
  let updated = 0;
  let lockedSkipped = 0;

  for (const next of incoming) {
    const previous = current.get(next.uniqueKey);
    if (!previous) {
      inserted += 1;
      current.set(next.uniqueKey, {
        ...next,
        lockedAt:
          next.maturityStatus === "mature" ? importedAt : next.lockedAt,
      });
      continue;
    }
    const locked =
      previous.maturityStatus === "mature" &&
      !previous.manuallyUnlocked &&
      Boolean(previous.lockedAt);
    if (locked) {
      lockedSkipped += 1;
      if (metricsDiffer(previous, next)) {
        const id = `${next.uniqueKey}|${importedAt}`;
        conflicts.push({
          id,
          uniqueKey: next.uniqueKey,
          campaignId: next.campaignId,
          date: next.date,
          hour: next.hour,
          lockedPurchases: previous.purchases,
          incomingPurchases: next.purchases,
          lockedSales: previous.adSales,
          incomingSales: next.adSales,
          importedAt,
          status: "unresolved",
          incomingFact: next,
        });
      }
      continue;
    }
    if (
      previous.purchases !== next.purchases ||
      Math.abs(previous.adSales - next.adSales) > 0.00001
    ) {
      changes.push({
        id: `${next.uniqueKey}|${importedAt}`,
        uniqueKey: next.uniqueKey,
        campaignId: next.campaignId,
        date: next.date,
        hour: next.hour,
        previousPurchases: previous.purchases,
        incomingPurchases: next.purchases,
        previousSales: previous.adSales,
        incomingSales: next.adSales,
        importedAt,
      });
    }
    updated += 1;
    current.set(next.uniqueKey, {
      ...next,
      firstImportedAt: previous.firstImportedAt,
      lastImportedAt: importedAt,
      manuallyUnlocked: false,
      lockedAt:
        next.maturityStatus === "mature"
          ? previous.lockedAt ?? importedAt
          : undefined,
    });
  }

  return {
    facts: [...current.values()].sort(
      (a, b) => a.date.localeCompare(b.date) || a.hour - b.hour,
    ),
    changes,
    conflicts,
    inserted,
    updated,
    lockedSkipped,
  };
}

async function hashFile(file: File): Promise<string> {
  const bytes = await file.arrayBuffer();
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(digest)]
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}

function buildQuality(
  ad: ImportedAd,
  tib: ImportedTib,
  campaigns: CampaignMeta[],
  facts: HourMetric[],
): DataQuality {
  const currencies = [...new Set(facts.map((row) => row.currency).filter(Boolean))];
  const match = periodMatch(ad.period, tib.period);
  const warnings: string[] = [];
  if (currencies.length > 1) {
    warnings.push("检测到多币种；当前版本不会执行汇率换算。");
  }
  if (ad.rejected) {
    warnings.push(`${ad.rejected}行因日期、小时或活动名称缺失被拒绝。`);
  }
  if (campaigns.some((row) => !row.recognized)) {
    warnings.push("部分广告名称未按“运营名-产品代码”格式识别。");
  }
  if (campaigns.some((row) => !row.tibMatched)) {
    warnings.push("部分广告活动未在TIB报告中精确匹配。");
  }
  if (match !== "exact") {
    warnings.push(
      match === "unknown"
        ? "TIB统计周期未知：活动开始/结束日期未被当作报表周期，正式四象限已拦截。"
        : `TIB与本次小时报告周期${match === "partial" ? "仅部分重叠" : "错位"}，正式四象限已拦截。`,
    );
  }
  const matureFacts = facts.filter((row) => row.maturityStatus === "mature").length;
  return {
    adRows: ad.rows,
    rejectedAdRows: ad.rejected,
    tibRows: tib.rows,
    rejectedTibRows: tib.rejected,
    campaignCount: campaigns.length,
    recognizedCampaignCount: campaigns.filter((row) => row.recognized).length,
    tibMatchedCampaignCount: campaigns.filter((row) => row.tibMatched).length,
    currencies,
    activeDateCount: new Set(facts.map((row) => row.date)).size,
    adPeriod: ad.period,
    tibPeriod: tib.period,
    tibPeriodMatch: match,
    duplicateRowsCollapsed: ad.duplicateRowsCollapsed,
    matureFactShare: facts.length ? matureFacts / facts.length : 0,
    warnings,
  };
}

export async function importAndMergeProject(
  adFile: File,
  tibFile: File,
  config: ProjectConfig,
  existing?: DashboardProject,
  onProgress?: (phase: string, progress: number) => void,
): Promise<DashboardProject> {
  const importedAt = new Date().toISOString();
  const [adRows, tibRows, adFileHash, tibFileHash] = await Promise.all([
    parseCsvFile(adFile, (progress) => onProgress?.("解析广告小时报告", progress)),
    parseCsvFile(tibFile, (progress) => onProgress?.("解析TIB活动报告", progress)),
    hashFile(adFile),
    hashFile(tibFile),
  ]);
  onProgress?.("识别表内日期并聚合唯一键", 0);
  const ad = await importAdRowsResponsive(
    adRows,
    config.accountTimezone,
    importedAt,
    (progress) => onProgress?.("分批聚合日期×小时记录", progress),
  );
  const tib = importTibRows(tibRows);
  onProgress?.("合并历史记录与归因回填", 0.3);
  await yieldToBrowser();
  const merged = mergeHourlyFacts(
    existing?.hourly ?? [],
    ad.hourly,
    config.accountTimezone,
    importedAt,
  );

  const identities = new Map<string, CampaignIdentity>();
  for (const campaign of existing?.campaigns ?? []) {
    identities.set(
      `${campaign.advertiserAccountId}|${campaign.campaignId}`,
      campaign,
    );
  }
  for (const identity of ad.identities.values()) {
    identities.set(
      `${identity.advertiserAccountId}|${identity.campaignId}`,
      identity,
    );
  }
  const previousMeta = new Map(
    (existing?.campaigns ?? []).map((campaign) => [
      `${campaign.advertiserAccountId}|${campaign.campaignId}`,
      campaign,
    ]),
  );
  const campaigns: CampaignMeta[] = [...identities.entries()].map(
    ([identityKey, identity]) => {
      const matched = tib.byName.get(identity.canonicalName.toLowerCase());
      const previous = previousMeta.get(identityKey);
      return {
        ...identity,
        ...(previous ?? {}),
        ...identity,
        ...(matched ?? {}),
        tibMatched: Boolean(matched ?? previous?.tibMatched),
        tibPeriod: matched?.tibPeriod ??
          previous?.tibPeriod ?? { source: "none", matchStatus: "unknown" },
        tibImportedAt: matched ? importedAt : previous?.tibImportedAt,
      };
    },
  );
  const match = periodMatch(ad.period, tib.period);
  for (const campaign of campaigns) {
    campaign.tibPeriod = {
      ...campaign.tibPeriod,
      matchStatus: match,
    };
  }

  const batchId = `${importedAt}|${adFileHash.slice(0, 12)}`;
  const batch: ImportBatch = {
    batchId,
    importedAt,
    adFileName: adFile.name,
    tibFileName: tibFile.name,
    adFileHash,
    tibFileHash,
    adPeriod: ad.period,
    tibPeriod: tib.period,
    inserted: merged.inserted,
    updated: merged.updated,
    lockedSkipped: merged.lockedSkipped,
    conflicts: merged.conflicts.length,
    rejectedAdRows: ad.rejected,
    rejectedTibRows: tib.rejected,
  };
  const quality = buildQuality(ad, tib, campaigns, merged.facts);
  onProgress?.("准备写入本地历史库", 0.9);
  await yieldToBrowser();
  return {
    schemaVersion: 2,
    createdAt: existing?.createdAt ?? importedAt,
    updatedAt: importedAt,
    sourceNames: { ad: adFile.name, tib: tibFile.name },
    config,
    campaigns,
    hourly: merged.facts,
    importBatches: [...(existing?.importBatches ?? []), batch],
    backfillChanges: [
      ...(existing?.backfillChanges ?? []),
      ...merged.changes,
    ],
    lockedConflicts: [
      ...(existing?.lockedConflicts ?? []),
      ...merged.conflicts,
    ],
    aiReviews: existing?.aiReviews ?? [],
    quality,
  };
}

export function acceptLockedConflict(
  project: DashboardProject,
  conflictId: string,
): DashboardProject {
  const conflict = project.lockedConflicts.find((item) => item.id === conflictId);
  if (!conflict || conflict.status !== "unresolved") return project;
  const now = new Date().toISOString();
  return {
    ...project,
    updatedAt: now,
    hourly: project.hourly.map((fact) =>
      fact.uniqueKey === conflict.uniqueKey
        ? {
            ...conflict.incomingFact,
            firstImportedAt: fact.firstImportedAt,
            lastImportedAt: now,
            lockedAt: now,
            manuallyUnlocked: false,
          }
        : fact,
    ),
    lockedConflicts: project.lockedConflicts.map((item) =>
      item.id === conflictId
        ? { ...item, status: "acceptedIncoming" }
        : item,
    ),
  };
}

export function keepLockedConflict(
  project: DashboardProject,
  conflictId: string,
): DashboardProject {
  return {
    ...project,
    lockedConflicts: project.lockedConflicts.map((item) =>
      item.id === conflictId ? { ...item, status: "keptLocked" } : item,
    ),
  };
}
