export const APP_VERSION = "0.1.0" as const;
export const SCHEMA_VERSION = "1.0.0" as const;
export const FOOTWEAR_PROMPT_VERSION = "footwear-v4.1.0" as const;
export const JUDGMENT_STANDARDS_VERSION = "footwear-judgment-v2" as const;

export const PRIMARY_DOMAINS = [
  "clothing_shoes_jewelry",
  "sports_outdoors",
  "home_kitchen",
  "patio_lawn_garden",
  "tools_home_improvement",
  "musical_instruments",
  "industrial_scientific",
  "automotive",
  "electronics",
  "baby_products",
  "arts_crafts_sewing",
  "health_household",
  "toys_games",
  "video_games",
  "grocery_gourmet_food",
  "office_products",
  "pet_supplies",
  "others"
] as const;

export type PrimaryDomain = (typeof PRIMARY_DOMAINS)[number];
export type EvidenceType = "explicit" | "page_validated" | "inferred";
export type ConfidenceLevel = "high" | "medium" | "low";
export type PromptMode = "blind" | "aided" | "diagnostic";
export type RunStatus = "draft" | "ready" | "running" | "stopping" | "stopped" | "completed" | "failed";
export type TurnStatus = "pending" | "running" | "completed" | "failed" | "skipped";

export const RUN_PRESETS = ["smoke", "calibration", "full"] as const;
export const PROMPT_LANGUAGES = ["en-US", "zh-CN"] as const;
export const SESSION_POLICIES = ["fresh", "shared_sequence"] as const;
export const TEST_ROLES = [
  "baseline",
  "positive_control",
  "negative_control",
  "retail_probe",
  "aided_recognition",
  "diagnostic"
] as const;
export const EXPECTED_MATCHES = ["eligible", "ineligible", "neutral", "diagnostic_only"] as const;
export const PROMPT_GENERATORS = ["deterministic", "deepseek_rewrite", "developer_edit"] as const;

export type RunPreset = (typeof RUN_PRESETS)[number];
export type PromptLanguage = (typeof PROMPT_LANGUAGES)[number];
export type SessionPolicy = (typeof SESSION_POLICIES)[number];
export type TestRole = (typeof TEST_ROLES)[number];
export type ExpectedMatch = (typeof EXPECTED_MATCHES)[number];
export type PromptGeneratedBy = (typeof PROMPT_GENERATORS)[number];
export type PromptExpression = "direct" | "natural_language" | "task" | "comparison" | "conflict";

export interface EvidenceFact {
  id: string;
  field: string;
  value: string | string[];
  evidenceType: EvidenceType;
  sourceSection: "title" | "brand" | "breadcrumb" | "bullets" | "specification" | "a_plus" | "review_summary" | "qa" | "retail";
  sourceText: string;
  confidence: ConfidenceLevel;
  capturedAt: string;
}

export interface IntentProfile {
  primary_domain: PrimaryDomain;
  secondary_domain: string[];
  product_type: string[];
  audience_intent: string[];
  function_intent: string[];
  capability_intent: string[];
  event_intent: string[];
  location_intent: string[];
  body_need_intent: string[];
  time_intent: string[];
  substitute_intent: string[];
  complement_intent: string[];
  latent_task: string;
  intent_stage: "exploration" | "consideration" | "high_intent" | "brand_harvest" | "unknown";
  evidence_type: EvidenceType[];
  confidence_level: ConfidenceLevel;
  intent_cluster: string;
  routing_action: "cluster_route" | "listing_gap_review" | "ambiguity_review" | "semantic_negative_candidate" | "performance_observation";
}

