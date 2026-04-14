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
var __param = (this && this.__param) || function (paramIndex, decorator) {
    return function (target, key) { decorator(target, key, paramIndex); }
};
var AgentsService_1;
Object.defineProperty(exports, "__esModule", { value: true });
exports.AgentsService = void 0;
const common_1 = require("@nestjs/common");
const bull_1 = require("@nestjs/bull");
const prisma_service_1 = require("../../prisma/prisma.service");
let AgentsService = AgentsService_1 = class AgentsService {
    constructor(prisma, agentQueue) {
        this.prisma = prisma;
        this.agentQueue = agentQueue;
        this.logger = new common_1.Logger(AgentsService_1.name);
    }
    async findAll(status) {
        return this.prisma.agentTask.findMany({
            where: status ? { status } : {},
            orderBy: { createdAt: 'desc' },
            take: 50,
        });
    }
    async findOne(id) {
        return this.prisma.agentTask.findUniqueOrThrow({ where: { id } });
    }
    async dispatch(type, name, payload) {
        const task = await this.prisma.agentTask.create({
            data: { name, type, status: 'pending' },
        });
        if (this.agentQueue)
            await this.agentQueue.add(type, { taskId: task.id, payload }, { attempts: 3 });
        this.logger.log(`Dispatched task ${task.id}: ${type}`);
        return task;
    }
    async updateProgress(id, progress, status) {
        return this.prisma.agentTask.update({
            where: { id },
            data: { progress, ...(status ? { status } : {}) },
        });
    }
    async complete(id, result) {
        return this.prisma.agentTask.update({
            where: { id },
            data: { status: 'completed', progress: 100, result, completedAt: new Date() },
        });
    }
    async fail(id, error) {
        return this.prisma.agentTask.update({
            where: { id },
            data: { status: 'failed', error },
        });
    }
    async getStats() {
        const [pending, running, completed, failed] = await Promise.all([
            this.prisma.agentTask.count({ where: { status: 'pending' } }),
            this.prisma.agentTask.count({ where: { status: 'running' } }),
            this.prisma.agentTask.count({ where: { status: 'completed' } }),
            this.prisma.agentTask.count({ where: { status: 'failed' } }),
        ]);
        return { pending, running, completed, failed };
    }
};
exports.AgentsService = AgentsService;
exports.AgentsService = AgentsService = AgentsService_1 = __decorate([
    (0, common_1.Injectable)(),
    __param(1, (0, common_1.Optional)()),
    __param(1, (0, bull_1.InjectQueue)('agent-tasks')),
    __metadata("design:paramtypes", [prisma_service_1.PrismaService, Object])
], AgentsService);
//# sourceMappingURL=agents.service.js.map