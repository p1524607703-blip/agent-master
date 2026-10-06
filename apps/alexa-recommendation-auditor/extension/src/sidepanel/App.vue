<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import type { PromptCase, RunAuditEvent } from "@alexa-auditor/contracts";
import { useAuditorStore } from "./store";
import { isPromptDraftDirty, syncPromptDrafts, type PromptDraft } from "./prompt-drafts";
import { recommendationIndexAction } from "./quick-action";
import { EXECUTOR_BUILD, EXECUTOR_PROTOCOL_VERSION } from "../run/executor-protocol";

const store = useAuditorStore();
const busy = ref(false);
const edits = reactive<Record<string, PromptDraft>>({});
let port: chrome.runtime.Port | null = null;
let draftRunId = "";

const canPrepare = computed(() => store.connected && store.executorCompatible && (!store.authRequired || Boolean(store.token)) && !store.running);
const quickActionEnabled = computed(() => canPrepare.value && !busy.value);
const quickButtonLabel = computed(() => store.running
  ? `正在测试 ${store.run?.completedTurns || 0}/${store.run?.totalTurns || 0}`
  : "查看推荐指数");
const enabledTemplates = computed(() => store.questionTemplates.filter((item) => edits[item.templateId]?.enabled ?? item.enabled));
const dirtyTemplates = computed(() => store.questionTemplates.filter((item) => isPromptDraftDirty(edits[item.templateId])));
const generationSummary = computed(() => ({
  deepseek: store.questionTemplates.filter((item) => item.generatedBy === "deepseek_rewrite").length,
  deterministic: store.questionTemplates.filter((item) => item.generatedBy === "deterministic").length,
  edited: store.questionTemplates.filter((item) => item.generatedBy === "developer_edit").length
}));
const generationAudit = computed(() => {
  const event = [...store.auditEvents].reverse().find((item) => item.type === "question_plan_generated");
  const payload = event?.payload as {
    modelAudit?: { status?: string; model?: string; fallbackReason?: string; hermesSessionId?: string; latencyMs?: number };
    deepseekAudit?: { status?: string; model?: string; fallbackReason?: string; hermesSessionId?: string; latencyMs?: number };
  } | undefined;
  return payload?.modelAudit || payload?.deepseekAudit || null;
});
const scoringDimensions = computed(() => Object.entries((store.scoringStandards?.dimensions || {}) as Record<string, { weight?: number; rule?: string }>));
const scoringRoles = computed(() => Object.entries((store.scoringStandards?.roles || {}) as Record<string, string>));
const mainScoreEligibility = computed(() => Object.entries((store.scoringStandards?.mainScoreEligibility || {}) as Record<string, unknown>));
const constraintOutcomes = computed(() => Object.entries((store.scoringStandards?.constraintOutcomes || {}) as Record<string, string>));
const evidenceOutcomes = computed(() => Object.entries((store.scoringStandards?.evidenceOutcomes || {}) as Record<string, string>));
const evidenceMatchingRule = computed(() => Object.entries((store.scoringStandards?.evidenceMatchingRule || {}) as Record<string, string>));
const probeMetrics = computed(() => Object.entries((store.scoringStandards?.probeMetrics || {}) as Record<string, string>));
const precisionGate = computed(() => Object.entries((store.scoringStandards?.precisionGate || {}) as Record<string, unknown>));
const reasonCodes = computed(() => Object.entries((store.scoringStandards?.reasonCodes || {}) as Record<string, string>));
const aiSuggestionOptions = [
  { title: "价格带进入条件", slot: "P4 / P6", detail: "不使用品牌词时，测试什么预算区间与真实需求组合会让当前页面商品成为合理候选。" },
  { title: "使用场景进入条件", slot: "P4 / P5", detail: "从页面证据支持的海边、泳池、浴室、日常步行或旅行场景中生成验证假设。" },
  { title: "材料与结构进入条件", slot: "P4", detail: "围绕轻量、快干、一体式 EVA、防滑纹理等页面已证明属性生成无品牌问法。" },
  { title: "风险反证", slot: "P5 / P6", detail: "把高温缩水、尺码、耐久或湿地防滑等可见风险用于判断商品何时不再适合。" },
  { title: "自然用户问法", slot: "P4", detail: "基于一个证据组合生成最多 3 条不含品牌与 ASIN 的自然问题，供后续新会话验证。" }
];

