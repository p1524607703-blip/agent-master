export type MaturityStatus = "processing" | "backfilling" | "mature";
export type DataViewMode = "observation" | "decision";
export type ProductKind = "SP" | "SB" | "SD" | "OTHER";
export type PeriodMatchStatus =
  | "exact"
  | "partial"
  | "mismatch"
  | "unknown";
export type SampleSignal = "sufficient" | "isolated" | "insufficient";
export type EfficiencyClass =
  | "efficient"
  | "inefficient"
  | "nearBaseline"
  | "insufficient";
export type TibBand = "low" | "middle" | "high" | "unknown";
export type RawQuadrant =
  | "lowTibHighRoas"
  | "lowTibLowRoas"
  | "highTibHighRoas"
  | "highTibLowRoas"
  | "conditional"
  | "blocked";
export type CandidateLevel =
  | "正式候选"
  | "条件候选"
  | "继续观察"
  | "暂不进入TIB优化";

export interface Thresholds {
  minClicks: number;
  minPurchases: number;
  minActiveDays: number;
  efficiencyDelta: number;
  minMatureDays: number;
  minClickDays: number;
  minPurchaseDays: number;
  maxOrderConcentration: number;
}

export interface ProjectConfig {
  accountTimezone: string;
  thresholds: Thresholds;
  productRoasTargets: Record<string, number>;
}

export interface ReportPeriod {
  start?: string;
  end?: string;
  source:
    | "dateColumn"
    | "reportDateColumn"
    | "statisticsDateColumn"
    | "explicitRangeColumn"
    | "none";
  sourceField?: string;
  matchStatus: PeriodMatchStatus;
}

export interface CampaignIdentity {
  advertiserAccountId: string;
  campaignId: string;
  campaignName: string;
  canonicalName: string;
  operator: string;
  product: string;
  productLine: string;
  recognized: boolean;
  adType: string;
  productKind: ProductKind;
  currency: string;
}

export interface CampaignMeta extends CampaignIdentity {
  status?: string;
  targeting?: string;
  biddingStrategy?: string;
  budget?: number;
  tib?: number;
  tibMatched: boolean;
  tibPeriod: ReportPeriod;
  tibImportedAt?: string;
}

export interface HourMetric {
  uniqueKey: string;
  advertiserAccountId: string;
  date: string;
  hour: number;
  campaignId: string;
  campaignName: string;
  operator: string;
  product: string;
  productLine: string;
  adType: string;
  productKind: ProductKind;
  currency: string;
  impressions: number;
  viewableImpressions: number;
  clicks: number;
  spend: number;
  purchases: number;
  adSales: number;
  sourceRows: number;
  maturityStatus: MaturityStatus;
  firstImportedAt: string;
  lastImportedAt: string;
  lockedAt?: string;
  manuallyUnlocked?: boolean;
}

export interface ImportBatch {
  batchId: string;
  importedAt: string;
  adFileName: string;
  tibFileName: string;
  adFileHash: string;
  tibFileHash: string;
  adPeriod: ReportPeriod;
  tibPeriod: ReportPeriod;
  inserted: number;
  updated: number;
  lockedSkipped: number;
  conflicts: number;
  rejectedAdRows: number;
  rejectedTibRows: number;
}

export interface BackfillChange {
  id: string;
  uniqueKey: string;
  campaignId: string;
  date: string;
  hour: number;
  previousPurchases: number;
  incomingPurchases: number;
  previousSales: number;
  incomingSales: number;
  importedAt: string;
}

export interface LockedConflict {
  id: string;
  uniqueKey: string;
  campaignId: string;
  date: string;
  hour: number;
  lockedPurchases: number;
  incomingPurchases: number;
  lockedSales: number;
  incomingSales: number;
  importedAt: string;
  status: "unresolved" | "acceptedIncoming" | "keptLocked";
  incomingFact: HourMetric;
}

export interface HermesUsage {
  promptTokens?: number;
  completionTokens?: number;
  totalTokens?: number;
}