export interface ProductSnapshot {
  id?: string;
  asin: string;
  /** ASIN parsed from the URL before Amazon resolves a parent/child variation. */
  requestedAsin?: string;
  /** Selected buyable child ASIN after the product page has resolved. */
  resolvedAsin?: string;
  /** Parent and child ASINs that identify the same tested product family. */
  asinAliases?: string[];
  url: string;
  marketplace: string;
  title: string;
  brand: string;
  breadcrumb: string[];
  bullets: string[];
  specifications: Record<string, string>;
  aPlusText: string;
  reviewSummary: string;
  qaText: string;
  stableFacts: EvidenceFact[];
  volatileFacts: EvidenceFact[];
  intentProfile: IntentProfile;
  accountLabel: string;
  selectorVersion: string;
  schemaVersion: typeof SCHEMA_VERSION;
  capturedAt: string;
}

/** Immutable test meaning. DeepSeek may rewrite promptText but must preserve this metadata. */
export interface PromptCaseDefinition {
  templateId: string;
  enabled: boolean;
  slot: string;
  mode: PromptMode;
  expression: PromptExpression;
  promptText: string;
  testRole: TestRole;
  scoreEligible: boolean;
  hypothesis: string;
  expectedMatch: ExpectedMatch;
  evidenceFactIds: string[];
  requiredTerms: string[];
  /** Human-readable, developer-visible rules used to judge the Alexa response. */
  judgmentCriteria: string[];
  promptVersion: string;
  sessionPolicy: SessionPolicy;
  sessionGroup?: string;
  generatedBy: PromptGeneratedBy;
  originalPromptText?: string;
  rewriteReason?: string;
}

export interface PromptCase extends PromptCaseDefinition {
  id: string;
  repeatIndex: number;
  sequence: number;
  status: TurnStatus;
  revision: number;
  editable: boolean;
  updatedAt?: string;
}

/** A generated, reviewable question plan before execution is locked. */
export interface QuestionPlan {
  runId: string;
  schemaVersion: typeof SCHEMA_VERSION;
  promptVersion: string;
  preset: RunPreset;
  promptLanguage: PromptLanguage;
  sessionPolicy: SessionPolicy;
  revision: number;
  editable: boolean;
  prompts: PromptCase[];
  approvedAt?: string;
  lockedAt?: string;
  updatedAt: string;
}

/** Shape returned by deterministic generation or DeepSeek before repeats are expanded. */
export interface GeneratedPromptPlan {
  schemaVersion: typeof SCHEMA_VERSION;
  promptVersion: string;
  preset: RunPreset;
  promptLanguage: PromptLanguage;
  sessionPolicy: SessionPolicy;
  prompts: PromptCaseDefinition[];
}

export interface UpdatePromptCaseRequest {
  expectedRevision: number;
  changeReason: string;
  enabled?: boolean;
  promptText?: string;
  hypothesis?: string;
  testRole?: TestRole;
  scoreEligible?: boolean;
  expectedMatch?: ExpectedMatch;
  evidenceFactIds?: string[];
  requiredTerms?: string[];
  judgmentCriteria?: string[];
  sessionPolicy?: SessionPolicy;
  sessionGroup?: string | null;
}

export interface ApproveQuestionPlanRequest {
  expectedRevision: number;
  note?: string;
}

export interface RecommendationItem {
  asin: string;
  title: string;
  brand: string;
  rank: number;
  url: string;
  priceText: string;
  ratingText: string;
  reviewCountText: string;
  sponsored: boolean;
  deliveryText: string;
  evidenceText: string;
}

export interface ConversationTurn {
  id?: string;
  runId: string;
  promptCaseId: string;
  promptText: string;
  responseText: string;
  recommendations: RecommendationItem[];
  judgment?: TurnJudgment;
  judgmentVersion?: string;
  screenshotDataUrl?: string;
  screenshotPath?: string;
  screenshotError?: string;
  extractionDiagnostics?: {
    responseChars: number;
    domLinkCount: number;
    asinCount: number;
    textOnlyCount: number;
  };
  selectorVersion: string;
  status: TurnStatus;
  errorCode?: string;
  errorMessage?: string;
  capturedAt: string;
}

export interface ScoreDimensions {
  inclusion: number;
  rank: number;
  comparison: number;
  evidence: number;
  consistency: number;
}