watch(() => `${store.run?.id || ""}:${store.run?.questionPlanRevision || 0}`, () => {
  const nextRunId = store.run?.id || "";
  syncPromptDrafts(edits, store.questionTemplates, nextRunId !== draftRunId);
  draftRunId = nextRunId;
}, { immediate: true });

async function action(task: () => Promise<void>) {
  busy.value = true;
  store.error = "";
  try { await task(); } catch (error) { store.error = (error as Error).message; } finally { busy.value = false; }
}

function connectExecutorPort() {
  const next = store.attachPort(() => {
    if (port === next) port = null;
  });
  port = next;
  return next;
}

function sendExecutorMessage(message: Record<string, unknown>) {
  for (let attempt = 0; attempt < 2; attempt += 1) {
    const activePort = port || connectExecutorPort();
    try {
      activePort.postMessage(message);
      return;
    } catch (error) {
      if (port === activePort) port = null;
      if (attempt === 1) throw error;
    }
  }
}

async function launchRun() {
  if (!store.run) return;
  await store.prepareBackgroundRun();
  try {
    sendExecutorMessage({
      type: "EXECUTE_RUN",
      protocolVersion: EXECUTOR_PROTOCOL_VERSION,
      sidepanelBuild: EXECUTOR_BUILD,
      run: store.run,
      serverUrl: store.serverUrl,
      token: store.token,
      minIntervalMs: 12000
    });
    store.running = true;
    store.status = "正在后台自动测试全部问题";
  } catch (error) {
    store.running = false;
    store.status = "启动失败，可再次点击查看推荐指数重试";
    throw error;
  }
}

function openReport() {
  if (store.run) chrome.runtime.sendMessage({ type: "OPEN_REPORT", runId: store.run.id, serverUrl: store.serverUrl });
}

async function showRecommendationIndex() {
  if (recommendationIndexAction(store.run) === "open_report") {
    openReport();
    return;
  }
  await action(async () => {
    if (recommendationIndexAction(store.run) === "prepare_run") await store.prepareRun();
    for (const prompt of [...dirtyTemplates.value]) await savePromptNow(prompt);
    if (!store.run?.questionPlanApprovedAt || store.run.questionPlanEditable) {
      await store.approveQuestionPlan("一键查看推荐指数：系统按当前启用模板自动校验、审核并锁定问题集");
    }
    await launchRun();
  });
}

