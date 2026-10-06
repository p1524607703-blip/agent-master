<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import type {
  ConversationTurn,
  ProbeMetric,
  PromptCase,
  RecommendationItem,
  RunAuditEvent,
  RunReport,
  TestRole,
  TurnJudgment
} from "@alexa-auditor/contracts";
import DimensionChart from "./components/DimensionChart.vue";

type Standards = {
  standardsVersion?: string;
  formulaVersion?: string;
  scope?: string;
  developerCriteria?: { executable?: boolean; rule?: string };
  mainScoreEligibility?: Record<string, unknown>;
  roles?: Record<string, string>;
  constraintOutcomes?: Record<string, string>;
  evidenceOutcomes?: Record<string, string>;
  evidenceMatchingRule?: Record<string, string>;
  reasonCodes?: Record<string, string>;
  probeMetrics?: Record<string, string>;
  dimensions?: Record<string, { weight?: number; rule?: string }>;
  precisionGate?: Record<string, unknown>;
};

const report = ref<RunReport | null>(null);
const standards = ref<Standards | null>(null);
const loading = ref(true);
const error = ref("");
const runId = location.pathname.match(/\/reports\/([^/?#]+)/)?.[1] || new URLSearchParams(location.search).get("run") || "";
const baseUrl = location.port === "4319" ? "http://127.0.0.1:4318" : "";

const promptById = computed(() => new Map(report.value?.run.promptCases.map((item) => [item.id, item]) || []));
const judgmentByPromptId = computed(() => {
  const result = new Map<string, TurnJudgment>();
  report.value?.score?.judgments.forEach((item) => result.set(item.promptCaseId, item));
  report.value?.turns.forEach((turn) => {
    if (turn.judgment && !result.has(turn.promptCaseId)) result.set(turn.promptCaseId, turn.judgment);
  });
  return result;
});
const ownAsins = computed(() => new Set([
  report.value?.product.asin,
  report.value?.product.requestedAsin,
  report.value?.product.resolvedAsin,
  ...(report.value?.product.asinAliases || [])
].map(normalizeAsin).filter(Boolean)));
const asinLabels = computed(() => [...ownAsins.value]);

function normalizeAsin(value?: string) {
  return String(value || "").trim().toUpperCase();
}

function normalizeTitle(value?: string) {
  return String(value || "").normalize("NFKC").toLowerCase().replace(/[^a-z0-9\p{L}]+/gu, " ").replace(/\s+/g, " ").trim();
}

function isOwnProduct(item: RecommendationItem) {
  if (normalizeAsin(item.asin) && ownAsins.value.has(normalizeAsin(item.asin))) return true;
  const product = report.value?.product;
  if (!product) return false;
  const itemTitle = normalizeTitle(item.title);
  const brand = normalizeTitle(product.brand);
  if (!itemTitle || !brand || !itemTitle.includes(brand)) return false;
  const brandTokens = new Set(brand.split(" "));
  const discriminators = normalizeTitle(product.title).split(" ").filter((token) => token.length > 4 && !brandTokens.has(token));
  return discriminators.slice(0, 8).filter((token) => itemTitle.includes(token)).length >= 2;
}

function promptFor(turn: ConversationTurn) {
  return promptById.value.get(turn.promptCaseId);
}

function judgmentFor(turn: ConversationTurn) {
  return judgmentByPromptId.value.get(turn.promptCaseId) || turn.judgment;
}

function ownItem(turn: ConversationTurn) {
  return turn.recommendations.find(isOwnProduct);
}

const mainScoreTurns = computed(() => report.value?.turns.filter((turn) => {
  const prompt = promptFor(turn);
  const judgment = judgmentFor(turn);
  return turn.status === "completed"
    && prompt?.enabled
    && prompt.testRole === "positive_control"
    && prompt.scoreEligible
    && prompt.expectedMatch === "eligible"
    && judgment?.scoreEligible;
}) || []);
const inclusionCount = computed(() => mainScoreTurns.value.filter((turn) => judgmentFor(turn)?.ownIncluded ?? Boolean(ownItem(turn))).length);
const candidateTurns = computed(() => report.value?.turns.filter((turn) => {
  const prompt = promptFor(turn);
  if (turn.status !== "completed" || prompt?.enabled === false) return false;
  return !prompt || ["baseline", "positive_control", "retail_probe"].includes(prompt.testRole);
}) || []);

function recommendationKey(item: RecommendationItem) {
  return normalizeAsin(item.asin) || normalizeTitle(item.title);
}

const progressiveRows = computed(() => {
  const turns = (report.value?.turns || [])
    .filter((turn) => turn.status === "completed" && promptFor(turn)?.sessionPolicy === "shared_sequence")
    .sort((a, b) => (promptFor(a)?.sequence || 0) - (promptFor(b)?.sequence || 0));
  let previous = new Set<string>();
  return turns.map((turn, index) => {
    const prompt = promptFor(turn);
    const current = new Set(turn.recommendations.map(recommendationKey).filter(Boolean));
    const retained = index === 0 ? null : [...current].filter((key) => previous.has(key)).length;
    const retentionRate = index === 0 || previous.size === 0 ? null : round((retained! / previous.size) * 100);
    const own = ownItem(turn);
    const row = {
      step: index + 1,
      prompt: turn.promptText,
      addedConstraint: prompt?.requiredTerms.join(" · ") || "—",
      candidates: current.size,
      retained,
      retentionRate,
      ownIncluded: Boolean(own),
      ownRank: own?.rank ?? null
    };
    previous = current;
    return row;
  });
});

const uniquePromptTemplates = computed(() => {
  const seen = new Set<string>();
  return (report.value?.run.promptCases || []).filter((item) => {
    if (seen.has(item.templateId)) return false;
    seen.add(item.templateId);
    return true;
  }).sort((a, b) => a.sequence - b.sequence);
});

const slotRows = computed(() => {
  const groups = new Map<string, ConversationTurn[]>();
  mainScoreTurns.value.forEach((turn) => {
    const slot = promptFor(turn)?.slot || "unknown";
    groups.set(slot, [...(groups.get(slot) || []), turn]);
  });
  return [...groups.entries()].map(([slot, turns]) => {
    const ranks = turns.map((turn) => judgmentFor(turn)?.ownRank ?? ownItem(turn)?.rank ?? null).filter((rank): rank is number => rank !== null);
    return {
      slot,
      samples: turns.length,
      inclusions: ranks.length,
      inclusionRate: turns.length ? round((ranks.length / turns.length) * 100) : 0,
      averageRank: ranks.length ? round(ranks.reduce((sum, rank) => sum + rank, 0) / ranks.length) : null
    };
  }).sort((a, b) => b.inclusionRate - a.inclusionRate || a.slot.localeCompare(b.slot));
});

const competitorRows = computed(() => {
  const items = new Map<string, { asin: string; title: string; appearances: number; rankTotal: number; price: string; rating: string; delivery: string }>();
  candidateTurns.value.forEach((turn) => turn.recommendations.forEach((item) => {
    if (!item.asin || isOwnProduct(item)) return;
    const current = items.get(item.asin) || { asin: item.asin, title: item.title, appearances: 0, rankTotal: 0, price: "", rating: "", delivery: "" };
    current.appearances += 1;
    current.rankTotal += item.rank;
    current.price ||= item.priceText || "";
    current.rating ||= item.ratingText || "";
    current.delivery ||= item.deliveryText || "";
    items.set(item.asin, current);
  }));
  return [...items.values()].map((item) => ({ ...item, averageRank: round(item.rankTotal / item.appearances) }))
    .sort((a, b) => b.appearances - a.appearances || a.averageRank - b.averageRank).slice(0, 12);
});

const selfReportMismatches = computed(() => {
  const product = report.value?.product;
  if (!product) return [];
  const identities = [...asinLabels.value, product.brand].filter((value) => value.length > 2).map((value) => value.toLowerCase());
  return report.value?.turns.filter((turn) => {
    const mentioned = identities.some((identity) => turn.responseText.toLowerCase().includes(identity));
    return mentioned !== turn.recommendations.some(isOwnProduct);
  }) || [];
});

const probeRows = computed(() => {
  const probes = report.value?.score?.probes;
  if (!probes) return [];
  return [
    probeRow("baseline", "宽泛品类基线", probes.baseline, "只观察自然发现，不进入主分"),
    probeRow("negativeControl", "负向对照", probes.negativeControl, "看不兼容条件下能否正确排除"),
    probeRow("retailProbe", "零售条件探针", probes.retailProbe, "价格、评分、库存和配送只单独观察"),
    probeRow("aidedRecognition", "辅助识别", probes.aidedRecognition, "给出品牌/ASIN后的识别能力"),
    probeRow("diagnostic", "解释诊断", probes.diagnostic, "回答可用率；不奖励候选排名")
  ];
});

function probeRow(key: string, label: string, metric: ProbeMetric, meaning: string) {
  return { key, label, meaning, ...metric };
}

const roleRows = computed(() => {
  const roles: TestRole[] = ["positive_control", "baseline", "negative_control", "retail_probe", "aided_recognition", "diagnostic"];
  return roles.map((role) => {
    const templates = uniquePromptTemplates.value.filter((item) => item.enabled && item.testRole === role);
    const turns = report.value?.turns.filter((turn) => promptFor(turn)?.enabled && promptFor(turn)?.testRole === role && turn.status === "completed") || [];
    const judgments = turns.map(judgmentFor).filter((item): item is TurnJudgment => Boolean(item));
    return {
      role,
      label: roleLabel(role),
      scope: role === "positive_control" ? "主指数候选（仍须证据对齐）" : "隔离探针，不计主分",
      templates: templates.length,
      turns: turns.length,
      inclusions: judgments.filter((item) => item.ownIncluded).length,
      passes: judgments.filter((item) => item.constraintOutcome === "pass").length
    };
  }).filter((item) => item.templates || item.turns);
});

const judgmentRows = computed(() => (report.value?.turns || []).map((turn, index) => {
  const prompt = promptFor(turn);
  const judgment = judgmentFor(turn);
  const own = ownItem(turn);
  return {
    index: index + 1,
    turn,
    prompt,
    judgment,
    role: prompt?.testRole || judgment?.testRole || "baseline",
    ownIncluded: judgment?.ownIncluded ?? Boolean(own),
    ownRank: judgment?.ownRank ?? own?.rank ?? null,
    constraintOutcome: judgment?.constraintOutcome || "insufficient_evidence",
    evidenceOutcome: judgment?.evidenceOutcome || "insufficient_evidence",
    reasonCodes: judgment?.reasonCodes || [],
    mainScore: Boolean(judgment?.scoreEligible && prompt?.testRole === "positive_control")
  };
}));

const auditEvents = computed(() => [...(report.value?.auditEvents || [])].reverse());
const scoringDimensionRows = computed(() => Object.entries(standards.value?.dimensions || {}).map(([name, value]) => ({ name, weight: Math.round(Number(value.weight || 0) * 100), rule: value.rule || "" })));
const roleStandardRows = computed(() => Object.entries(standards.value?.roles || {}).map(([role, rule]) => ({ role, label: roleLabel(role as TestRole), rule })));
const mainEligibilityRows = computed(() => Object.entries(standards.value?.mainScoreEligibility || {}).map(([name, value]) => ({ name, rule: String(value) })));
const constraintStandardRows = computed(() => Object.entries(standards.value?.constraintOutcomes || {}).map(([name, rule]) => ({ name, rule })));
const evidenceStandardRows = computed(() => [
  ...Object.entries(standards.value?.evidenceOutcomes || {}).map(([name, rule]) => ({ name, rule })),
  ...Object.entries(standards.value?.evidenceMatchingRule || {}).map(([name, rule]) => ({ name: `matching.${name}`, rule }))
]);
const precisionRows = computed(() => Object.entries(standards.value?.precisionGate || {}).map(([name, value]) => ({ name, rule: String(value) })));
const probeStandardRows = computed(() => Object.entries(standards.value?.probeMetrics || {}).map(([name, rule]) => ({ name, rule })));
const reasonCodeRows = computed(() => Object.entries(standards.value?.reasonCodes || {}).map(([name, rule]) => ({ name, rule })));

const strategySuggestions = computed(() => {
  const score = report.value?.score;
  if (!score) return [];
  const actions: Array<{ channel: string; action: string; basis: string }> = [];
  if (score.sampleSize > 0 && score.dimensions.evidence < 55) actions.push({ channel: "Listing", action: "把已被页面证据验证的品类、受众、功能和场景写入标题、Bullet与规格；未验证属性不要补写。", basis: "正向计分题的页面证据承接度偏低" });
  const strongSlots = slotRows.value.filter((row) => row.inclusionRate >= 50).map((row) => row.slot).slice(0, 4).join("、");
  if (strongSlots) actions.push({ channel: "SP", action: `围绕已获得推荐的证据对齐意图建立独立Exact/Phrase测试组：${strongSlots}。`, basis: "正向计分题召回较强；仍需结合广告绩效决定预算" });
  const weakSlots = slotRows.value.filter((row) => row.samples >= 2 && row.inclusionRate === 0).map((row) => row.slot).slice(0, 4).join("、");
  if (weakSlots) actions.push({ channel: "SBV / STV", action: `针对未形成稳定召回的场景用视频解释商品如何完成任务：${weakSlots}。`, basis: "页面证据对齐题仍未进入Alexa完整返回列表" });
  if (competitorRows.value.length) actions.push({ channel: "SD", action: "把高频候选ASIN作为人工审核清单，确认属性与价格/履约差距后再建立商品定向或再营销测试。", basis: "候选集合中存在重复出现的竞品" });
  return actions;
});

function round(value: number) {
  return Math.round(value * 10) / 10;
}

function artifact(name?: string) {
  return name ? `${baseUrl}/api/v1/artifacts/${runId}/${encodeURIComponent(name)}` : "";
}

function gradeText(value?: string) {
  return ({ strong: "强", medium: "中", weak: "弱", insufficient: "样本不足" } as Record<string, string>)[value || ""] || value;
}

function roleLabel(role?: TestRole | string) {
  return ({ baseline: "基线", positive_control: "正向计分", negative_control: "负向对照", retail_probe: "零售探针", aided_recognition: "辅助识别", diagnostic: "解释诊断" } as Record<string, string>)[role || ""] || role || "未知";
}

function sourceLabel(source?: PromptCase["generatedBy"]) {
  return ({ deterministic: "固定模板", deepseek_rewrite: "Hermes / DeepSeek改写", developer_edit: "开发者调整" } as Record<string, string>)[source || ""] || source || "未知";
}

function trackLabel(prompt?: Pick<PromptCase, "sessionPolicy">) {
  return prompt?.sessionPolicy === "shared_sequence" ? "单会话递进" : "独立新会话对照";
}

function outcomeLabel(outcome?: string) {
  return ({ pass: "通过", fail: "未通过", observe: "仅观察", not_applicable: "不适用", insufficient_evidence: "证据不足" } as Record<string, string>)[outcome || ""] || outcome || "—";
}

function reasonLabel(code: string) {
  return standards.value?.reasonCodes?.[code] || code;
}

function eventPayload(event: RunAuditEvent): Record<string, unknown> {
  return event.payload && typeof event.payload === "object" && !Array.isArray(event.payload) ? event.payload as Record<string, unknown> : {};
}

function eventQuestions(event: RunAuditEvent): Array<Record<string, unknown>> {
  const questions = eventPayload(event).questions;
  return Array.isArray(questions) ? questions.filter((item): item is Record<string, unknown> => Boolean(item && typeof item === "object")) : [];
}

function eventSummary(event: RunAuditEvent) {
  const payload = eventPayload(event);
  if (event.type === "question_plan_generated") {
    const questions = eventQuestions(event);
    const rawAudit = payload.modelAudit || payload.deepseekAudit;
    const audit = rawAudit && typeof rawAudit === "object" ? rawAudit as Record<string, unknown> : {};
    const status = String(audit.status || "");
    const model = String(audit.model || "Hermes Agent");
    const source = status === "rewritten"
      ? `${model} 已受控改写`
      : status === "fallback"
        ? `${model} 校验失败，已回退：${String(audit.fallbackReason || "未说明原因")}`
        : status === "deterministic_only"
          ? "Hermes未配置，使用固定模板"
          : payload.modelEnabled ? `${model} 状态 ${status || "未知"}` : "使用固定模板";
    return `${questions.length} 个问题模板 · ${source}`;
  }
  if (/prompt|question_plan/.test(event.type) && /updated|edited/.test(event.type)) {
    const after = payload.after as Record<string, unknown> | undefined;
    return `开发者调整${after?.promptText ? `：${String(after.promptText)}` : ""}`;
  }
  if (event.type === "turn_judged") return `${roleLabel(String(payload.testRole || ""))} · ${outcomeLabel(String(payload.constraintOutcome || ""))} · ${Array.isArray(payload.reasonCodes) ? payload.reasonCodes.join(" / ") : ""}`;
  if (event.type === "score_recalculated") return `主样本 ${payload.mainSampleSize ?? 0} · 指数 ${payload.total ?? "—"} · ${payload.grade ?? ""}`;
  if (event.type === "turn_recorded") return `${roleLabel(String(payload.testRole || ""))} · ${payload.status ?? ""} · 候选 ${payload.recommendationCount ?? 0}`;
  return Object.keys(payload).slice(0, 4).map((key) => `${key}=${String(payload[key])}`).join(" · ") || "状态事件";
}

function formatAudit(value: unknown) {
  try { return JSON.stringify(value, null, 2); } catch { return String(value); }
}

onMounted(async () => {
  try {
    if (!runId) throw new Error("报告URL缺少run_id");
    const [reportResponse, standardsResponse] = await Promise.all([
      fetch(`${baseUrl}/api/v1/reports/${runId}`),
      fetch(`${baseUrl}/api/v1/scoring-standards`).catch(() => null)
    ]);
    if (!reportResponse.ok) throw new Error(`${reportResponse.status}: ${await reportResponse.text()}`);
    report.value = await reportResponse.json();
    if (standardsResponse?.ok) standards.value = await standardsResponse.json();
  } catch (reason) {
    error.value = (reason as Error).message;
  } finally {
    loading.value = false;
  }
});
</script>

<template>
  <div v-if="loading" class="state">正在载入报告…</div>
  <div v-else-if="error" class="state error">{{ error }}</div>
  <main v-else-if="report" class="page">
    <header class="topbar">
      <div>
        <span class="eyebrow">FOOTWEAR RECOMMENDATION AUDIT</span>
        <h1>{{ report.product.brand || '品牌未识别' }} · {{ report.product.resolvedAsin || report.product.asin }}</h1>
        <p>{{ report.product.title }}</p>
        <div class="alias-list"><span v-for="asin in asinLabels" :key="asin">{{ asin }}</span></div>
      </div>
      <div class="meta">
        <span>账户 {{ report.run.accountLabel }}</span><span>运行 {{ report.run.id }}</span>
        <span>{{ report.run.preset }} · {{ report.run.promptLanguage }} · {{ report.run.promptVersion }}</span>
        <span>{{ new Date(report.run.createdAt).toLocaleString() }}</span>
      </div>
    </header>

    <section class="score-grid">
      <article class="score-card primary-score">
        <span>Alexa推荐指数</span><strong>{{ report.score?.total ?? '—' }}</strong><b>{{ gradeText(report.score?.grade) }}</b>
        <p v-if="report.score?.confidence">正向计分题完整列表进入率95%区间：{{ report.score.confidence.lower.toFixed(1) }}–{{ report.score.confidence.upper.toFixed(1) }}</p>
        <p v-else>主样本未过精度门槛，不显示伪精确分数。</p>
      </article>
      <article class="metric"><span>正向计分题进入返回列表</span><strong>{{ inclusionCount }}/{{ mainScoreTurns.length }}</strong><p>只含页面证据对齐且预期符合的轮次</p></article>
      <article class="metric"><span>主指数有效样本</span><strong>{{ report.score?.sampleSize ?? 0 }}</strong><p>{{ report.score?.completedPromptGroups ?? 0 }}/{{ report.score?.expectedPromptGroups ?? 0 }} 个问题组完成</p></article>
      <article class="metric"><span>商品页面证据</span><strong>{{ report.product.stableFacts.length }}</strong><p>零售信号 {{ report.product.volatileFacts.length }} 条，单独观察</p></article>
    </section>

    <section class="panel two-column">
      <div>
        <div class="panel-title"><h2>主指数维度</h2><span>公式 v{{ report.score?.formulaVersion || standards?.formulaVersion || '—' }}</span></div>
        <DimensionChart v-if="report.score" :dimensions="report.score.dimensions" />
        <div v-else class="empty">完成正向计分轮次后显示。</div>
      </div>
      <div>
        <div class="panel-title"><h2>口径与边界</h2><span>{{ report.score?.standardsVersion || standards?.standardsVersion || '标准未载入' }}</span></div>
        <div class="boundary">
          <p><b>主分：</b>只使用独立新会话对照组中页面证据对齐、预期符合、正向计分且已完成的问题。</p>
          <p><b>隔离：</b>单会话递进组、基线、负向对照和解释诊断不改变主分。</p>
          <p><b>可观察：</b>商品家族是否进入Alexa完整返回列表、位置、卡片证据和重复稳定性。</p>
          <p><b>不可宣称：</b>Amazon内部真实权重、系统提示词或隐藏召回逻辑。</p>
        </div>
        <el-alert v-for="warning in report.score?.warnings" :key="warning" :title="warning" type="warning" :closable="false" show-icon />
      </div>
    </section>

    <section class="panel">
      <div class="panel-title"><h2>判分资格、结果口径与精度门槛</h2><span>页面公开，生产配对模式也可复核</span></div>
      <div class="standards-grid">
        <div><h3>主分资格</h3><div class="standard-list"><div v-for="item in mainEligibilityRows" :key="item.name"><b>{{ item.name }}</b><p>{{ item.rule }}</p></div></div></div>
        <div><h3>约束结果</h3><div class="standard-list"><div v-for="item in constraintStandardRows" :key="item.name"><b>{{ item.name }}</b><p>{{ item.rule }}</p></div></div></div>
        <div><h3>证据结果与匹配算法</h3><div class="standard-list"><div v-for="item in evidenceStandardRows" :key="item.name"><b>{{ item.name }}</b><p>{{ item.rule }}</p></div></div></div>
        <div><h3>精度门槛</h3><div class="standard-list"><div v-for="item in precisionRows" :key="item.name"><b>{{ item.name }}</b><p>{{ item.rule }}</p></div></div></div>
        <div><h3>独立探针</h3><div class="standard-list"><div v-for="item in probeStandardRows" :key="item.name"><b>{{ item.name }}</b><p>{{ item.rule }}</p></div></div></div>
        <div><h3>原因码词典</h3><div class="standard-list"><div v-for="item in reasonCodeRows" :key="item.name"><b>{{ item.name }}</b><p>{{ item.rule }}</p></div></div></div>
      </div>
    </section>

    <section class="panel">
      <div class="panel-title"><h2>主指数与控制探针隔离</h2><span>不同测试角色不能混算</span></div>
      <el-table :data="roleRows" stripe>
        <el-table-column prop="label" label="测试角色" width="145"><template #default="scope"><span class="role" :class="scope.row.role">{{ scope.row.label }}</span></template></el-table-column>
        <el-table-column prop="scope" label="计分范围" min-width="230" />
        <el-table-column prop="templates" label="问题模板" width="105" />
        <el-table-column prop="turns" label="完成轮次" width="105" />
        <el-table-column prop="inclusions" label="命中家族" width="105" />
        <el-table-column prop="passes" label="约束通过" width="105" />
      </el-table>
      <div v-if="probeRows.length" class="probe-grid">
        <article v-for="probe in probeRows" :key="probe.key" class="probe-card">
          <div><b>{{ probe.label }}</b><span>n={{ probe.sampleSize }}</span></div>
          <strong>{{ probe.passRate !== undefined ? `${probe.passRate}%` : `${probe.inclusionRate}%` }}</strong>
          <p>{{ probe.passRate !== undefined ? `通过 ${probe.passCount || 0}/${probe.sampleSize} · 入选率 ${probe.inclusionRate}%` : `入选 ${probe.includedCount}/${probe.sampleSize}` }}</p>
          <small>{{ probe.meaning }}</small>
        </article>
      </div>
    </section>

    <section class="panel">
      <div class="panel-title"><h2>单会话递进轨迹</h2><span>固定顺序、最多6问，不计入主推荐指数</span></div>
      <el-table v-if="progressiveRows.length" :data="progressiveRows" stripe>
        <el-table-column prop="step" label="轮次" width="70" />
        <el-table-column prop="prompt" label="递进问题" min-width="390" show-overflow-tooltip />
        <el-table-column prop="addedConstraint" label="本轮条件" min-width="240" show-overflow-tooltip />
        <el-table-column prop="candidates" label="完整候选" width="105" />
        <el-table-column label="沿用上轮" width="125"><template #default="scope">{{ scope.row.retentionRate === null ? '基线' : `${scope.row.retained} · ${scope.row.retentionRate}%` }}</template></el-table-column>
        <el-table-column label="我方商品" width="110"><template #default="scope">{{ scope.row.ownIncluded ? `是 #${scope.row.ownRank}` : '否' }}</template></el-table-column>
      </el-table>
      <div v-else class="empty">尚未完成单会话递进轮次。</div>
      <p class="standard-scope">“沿用上轮”只描述候选集合变化，用于观察Alexa是否保留上下文；它不是Amazon内部权重，也不参与主分。</p>
    </section>

    <section class="panel two-column">
      <div>
        <div class="panel-title"><h2>确定性评分标准</h2><span>{{ standards?.standardsVersion || report.score?.standardsVersion || '—' }}</span></div>
        <el-table :data="scoringDimensionRows" stripe>
          <el-table-column prop="name" label="维度" width="120" />
          <el-table-column prop="weight" label="权重" width="90"><template #default="scope">{{ scope.row.weight }}%</template></el-table-column>
          <el-table-column prop="rule" label="可复算规则" min-width="360" />
        </el-table>
      </div>
      <div>
        <div class="panel-title"><h2>测试角色规则</h2><span>Hermes / DeepSeek不直接打分</span></div>
        <div class="standard-list"><div v-for="item in roleStandardRows" :key="item.role"><b>{{ item.label }}</b><p>{{ item.rule }}</p></div></div>
        <p v-if="standards?.scope" class="standard-scope">{{ standards.scope }}</p>
        <p v-if="standards?.developerCriteria?.rule" class="standard-scope">{{ standards.developerCriteria.rule }}</p>
      </div>
    </section>

    <section class="panel">
      <div class="panel-title"><h2>问题集来源与测试含义</h2><span>{{ uniquePromptTemplates.length }} 个模板 · {{ report.run.totalTurns }} 个执行轮次</span></div>
      <el-table :data="uniquePromptTemplates" stripe max-height="620">
        <el-table-column label="轨道" width="135"><template #default="scope">{{ trackLabel(scope.row) }}</template></el-table-column>
        <el-table-column label="角色" width="130"><template #default="scope"><span class="role" :class="scope.row.testRole">{{ roleLabel(scope.row.testRole) }}</span></template></el-table-column>
        <el-table-column label="来源" width="125"><template #default="scope">{{ sourceLabel(scope.row.generatedBy) }}</template></el-table-column>
        <el-table-column prop="slot" label="意图槽位" width="165" />
        <el-table-column prop="promptText" label="Alexa问题" min-width="360" show-overflow-tooltip />
        <el-table-column prop="hypothesis" label="测试假设" min-width="300" show-overflow-tooltip />
        <el-table-column label="预期" width="105"><template #default="scope">{{ scope.row.expectedMatch }}</template></el-table-column>
        <el-table-column label="主分" width="80"><template #default="scope">{{ scope.row.scoreEligible ? '候选' : '否' }}</template></el-table-column>
        <el-table-column label="证据" width="85"><template #default="scope">{{ scope.row.evidenceFactIds.length }}</template></el-table-column>
        <el-table-column label="状态" width="85"><template #default="scope">{{ scope.row.enabled ? '启用' : '禁用' }}</template></el-table-column>
      </el-table>
    </section>

    <section class="panel">
      <div class="panel-title"><h2>运行审计日志</h2><span>问题生成、Hermes / DeepSeek改写、开发者调整与评分均可追溯</span></div>
      <div v-if="auditEvents.length" class="audit-timeline">
        <details v-for="event in auditEvents" :key="event.id" class="audit-event" :class="event.actor" :open="event.type === 'question_plan_generated'">
          <summary><time>{{ new Date(event.createdAt).toLocaleString() }}</time><b>{{ event.type }}</b><span>{{ event.actor }}</span><em>{{ eventSummary(event) }}</em></summary>
          <div v-if="eventQuestions(event).length" class="audit-questions">
            <article v-for="(question, index) in eventQuestions(event)" :key="String(question.templateId || index)">
              <div><b>{{ index + 1 }}. {{ question.slot }}</b><span>{{ String(question.sessionPolicy || '') === 'shared_sequence' ? '单会话递进' : '独立新会话对照' }} · {{ roleLabel(String(question.testRole || '')) }} · {{ question.generatedBy }}</span></div>
              <p>{{ question.promptText }}</p>
              <small>{{ question.hypothesis }} · 证据 {{ Array.isArray(question.evidenceFactIds) ? question.evidenceFactIds.join(' / ') : '无' }}</small>
            </article>
          </div>
          <details class="raw-event"><summary>查看原始事件 JSON</summary><pre>{{ formatAudit(event.payload) }}</pre></details>
        </details>
      </div>
      <div v-else class="empty">当前报告没有审计事件；旧版运行可能尚未记录。</div>
    </section>

    <section class="panel">
      <div class="panel-title"><h2>Alexa输出逐轮判断</h2><span>标准 {{ report.score?.standardsVersion || standards?.standardsVersion || '—' }}</span></div>
      <el-table :data="judgmentRows" stripe max-height="640">
        <el-table-column prop="index" label="#" width="55" />
        <el-table-column label="轨道" width="135"><template #default="scope">{{ trackLabel(scope.row.prompt) }}</template></el-table-column>
        <el-table-column label="角色" width="125"><template #default="scope"><span class="role" :class="scope.row.role">{{ roleLabel(scope.row.role) }}</span></template></el-table-column>
        <el-table-column label="问题" min-width="340" show-overflow-tooltip><template #default="scope">{{ scope.row.turn.promptText }}</template></el-table-column>
        <el-table-column label="命中" width="100"><template #default="scope">{{ scope.row.ownIncluded ? `是 #${scope.row.ownRank}` : '否' }}</template></el-table-column>
        <el-table-column label="约束" width="105"><template #default="scope"><span class="outcome" :class="scope.row.constraintOutcome">{{ outcomeLabel(scope.row.constraintOutcome) }}</span></template></el-table-column>
        <el-table-column label="证据" width="105"><template #default="scope"><span class="outcome" :class="scope.row.evidenceOutcome">{{ outcomeLabel(scope.row.evidenceOutcome) }}</span></template></el-table-column>
        <el-table-column label="主分" width="80"><template #default="scope">{{ scope.row.mainScore ? '计入' : '隔离' }}</template></el-table-column>
        <el-table-column label="原因码" min-width="310"><template #default="scope"><div class="reason-list"><span v-for="code in scope.row.reasonCodes" :key="code" :title="reasonLabel(code)">{{ code }}</span></div></template></el-table-column>
      </el-table>
    </section>

    <section class="panel">
      <div class="panel-title"><h2>正向意图槽位推荐情况</h2><span>仅聚合主指数有效轮次</span></div>
      <el-table :data="slotRows" stripe>
        <el-table-column prop="slot" label="意图槽位" min-width="210" />
        <el-table-column prop="samples" label="有效样本" width="110" />
        <el-table-column prop="inclusions" label="进入列表" width="110" />
        <el-table-column prop="inclusionRate" label="进入率" width="120"><template #default="scope">{{ scope.row.inclusionRate }}%</template></el-table-column>
        <el-table-column prop="averageRank" label="平均名次" width="120"><template #default="scope">{{ scope.row.averageRank ?? '—' }}</template></el-table-column>
      </el-table>
      <div v-if="!slotRows.length" class="empty">没有已完成且满足证据对齐条件的正向计分轮次。</div>
    </section>

    <section class="panel">
      <div class="panel-title"><h2>不推荐原因诊断</h2><span>{{ report.diagnoses.length }} 项</span></div>
      <div v-if="report.diagnoses.length" class="diagnosis-grid">
        <article v-for="item in report.diagnoses" :key="item.category" class="diagnosis">
          <div><span class="severity" :class="item.severity">{{ item.severity }}</span><b>{{ item.category }}</b></div>
          <h3>{{ item.observation }}</h3><p><b>推断：</b>{{ item.inference }}</p><p><b>动作：</b>{{ item.recommendedAction }}</p>
        </article>
      </div>
      <div v-else class="empty">运行完成后生成诊断。</div>
    </section>

    <section class="panel two-column">
      <div>
        <div class="panel-title"><h2>高频候选竞品</h2><span>来自基线、正向与零售探针；不含负向/辅助/诊断</span></div>
        <el-table :data="competitorRows" stripe max-height="460">
          <el-table-column prop="asin" label="ASIN" width="120" /><el-table-column prop="title" label="商品" min-width="260" show-overflow-tooltip />
          <el-table-column prop="appearances" label="出现" width="75" /><el-table-column prop="averageRank" label="均排" width="75" />
          <el-table-column prop="price" label="价格" width="90" /><el-table-column prop="rating" label="评分" width="110" />
        </el-table>
      </div>
      <div>
        <div class="panel-title"><h2>Alexa自述与卡片行为</h2><span>{{ selfReportMismatches.length }} 个不一致样本</span></div>
        <p class="boundary">使用商品家族全部ASIN别名和品牌检测回答提及，再与Alexa完整返回商品卡片交叉验证。Alexa解释仍只属于自述证据。</p>
        <ol class="mismatch-list"><li v-for="turn in selfReportMismatches.slice(0, 8)" :key="turn.id || turn.promptCaseId">{{ turn.promptText }}</li></ol>
        <div v-if="!selfReportMismatches.length" class="empty">当前记录中未发现可机械识别的不一致。</div>
      </div>
    </section>

    <section class="panel">
      <div class="panel-title"><h2>渠道动作建议</h2><span>需结合广告绩效后再决定预算</span></div>
      <el-table :data="strategySuggestions" stripe><el-table-column prop="channel" label="渠道" width="140" /><el-table-column prop="action" label="建议动作" min-width="520" /><el-table-column prop="basis" label="当前依据" min-width="280" /></el-table>
    </section>

    <section class="panel">
      <div class="panel-title"><h2>商品证据基准</h2><span>页面未证明的属性不会升级为事实</span></div>
      <el-table :data="report.product.stableFacts" stripe max-height="520">
        <el-table-column prop="id" label="证据ID" width="170" /><el-table-column prop="field" label="字段" width="170" />
        <el-table-column prop="value" label="值" width="230"><template #default="scope">{{ Array.isArray(scope.row.value) ? scope.row.value.join(' | ') : scope.row.value }}</template></el-table-column>
        <el-table-column prop="sourceSection" label="来源" width="130" /><el-table-column prop="sourceText" label="页面证据" min-width="420" show-overflow-tooltip /><el-table-column prop="confidence" label="置信" width="90" />
      </el-table>
    </section>

    <section class="panel">
      <div class="panel-title"><h2>逐轮证据回放</h2><span>{{ report.turns.length }} 轮</span></div>
      <el-collapse>
        <el-collapse-item v-for="(turn, index) in report.turns" :key="turn.id || turn.promptCaseId" :name="turn.id || turn.promptCaseId">
          <template #title><div class="turn-title"><span>#{{ index + 1 }}</span><b>{{ turn.promptText }}</b><em class="role" :class="promptFor(turn)?.testRole">{{ roleLabel(promptFor(turn)?.testRole) }}</em><small>{{ trackLabel(promptFor(turn)) }} · {{ turn.recommendations.length }}件商品</small></div></template>
          <div class="turn-judgment" v-if="judgmentFor(turn)">
            <b>{{ judgmentFor(turn)?.scoreEligible ? '计入主指数' : '隔离观察' }}</b>
            <span>家族命中 {{ judgmentFor(turn)?.ownIncluded ? `#${judgmentFor(turn)?.ownRank}` : '否' }}</span>
            <span>约束 {{ outcomeLabel(judgmentFor(turn)?.constraintOutcome) }}</span><span>证据 {{ outcomeLabel(judgmentFor(turn)?.evidenceOutcome) }}</span>
            <small>{{ judgmentFor(turn)?.reasonCodes.map(reasonLabel).join(' · ') }}</small>
          </div>
          <div class="turn-body">
            <div><h4>Alexa回答</h4><pre>{{ turn.responseText }}</pre></div>
            <div><h4>Alexa完整返回商品</h4><ol><li v-for="item in turn.recommendations" :key="item.asin || item.title" :class="{ own: isOwnProduct(item) }"><b>{{ item.rank }}. {{ item.title }}</b><span>{{ item.asin }} · {{ item.priceText }} · {{ item.ratingText }}</span><small v-if="item.evidenceText">{{ item.evidenceText }}</small></li></ol></div>
            <img v-if="turn.screenshotPath" :src="artifact(turn.screenshotPath)" alt="本轮截图" loading="lazy" />
          </div>
        </el-collapse-item>
      </el-collapse>
    </section>
  </main>
</template>
