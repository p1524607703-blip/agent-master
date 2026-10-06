import { defineStore } from "pinia";
import { FOOTWEAR_PROMPT_VERSION } from "@alexa-auditor/contracts";
import type {
  ExperimentRun,
  ProductSnapshot,
  PromptCase,
  PromptLanguage,
  RunAuditEvent,
  RunPreset,
  SessionPolicy,
  UpdatePromptCaseRequest
} from "@alexa-auditor/contracts";
import { AuditorApi } from "./api";
import {
  EXECUTOR_BUILD,
  EXECUTOR_PROTOCOL_VERSION,
  executorCompatibilityError,
  type ExecutorInfo
} from "../run/executor-protocol";

export const useAuditorStore = defineStore("auditor", {
  state: () => ({
    serverUrl: "http://127.0.0.1:4318",
    token: "",
    connected: false,
    hermesReachable: false,
    hermesDashboardUrl: "http://127.0.0.1:9119",
    hermesStatusReason: "",
    authRequired: true,
    pairingRequired: true,
    pairingCode: "",
    accountLabel: "dedicated_test_account",
    snapshot: null as ProductSnapshot | null,
    run: null as ExperimentRun | null,
    auditEvents: [] as RunAuditEvent[],
    auditError: "",
    scoringStandards: null as Record<string, unknown> | null,
    preset: "smoke" as RunPreset,
    promptLanguage: "en-US" as PromptLanguage,
    sessionPolicy: "fresh" as SessionPolicy,
    executorCompatible: false,
    executorBuild: "",
    running: false,
    status: "等待连接本地服务",
    error: ""
  }),
  getters: {
    api(state) { return new AuditorApi(state.serverUrl, state.token); },
    progress(state) { return state.run?.totalTurns ? Math.round((state.run.completedTurns / state.run.totalTurns) * 100) : 0; },
    questionTemplates(state): PromptCase[] {
      const seen = new Set<string>();
      return (state.run?.promptCases || []).filter((item) => {
        if (seen.has(item.templateId)) return false;
        seen.add(item.templateId);
        return true;
      }).sort((a, b) => a.templateId.localeCompare(b.templateId));
    }
  },
  actions: {
    async restore() {
      const saved = await chrome.storage.local.get({
        auditorServerUrl: this.serverUrl,
        auditorToken: "",
        auditorAccountLabel: this.accountLabel,
        auditorPromptLanguage: this.promptLanguage,
        auditorRunId: ""
      }) as {
        auditorServerUrl: string;
        auditorToken: string;
        auditorAccountLabel: string;
        auditorPromptLanguage: PromptLanguage;
        auditorRunId: string;
      };
      this.serverUrl = saved.auditorServerUrl;
      this.token = saved.auditorToken;
      this.accountLabel = saved.auditorAccountLabel;
      this.promptLanguage = saved.auditorPromptLanguage;
      await this.checkHealth();
      if (this.connected) {
        await this.checkExecutorCompatibility();
        this.scoringStandards = await this.api.getScoringStandards().catch(() => null);
        if (saved.auditorRunId) {
          try {
            this.run = await this.api.getRun(saved.auditorRunId);
            this.snapshot = await this.api.getSnapshot(this.run.productSnapshotId);
            this.promptLanguage = this.run.promptLanguage;
            const execution = await chrome.runtime.sendMessage({
              type: "GET_EXECUTION_STATUS",
              runId: this.run.id
            }).catch(() => ({ active: false })) as { active?: boolean };
            this.running = Boolean(execution.active);
            await this.refreshDeveloperData();
            this.status = this.run.status === "running" && !this.running
              ? `检测到中断运行 ${this.run.id}，可继续剩余问题`
              : this.running
                ? `已恢复正在执行的运行 ${this.run.id}`
                : `已恢复问题集 ${this.run.id}`;
          } catch {
            await chrome.storage.local.remove("auditorRunId");
          }
        }
      }
    },
    async checkHealth() {
      try {
        const health = await this.api.health();
        this.connected = health.ok;
        this.hermesReachable = Boolean(health.modelTransport?.reachable);
        this.hermesDashboardUrl = health.modelTransport?.dashboardUrl || this.hermesDashboardUrl;
        this.hermesStatusReason = health.modelTransport?.reason || "";
        this.authRequired = health.authRequired;
        this.pairingRequired = health.pairingRequired;
        if (health.pairingRequired && this.token) {
          this.token = "";
          await chrome.storage.local.remove("auditorToken");
        }
        if (!health.authRequired && this.token) {
          this.token = "";
          await chrome.storage.local.remove("auditorToken");
        }
        this.status = !health.authRequired
          ? "本地服务已连接（开发模式免配对）"
          : this.pairingRequired
            ? "请输入服务终端显示的配对码"
            : this.token
              ? "本地服务已连接"
              : "服务已被其他客户端配对，请重启本地服务";
        this.error = "";
      } catch (error) {
        this.connected = false;
        this.status = "本地服务未启动";
        this.error = (error as Error).message;
      }
    },
    async pair() {
      const result = await this.api.pair(this.pairingCode);
      this.token = result.token;
      this.authRequired = true;
      this.pairingRequired = false;
      await chrome.storage.local.set({ auditorToken: this.token, auditorServerUrl: this.serverUrl });
      this.status = "配对成功";
    },
    async checkExecutorCompatibility() {
      const info = await chrome.runtime.sendMessage({
        type: "GET_EXECUTOR_INFO",
        expectedProtocolVersion: EXECUTOR_PROTOCOL_VERSION,
        sidepanelBuild: EXECUTOR_BUILD
      }).catch(() => null) as ExecutorInfo | null;
      const mismatch = executorCompatibilityError(info);
      this.executorCompatible = !mismatch;
      this.executorBuild = info?.executorBuild || "";
      if (mismatch) throw new Error(mismatch);
      return info;
    },
    async extract() {
      this.error = "";
      const result = await chrome.runtime.sendMessage({ type: "GET_LATEST_AMAZON_PRODUCT_CONTEXT" }) as { ok: boolean; snapshot?: ProductSnapshot; cached?: boolean; warning?: string; error?: string };
      if (!result.ok || !result.snapshot) throw new Error(result.error || "读取商品页失败");
      this.snapshot = { ...result.snapshot, accountLabel: this.accountLabel };
      this.status = result.cached
        ? `已使用最近保存的商品基准 ${this.snapshot.asin}`
        : `已读取最近使用的商品页 ${this.snapshot.asin}`;
    },
    async prepareRun() {
      if (!this.snapshot) await this.extract();
      const previousRun = this.run;
      const previousAuditEvents = this.auditEvents;
      this.run = null;
      this.auditEvents = [];
      this.auditError = "";
      this.running = false;
      await chrome.storage.local.remove("auditorRunId");
      await chrome.storage.local.set({
        auditorAccountLabel: this.accountLabel,
        auditorPromptLanguage: this.promptLanguage
      });
      try {
        const saved = await this.api.createSnapshot({ ...this.snapshot!, accountLabel: this.accountLabel });
        const run = await this.api.createRun({
          productSnapshotId: saved.id!,
          accountLabel: this.accountLabel,
          preset: this.preset,
          promptLanguage: this.promptLanguage,
          sessionPolicy: this.sessionPolicy,
          repetitions: 1
        });
        this.snapshot = saved;
        this.run = run;
        await chrome.storage.local.set({ auditorRunId: run.id });
        await this.refreshDeveloperData();
        this.status = `已生成 ${this.questionTemplates.length} 个问题模板、${run.totalTurns} 个执行轮次，请先审核问题集`;
      } catch (error) {
        this.run = previousRun;
        this.auditEvents = previousAuditEvents;
        if (previousRun) await chrome.storage.local.set({ auditorRunId: previousRun.id });
        throw error;
      }
    },
    async refreshDeveloperData() {
      if (!this.run) return;
      const [run, standards] = await Promise.all([
        this.api.getRun(this.run.id),
        this.scoringStandards ? Promise.resolve(this.scoringStandards) : this.api.getScoringStandards().catch(() => null)
      ]);
      this.run = run;
      this.scoringStandards = standards;
      try {
        const audit = await this.api.getAudit(this.run.id);
        this.auditEvents = audit.events;
        this.auditError = "";
        if (Object.keys(audit.standards || {}).length) this.scoringStandards = audit.standards;
      } catch (error) {
        this.auditError = `运行日志刷新失败：${(error as Error).message}`;
      }
    },
    async updatePrompt(prompt: PromptCase, changes: Omit<UpdatePromptCaseRequest, "expectedRevision">) {
      if (!this.run) return;
      this.run = await this.api.updatePrompt(this.run.id, prompt.id, {
        ...changes,
        expectedRevision: this.run.questionPlanRevision
      });
      this.auditEvents = (await this.api.getAudit(this.run.id).catch(() => ({ events: this.auditEvents } as { events: RunAuditEvent[] }))).events;
      this.status = `已保存 ${prompt.slot}，问题集版本 v${this.run.questionPlanRevision}`;
    },
    async approveQuestionPlan(note = "开发者已审核问题文本、证据映射、测试角色和判断标准") {
      if (!this.run) return;
      this.run = await this.api.approveQuestionPlan(this.run.id, {
        expectedRevision: this.run.questionPlanRevision,
        note
      });
      this.auditEvents = (await this.api.getAudit(this.run.id).catch(() => ({ events: this.auditEvents } as { events: RunAuditEvent[] }))).events;
      this.status = "问题集已审核并锁定";
    },
    async prepareBackgroundRun() {
      await this.checkExecutorCompatibility();
      if (!this.run || !this.snapshot?.id) throw new Error("缺少已保存的商品基准");
      if (this.run.productSnapshotId !== this.snapshot.id) throw new Error("当前运行与商品基准ID不一致，请重新生成问题集");
      if (this.run.promptVersion !== FOOTWEAR_PROMPT_VERSION) throw new Error("当前运行使用旧版问题模板，请重新生成问题集后再测试");
      this.status = `商品基准 ${this.snapshot.asin} 已锁定，将在当前窗口的非活动 Amazon 测试标签页运行`;
    },
    attachPort(onDisconnect?: () => void) {
      const port = chrome.runtime.connect({ name: "alexa-auditor" });
      port.onMessage.addListener((message) => {
        const incomingRunId = String(message.runId || message.run?.id || "");
        if (incomingRunId && this.run?.id && incomingRunId !== this.run.id) return;
        if (message.run) this.run = message.run;
        if (message.type === "RUN_STARTED") { this.running = true; this.status = "测试正在后台运行，可继续浏览其他页面"; }
        if (message.type === "RUN_RESUMED") { this.running = true; this.status = "正在后台继续剩余测试"; }
        if (message.type === "TURN_STARTED") this.status = `正在执行 ${message.index}/${message.total}：${message.prompt.slot}`;
        if (message.type === "TURN_RECORDED") {
          this.status = `已完成 ${message.run.completedTurns}/${message.run.totalTurns}`;
          void this.refreshDeveloperData().catch((error) => {
            this.auditError = `运行日志刷新失败：${(error as Error).message}`;
          });
        }
        if (message.type === "RUN_FINISHED") { this.running = false; this.status = message.run.status === "completed" ? "测试完成" : `测试已停止：${message.run.stopReason || ""}`; }
        if (message.type === "RUN_ERROR") { this.running = false; this.error = message.error; this.status = "测试异常停止"; }
      });
      port.onDisconnect.addListener(() => {
        const wasRunning = this.running;
        this.running = false;
        if (wasRunning) this.status = "后台连接已断开，下一次操作将自动重连";
        onDisconnect?.();
      });
      return port;
    }
  }
});
