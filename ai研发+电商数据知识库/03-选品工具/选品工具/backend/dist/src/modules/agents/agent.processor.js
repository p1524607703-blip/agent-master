"use strict";
var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
var __metadata = (this && this.__metadata) || function (k, v) {
    if (typeof Reflect === "object" && typeof Reflect.metadata === "function") return Reflect.metadata(k, v);
};
var AgentProcessor_1;
Object.defineProperty(exports, "__esModule", { value: true });
exports.AgentProcessor = void 0;
const bull_1 = require("@nestjs/bull");
const common_1 = require("@nestjs/common");
const agents_service_1 = require("./agents.service");
const google_trends_scraper_1 = require("../../scrapers/google-trends.scraper");
let AgentProcessor = AgentProcessor_1 = class AgentProcessor {
    constructor(agentsService, googleTrends) {
        this.agentsService = agentsService;
        this.googleTrends = googleTrends;
        this.logger = new common_1.Logger(AgentProcessor_1.name);
    }
    async handleScan(job) {
        const { taskId } = job.data;
        this.logger.log(`Processing scan task ${taskId}`);
        await this.agentsService.updateProgress(taskId, 10, 'running');
        const result = await this.googleTrends.scrapeAllProducts();
        await this.agentsService.complete(taskId, { ...result, source: 'google' });
    }
    async handleAnalysis(job) {
        const { taskId, payload } = job.data;
        this.logger.log(`Processing AI analysis task ${taskId}`);
        await this.agentsService.updateProgress(taskId, 10, 'running');
        await this.agentsService.complete(taskId, { analyzed: payload?.productId });
    }
    async handleAlertCheck(job) {
        const { taskId } = job.data;
        await this.agentsService.updateProgress(taskId, 50, 'running');
        await this.agentsService.complete(taskId, { checked: true });
    }
    async handleReport(job) {
        const { taskId } = job.data;
        await this.agentsService.updateProgress(taskId, 50, 'running');
        await this.agentsService.complete(taskId, { reportGenerated: true });
    }
};
exports.AgentProcessor = AgentProcessor;
__decorate([
    (0, bull_1.Process)('scan'),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [Object]),
    __metadata("design:returntype", Promise)
], AgentProcessor.prototype, "handleScan", null);
__decorate([
    (0, bull_1.Process)('ai_analysis'),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [Object]),
    __metadata("design:returntype", Promise)
], AgentProcessor.prototype, "handleAnalysis", null);
__decorate([
    (0, bull_1.Process)('alert_check'),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [Object]),
    __metadata("design:returntype", Promise)
], AgentProcessor.prototype, "handleAlertCheck", null);
__decorate([
    (0, bull_1.Process)('report'),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [Object]),
    __metadata("design:returntype", Promise)
], AgentProcessor.prototype, "handleReport", null);
exports.AgentProcessor = AgentProcessor = AgentProcessor_1 = __decorate([
    (0, bull_1.Processor)('agent-tasks'),
    __metadata("design:paramtypes", [agents_service_1.AgentsService,
        google_trends_scraper_1.GoogleTrendsScraper])
], AgentProcessor);
//# sourceMappingURL=agent.processor.js.map