export interface ScoreSnapshot {
  total: number | null;
  grade: "strong" | "medium" | "weak" | "insufficient";
  dimensions: ScoreDimensions;
  sampleSize: number;
  completedPromptGroups: number;
  expectedPromptGroups: number;
  confidence: { lower: number; upper: number } | null;
  warnings: string[];
  formulaVersion: "2.1.0";
  standardsVersion: string;
  judgments: TurnJudgment[];
  probes: {
    baseline: ProbeMetric;
    negativeControl: ProbeMetric;
    retailProbe: ProbeMetric;
    aidedRecognition: ProbeMetric;
    diagnostic: ProbeMetric;
  };
  calculatedAt: string;
}

export type JudgmentOutcome = "pass" | "fail" | "observe" | "not_applicable" | "insufficient_evidence";

export interface TurnJudgment {
  turnId?: string;
  promptCaseId: string;
  testRole: TestRole;
  scoreEligible: boolean;
  expectedMatch: ExpectedMatch;
  ownIncluded: boolean;
  ownRank: number | null;
  constraintOutcome: JudgmentOutcome;
  evidenceOutcome: JudgmentOutcome;
  reasonCodes: string[];
}

export interface ProbeMetric {
  sampleSize: number;
  includedCount: number;
  inclusionRate: number;
  meanRankScore?: number;
  passCount?: number;
  passRate?: number;
}

export type DiagnosisCategory =
  | "recall_gap"
  | "intent_evidence_gap"
  | "attribute_conflict"
  | "retail_competition"
  | "product_recognition"
  | "personalization_noise"
  | "unknown";

export interface Diagnosis {
  category: DiagnosisCategory;
  severity: "high" | "medium" | "low";
  observation: string;
  supportingTurnIds: string[];
  evidenceFactIds: string[];
  inference: string;
  recommendedAction: string;
}

export interface ExperimentRun {
  id: string;
  productSnapshotId: string;
  status: RunStatus;
  accountLabel: string;
  runSeed: string;
  preset: RunPreset;
  promptLanguage: PromptLanguage;
  sessionPolicy: SessionPolicy;
  promptVersion: string;
  questionPlanRevision: number;
  questionPlanEditable: boolean;
  questionPlanApprovedAt?: string;
  questionPlanLockedAt?: string;
  promptCount: number;
  repetitions: number;
  totalTurns: number;
  completedTurns: number;
  promptCases: PromptCase[];
  score: ScoreSnapshot | null;
  diagnoses: Diagnosis[];
  stopReason?: string;
  createdAt: string;
  updatedAt: string;
}

export interface CreateRunRequest {
  productSnapshotId: string;
  accountLabel: string;
  preset?: RunPreset;
  promptLanguage?: PromptLanguage;
  sessionPolicy?: SessionPolicy;
  promptCount?: number;
  repetitions?: number;
  runSeed?: string;
}

export type AuditActor = "system" | "developer" | "deepseek" | "extension";

export interface RunAuditEvent {
  id: string;
  runId: string;
  type: string;
  actor: AuditActor;
  promptCaseId?: string;
  payload: unknown;
  createdAt: string;
}

/** Backward-friendly public name for persisted run events. */
export type RunEvent = RunAuditEvent;

export interface QuestionPlanAuditPayload {
  action: "generated" | "deepseek_rewritten" | "developer_updated" | "approved" | "locked";
  fromRevision?: number;
  toRevision: number;
  before?: Partial<PromptCaseDefinition>;
  after?: Partial<PromptCaseDefinition>;
  changeReason?: string;
}

export interface ApiError {
  statusCode: number;
  code: string;
  message: string;
  details?: unknown;
}

export interface RunReport {
  run: ExperimentRun;
  product: ProductSnapshot;
  turns: ConversationTurn[];
  score: ScoreSnapshot | null;
  diagnoses: Diagnosis[];
  auditEvents: RunAuditEvent[];
}