export interface HermesReviewV1 {
  campaignId: string;
  finalQuadrant: string;
  candidateLevel: CandidateLevel;
  actionEligible: boolean;
  reasons: string[];
  referenceCampaignIds: string[];
  risks: string[];
  nextAnalysis: string[];
  reviewedAt: string;
}

export interface AiReviewAudit {
  campaignId: string;
  inputHash: string;
  promptVersion: string;
  schemaVersion: "HermesReviewV1";
  hermesSessionId?: string;
  model: string;
  durationMs: number;
  usage?: HermesUsage;
  status: "success" | "rulesOnly" | "error" | "imported";
  errorCode?: string;
  errorMessage?: string;
  review?: HermesReviewV1;
}

export interface DataQuality {
  adRows: number;
  rejectedAdRows: number;
  tibRows: number;
  rejectedTibRows: number;
  campaignCount: number;
  recognizedCampaignCount: number;
  tibMatchedCampaignCount: number;
  currencies: string[];
  activeDateCount: number;
  adPeriod: ReportPeriod;
  tibPeriod: ReportPeriod;
  tibPeriodMatch: PeriodMatchStatus;
  duplicateRowsCollapsed: number;
  matureFactShare: number;
  warnings: string[];
}

export interface DashboardProject {
  schemaVersion: 2;
  createdAt: string;
  updatedAt: string;
  sourceNames: {
    ad: string;
    tib: string;
  };
  config: ProjectConfig;
  campaigns: CampaignMeta[];
  hourly: HourMetric[];
  importBatches: ImportBatch[];
  backfillChanges: BackfillChange[];
  lockedConflicts: LockedConflict[];
  aiReviews: AiReviewAudit[];
  quality: DataQuality;
}

export interface FilterState {
  reportStart: string;
  reportEnd: string;
  operator: string;
  productLine: string;
  adType: string;
  campaignId: string;
}

export interface ObservationWindow {
  mode: "observation";
  start: string;
  end: string;
  label: string;
}

export interface DecisionWindow {
  mode: "decision";
  productKind: ProductKind;
  start: string;
  end: string;
  label: string;
}

export interface StabilityMetrics {
  calendarDays: number;
  matureDays: number;
  activeDays: number;
  clickDays: number;
  purchaseDays: number;
  maxDailyOrderConcentration: number | null;
  matureFactShare: number;
}

export interface HourSummary {
  hour: number;
  impressions: number;
  clicks: number;
  spend: number;
  purchases: number;
  adSales: number;
  roas: number | null;
  acos: number | null;
  cpc: number | null;
  cvr: number | null;
  activeDays: number;
  signal: SampleSignal;
  classification: EfficiencyClass;
}

export interface SummaryMetrics extends StabilityMetrics {
  impressions: number;
  clicks: number;
  spend: number;
  purchases: number;
  adSales: number;
  roas: number | null;
  acos: number | null;
  cpc: number | null;
  cvr: number | null;
  weightedTib: number | null;
}

export interface TimeWindow {
  start: number;
  end: number;
  classification: EfficiencyClass;
  signal: SampleSignal;
  isolated: boolean;
  label: string;
}

export interface ProductLineRow extends SummaryMetrics {
  operator: string;
  product: string;
  productLine: string;
  campaignCount: number;
  tibCoverage: number;
  targetRoas: number | null;
  eligibleCampaigns: number;
  blockedCampaigns: number;
  windows: TimeWindow[];
}

export interface CandidateGate {
  key: string;
  label: string;
  passed: boolean;
  value: string;
}

export interface CampaignRow extends CampaignMeta, SummaryMetrics {
  tibBand: TibBand;
  rawQuadrant: RawQuadrant;
  candidateLevel: CandidateLevel;
  actionEligible: boolean;
  gates: CandidateGate[];
  medianLastActiveHour: number | null;
  lastActiveDistribution: Record<string, number>;
  activeHourCount: number;
  spendShare: number;
  purchaseShare: number;
  sameDayHandoffDays: number;
  flowHandoff: boolean;
  targetRoas: number | null;
  periodExact: boolean;
}
