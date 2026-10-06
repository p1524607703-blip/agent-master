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
Object.defineProperty(exports, "__esModule", { value: true });
exports.TrendsService = void 0;
const common_1 = require("@nestjs/common");
const prisma_service_1 = require("../../prisma/prisma.service");
let TrendsService = class TrendsService {
    constructor(prisma) {
        this.prisma = prisma;
    }
    async findByProduct(productId, platform, limit = 30) {
        return this.prisma.trendData.findMany({
            where: { productId, ...(platform ? { platform } : {}) },
            orderBy: { recordedAt: 'desc' },
            take: limit,
        });
    }
    async getTopTrending(platform, limit = 20) {
        const trends = await this.prisma.trendData.findMany({
            where: { ...(platform ? { platform } : {}), deltaPercent: { gt: 0 } },
            orderBy: { deltaPercent: 'desc' },
            take: limit,
            include: { product: true },
        });
        return trends;
    }
    async getPlatformSummary() {
        const platforms = ['tiktok', 'reddit', 'google', 'facebook'];
        const results = await Promise.all(platforms.map(async (platform) => {
            const count = await this.prisma.trendData.count({ where: { platform } });
            const latest = await this.prisma.trendData.findFirst({
                where: { platform },
                orderBy: { recordedAt: 'desc' },
            });
            return { platform, count, latestAt: latest?.recordedAt };
        }));
        return results;
    }
    async recordTrend(data) {
        return this.prisma.trendData.create({ data });
    }
};
exports.TrendsService = TrendsService;
exports.TrendsService = TrendsService = __decorate([
    (0, common_1.Injectable)(),
    __metadata("design:paramtypes", [prisma_service_1.PrismaService])
], TrendsService);
//# sourceMappingURL=trends.service.js.map