function openHermesDashboard() {
  if (/^https?:\/\//i.test(store.hermesDashboardUrl)) void chrome.tabs.create({ url: store.hermesDashboardUrl });
}

function roleLabel(role: PromptCase["testRole"]) {
  return ({ baseline: "基线", positive_control: "正向计分", negative_control: "负向对照", retail_probe: "零售探针", aided_recognition: "辅助认知", diagnostic: "诊断" } as Record<string, string>)[role] || role;
}

function sourceLabel(source: PromptCase["generatedBy"]) {
  return ({ deterministic: "固定模板", deepseek_rewrite: "Hermes / DeepSeek 改写", developer_edit: "开发者调整" } as Record<string, string>)[source] || source;
}

function trackLabel(prompt: Pick<PromptCase, "sessionPolicy">) {
  return prompt.sessionPolicy === "shared_sequence" ? "单会话递进" : "独立新会话对照";
}

async function savePromptNow(prompt: PromptCase) {
  const edit = edits[prompt.templateId];
  if (!edit) return;
  if (!isPromptDraftDirty(edit)) return;
  await store.updatePrompt(prompt, {
    promptText: edit.promptText,
    enabled: edit.enabled,
    changeReason: edit.changeReason.trim() || "开发者运行前审核调整"
  });
  syncPromptDrafts(edits, store.questionTemplates);
  const savedPrompt = store.questionTemplates.find((item) => item.templateId === prompt.templateId);
  if (savedPrompt) edits[prompt.templateId] = {
    promptText: savedPrompt.promptText,
    enabled: savedPrompt.enabled,
    changeReason: "",
    serverPromptText: savedPrompt.promptText,
    serverEnabled: savedPrompt.enabled
  };
}

async function savePrompt(prompt: PromptCase) {
  await action(() => savePromptNow(prompt));
}

async function saveAllDrafts() {
  await action(async () => {
    for (const prompt of [...dirtyTemplates.value]) await savePromptNow(prompt);
  });
}

async function approvePlan() {
  if (dirtyTemplates.value.length) throw new Error(`仍有 ${dirtyTemplates.value.length} 个未保存的问题草稿`);
  await store.approveQuestionPlan();
}

function reasonLabel(code: string) {
  return String(((store.scoringStandards?.reasonCodes || {}) as Record<string, string>)[code] || "");
}

function formatAudit(value: unknown) {
  try { return JSON.stringify(value, null, 2); } catch { return String(value); }
}

function auditQuestions(event: RunAuditEvent): Array<Record<string, unknown>> {
  const questions = (event.payload as { questions?: unknown[] })?.questions;
  return Array.isArray(questions)
    ? questions.filter((item): item is Record<string, unknown> => Boolean(item && typeof item === "object"))
    : [];
}

onMounted(() => action(() => store.restore()));
</script>

<template>
  <main class="shell">
    <header class="hero">
      <div>
        <span class="eyebrow">BLACK-BOX AUDIT</span>
        <h1>Alexa 推荐诊断</h1>
        <p>依据公开页面与实际推荐行为，不推断Amazon内部权重。</p>
      </div>
      <span class="status-dot" :class="{ online: store.connected }" :title="store.connected ? '服务在线' : '服务离线'" />
    </header>

    <section v-if="!store.connected || store.pairingRequired || (store.authRequired && !store.token)" class="card setup-card">
      <h2>连接本地服务</h2>
      <label>服务地址<input v-model="store.serverUrl" spellcheck="false" /></label>
      <label v-if="store.connected && store.pairingRequired">配对码<input v-model="store.pairingCode" inputmode="numeric" maxlength="6" placeholder="查看服务终端" /></label>
      <div class="actions">
        <button class="secondary" :disabled="busy" @click="action(() => store.checkHealth())">检查连接</button>
        <button v-if="store.connected && store.pairingRequired" class="primary" :disabled="busy || store.pairingCode.length !== 6" @click="action(() => store.pair())">完成配对</button>
      </div>
    </section>

    <template v-else>
      <section class="card hermes-status">
        <div class="section-head">
          <div><h2>Hermes 模型通道</h2><small>{{ store.hermesReachable ? 'API Server 在线' : `不可用：${store.hermesStatusReason || '状态未知'}` }}</small></div>
          <button class="text-button" @click="openHermesDashboard">打开 Hermes 日志</button>
        </div>
        <p class="hint">模型增强只能经 Hermes Agent；不可用时自动使用固定模板和确定性诊断，不会直连 DeepSeek。</p>
      </section>

      <section class="card">
        <div class="section-head"><h2>商品基准</h2><button class="text-button" :disabled="busy || store.running" @click="action(() => store.extract())">重新读取</button></div>
        <label>测试账户标签<input v-model="store.accountLabel" maxlength="80" /></label>
        <div v-if="store.snapshot" class="product">
          <div class="asin">{{ store.snapshot.asin }}</div>
          <h3>{{ store.snapshot.title }}</h3>
          <p>{{ store.snapshot.brand || '品牌未识别' }}</p>
          <div class="facts">
            <span>{{ store.snapshot.stableFacts.length }} 条稳定证据</span>
            <span>{{ store.snapshot.volatileFacts.length }} 条零售信号</span>
          </div>
        </div>
        <div v-else class="empty">打开Amazon商品详情页后读取商品。</div>
      </section>

      <section class="card quick-index-card">
        <div class="section-head">
          <div><h2>推荐指数</h2><small>自动生成、审核并执行全部问题，无需逐题操作</small></div>
          <span v-if="store.run" class="pill" :class="store.run.status">{{ store.run.status }}</span>
        </div>
        <div v-if="store.run" class="progress"><div :style="{ width: `${store.progress}%` }" /></div>
        <div v-if="store.run" class="progress-meta"><span>{{ store.run.completedTurns }}/{{ store.run.totalTurns }}</span><b>{{ store.progress }}%</b></div>
        <button class="primary full quick-index-button" :disabled="!quickActionEnabled" @click="showRecommendationIndex">{{ quickButtonLabel }}</button>
        <p class="hint quick-index-hint">点击后在独立后台 Amazon 工作区自动测试；验证码、限流或登录异常会自动安全停止，不会切换当前标签页。</p>
        <div v-if="store.run?.score" class="score-preview">
          <div><strong>{{ store.run.score.total ?? '—' }}</strong><span>推荐指数</span></div>
          <div><strong>{{ store.run.score.grade }}</strong><span>当前评级</span></div>
        </div>
      </section>

      <details class="advanced-panel">
        <summary>高级设置与审计</summary>
        <div class="advanced-body">

      <section class="card">
        <div class="section-head"><h2>问题生成配置</h2><span class="pill">鞋类双轨 v4</span></div>
        <div class="config-grid">
          <label>运行预设
            <select v-model="store.preset" :disabled="busy || store.running">
              <option value="smoke">冒烟：3个独立对照 + 2步递进</option>
              <option value="calibration">校准：5个独立对照 + 4步递进</option>
              <option value="full">完整：5个独立对照 + 6步递进</option>
            </select>
          </label>
          <label>提问语言
            <select v-model="store.promptLanguage" :disabled="busy || store.running">
              <option value="en-US">英语（Amazon US）</option>
              <option value="zh-CN">简体中文</option>
            </select>
          </label>
        </div>
        <ul class="plan-list">
          <li><b>独立对照组</b><span>每题新建Alexa会话，最多5题；用于可比较的召回、排名和主指数</span></li>
          <li><b>单会话递进组</b><span>同一Alexa对话内逐步添加、改写和删除条件，最多6步；只做上下文诊断</span></li>
          <li><b>动态槽位</b><span>只使用当前商品页已证明的鞋类事实</span></li>
          <li><b>Hermes / DeepSeek</b><span>只改写措辞，不能改变假设、证据和计分角色</span></li>
          <li><b>题目语言</b><span>英语与简体中文使用同一测试槽位、证据和计分角色，仅改变提问措辞</span></li>
          <li><b>执行限制</b><span>每个模板只执行1次，单并发，每轮至少间隔12秒</span></li>
        </ul>
        <details class="standards suggestion-options">
          <summary>查看 5 个 AI 建议问题方向（可替换 P4—P6，不突破 5+6 上限）</summary>
          <div class="standard-list">
            <div v-for="option in aiSuggestionOptions" :key="option.title">
              <b>{{ option.title }} · {{ option.slot }}</b>
              <p>{{ option.detail }}</p>
            </div>
          </div>
          <p class="hint">正式建议必须保存问题文本、页面证据 ID、适用槽位和替换理由；建议仅是待验证假设，不代表 Amazon 内部排序规则。</p>
        </details>
        <button class="primary full" :disabled="!canPrepare || busy" @click="action(() => store.prepareRun())">{{ store.run ? '按当前基准重新生成问题集' : '生成鞋类诊断问题集' }}</button>
      </section>

      <section v-if="store.run" class="card developer-card">
        <div class="section-head">
          <div><h2>开发者问题审核</h2><small>v{{ store.run.questionPlanRevision }} · {{ enabledTemplates.length }}/{{ store.questionTemplates.length }} 个模板启用</small></div>
          <span class="pill">{{ store.run.questionPlanEditable ? '可编辑' : '已锁定' }}</span>
        </div>
        <div class="generation-strip">
          <span>固定模板 {{ generationSummary.deterministic }}</span>
          <span>Hermes / DeepSeek 改写 {{ generationSummary.deepseek }}</span>
          <span>人工调整 {{ generationSummary.edited }}</span>
          <span v-if="generationAudit">Hermes模型 {{ generationAudit.model }} · {{ generationAudit.status }}<template v-if="generationAudit.latencyMs"> · {{ generationAudit.latencyMs }}ms</template></span>
          <span v-if="generationAudit?.hermesSessionId">Session {{ generationAudit.hermesSessionId }}</span>
        </div>
        <p v-if="generationAudit?.fallbackReason" class="unsaved-warning">Hermes模型改写已回退到固定模板：{{ generationAudit.fallbackReason }}</p>
        <p class="hint">一键流程会自动校验并锁定题集；如需人工改题，可在测试开始前从这里调整。</p>
        <p v-if="dirtyTemplates.length" class="unsaved-warning">有 {{ dirtyTemplates.length }} 个未保存草稿；保存前不能审批锁定。</p>
        <details v-for="(prompt, index) in store.questionTemplates" :key="prompt.templateId" class="prompt-editor" :open="index === 0">
          <summary>
            <span class="prompt-index">{{ index + 1 }}</span>
            <b>{{ prompt.slot }}</b>
            <em :class="['role', prompt.testRole]">{{ roleLabel(prompt.testRole) }}</em>
            <small>{{ sourceLabel(prompt.generatedBy) }}</small>
          </summary>
          <div v-if="edits[prompt.templateId]" class="prompt-body">
            <div class="metadata-row"><span>{{ trackLabel(prompt) }}</span><span>模板 {{ prompt.templateId }}</span><span>预期 {{ prompt.expectedMatch }}</span><span>{{ prompt.scoreEligible ? '计入主指数' : '隔离观察' }}</span></div>
            <label class="inline-check"><input v-model="edits[prompt.templateId].enabled" type="checkbox" :disabled="!store.run.questionPlanEditable" /><span>启用这个问题模板</span></label>
            <label>Alexa问题<textarea v-model="edits[prompt.templateId].promptText" rows="4" :disabled="!store.run.questionPlanEditable" /></label>
            <label>调整原因<input v-model="edits[prompt.templateId].changeReason" placeholder="例如：避免把未证明的久站能力写进题目" :disabled="!store.run.questionPlanEditable" /></label>
            <div class="explain-block"><b>测试假设</b><p>{{ prompt.hypothesis }}</p></div>
            <div class="explain-block"><b>页面证据 ID</b><p>{{ prompt.evidenceFactIds.join(' · ') || '无——不得作为正向主计分题' }}</p></div>
            <div class="explain-block"><b>人工审阅清单（不直接改变代码评分）</b><ol><li v-for="criterion in prompt.judgmentCriteria" :key="criterion">{{ criterion }}</li></ol></div>
            <div v-if="prompt.originalPromptText" class="explain-block"><b>固定模板原文</b><p>{{ prompt.originalPromptText }}</p><small>{{ prompt.rewriteReason }}</small></div>
            <button class="secondary full" :disabled="busy || !store.run.questionPlanEditable" @click="savePrompt(prompt)">保存该问题</button>
          </div>
        </details>
        <button v-if="dirtyTemplates.length" class="secondary full" :disabled="busy || !store.run.questionPlanEditable" @click="saveAllDrafts">保存全部 {{ dirtyTemplates.length }} 个草稿</button>
        <button class="primary full approve" :disabled="busy || !store.run.questionPlanEditable || !enabledTemplates.length || Boolean(dirtyTemplates.length)" @click="action(approvePlan)">审核通过并锁定问题集</button>
      </section>

      <section v-if="store.run" class="card">
        <div class="section-head"><h2>评分与判断标准</h2><span class="pill">{{ store.scoringStandards?.standardsVersion || '载入中' }}</span></div>
        <p class="hint">主指数只使用独立新会话对照组中“页面证据对齐 + 预期符合 + 正向计分”的完成轮次。单会话递进组只判断上下文继承、条件增删和解释一致性，不进入主分。题目内的人工审阅清单是解释说明，实际分数严格由下列版本化代码规则计算。</p>
        <details class="standards"><summary>查看完整、可复算的代码评分规则</summary>
          <div class="standard-list"><div v-for="([name, item]) in scoringDimensions" :key="name"><b>{{ name }} · {{ Math.round(Number(item.weight || 0) * 100) }}%</b><p>{{ item.rule }}</p></div></div>
          <div class="standard-list role-list"><div v-for="([name, rule]) in scoringRoles" :key="name"><b>{{ roleLabel(name as PromptCase['testRole']) }}</b><p>{{ rule }}</p></div></div>
          <div class="standard-list"><h3>主分资格门槛</h3><div v-for="([name, value]) in mainScoreEligibility" :key="name"><b>{{ name }}</b><p>{{ value }}</p></div></div>
          <div class="standard-list"><h3>约束判定</h3><div v-for="([name, rule]) in constraintOutcomes" :key="name"><b>{{ name }}</b><p>{{ rule }}</p></div></div>
          <div class="standard-list"><h3>证据判定与词法规则</h3><div v-for="([name, rule]) in evidenceOutcomes" :key="`e-${name}`"><b>{{ name }}</b><p>{{ rule }}</p></div><div v-for="([name, rule]) in evidenceMatchingRule" :key="`m-${name}`"><b>{{ name }}</b><p>{{ rule }}</p></div></div>
          <div class="standard-list"><h3>独立探针</h3><div v-for="([name, rule]) in probeMetrics" :key="name"><b>{{ name }}</b><p>{{ rule }}</p></div></div>
          <div class="standard-list"><h3>精度门槛</h3><div v-for="([name, value]) in precisionGate" :key="name"><b>{{ name }}</b><p>{{ value }}</p></div></div>
          <div class="standard-list"><h3>原因码词典</h3><div v-for="([name, rule]) in reasonCodes" :key="name"><b>{{ name }}</b><p>{{ rule }}</p></div></div>
        </details>
        <div v-if="store.run.score?.judgments?.length" class="judgment-list">
          <div v-for="item in store.run.score.judgments.slice(-8)" :key="item.promptCaseId">
            <b>{{ roleLabel(item.testRole) }} · {{ item.constraintOutcome }}</b><span>{{ item.ownIncluded ? `命中 #${item.ownRank}` : '未命中' }}</span><small v-for="code in item.reasonCodes" :key="code">{{ code }}{{ reasonLabel(code) ? `：${reasonLabel(code)}` : '' }}</small>
          </div>
        </div>
      </section>

      <section v-if="store.run" class="card audit-card">
        <div class="section-head"><h2>运行日志</h2><button class="text-button" :disabled="busy" @click="action(() => store.refreshDeveloperData())">刷新</button></div>
        <p class="hint">保留问题来源、Hermes / DeepSeek改写、开发者调整、审批、逐轮判断和状态，不记录账号凭据。</p>
        <p v-if="store.auditError" class="unsaved-warning">{{ store.auditError }}；已保留上一次成功读取的日志。</p>
        <details v-for="event in store.auditEvents.slice().reverse()" :key="event.id" class="audit-event">
          <summary><b>{{ event.type }}</b><span>{{ event.actor }}</span><time>{{ new Date(event.createdAt).toLocaleTimeString() }}</time></summary>
          <div v-if="auditQuestions(event).length" class="audit-question-list">
            <article v-for="(question, index) in auditQuestions(event)" :key="String(question.templateId || index)">
              <div><b>{{ index + 1 }}. {{ question.slot }}</b><span>{{ String(question.sessionPolicy || '') === 'shared_sequence' ? '单会话递进' : '独立新会话对照' }} · {{ sourceLabel(String(question.generatedBy || 'deterministic') as PromptCase['generatedBy']) }}</span></div>
              <p>{{ question.promptText }}</p>
              <small>{{ question.hypothesis }} · 证据 {{ Array.isArray(question.evidenceFactIds) ? question.evidenceFactIds.join(' / ') : '无' }}</small>
            </article>
          </div>
          <pre>{{ formatAudit(event.payload) }}</pre>
        </details>
        <div v-if="!store.auditEvents.length" class="empty">暂无运行日志。</div>
      </section>
        </div>
      </details>
    </template>

    <footer :class="{ error: store.error }">
      <span>{{ store.error || store.status }}</span>
    </footer>
  </main>
</template>
