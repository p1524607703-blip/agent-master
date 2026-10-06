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
var GoogleTrendsScraper_1;
Object.defineProperty(exports, "__esModule", { value: true });
exports.GoogleTrendsScraper = void 0;
const common_1 = require("@nestjs/common");
const prisma_service_1 = require("../prisma/prisma.service");
const googleTrends = require('google-trends-api');
let GoogleTrendsScraper = GoogleTrendsScraper_1 = class GoogleTrendsScraper {
    constructor(prisma) {
        this.prisma = prisma;
        this.logger = new common_1.Logger(GoogleTrendsScraper_1.name);
    }
    async scrapeKeyword(productId, keyword) {
        try {
            const raw = await googleTrends.interestOverTime({
                keyword,
                startTime: new Date(Date.now() - 30 * 24 * 3600 * 1000),
                hl: 'en-US',
                geo: 'US',
            });
            const data = JSON.parse(raw);
            const points = data?.default?.timelineData ?? [];
            if (!points.length)
                return 0;
            const recent = points[points.length - 1]?.value[0] ?? 0;
            const older = points[Math.max(0, points.length - 8)]?.value[0] ?? 1;
            const deltaPercent = older > 0 ? ((recent - older) / older) * 100 : 0;
            const toInsert = points.slice(-7);
            for (const point of toInsert) {
                await this.prisma.trendData.create({
                    data: {
                        productId,
                        platform: 'google',
                        metric: 'search_volume',
                        value: point.value[0],
                        deltaPercent,
                        recordedAt: new Date(point.formattedAxisTime),
                    },
                });
            }
            this.logger.log(`Google Trends [${keyword}]: ${toInsert.length} points, delta=${deltaPercent.toFixed(1)}%`);
            return toInsert.length;
        }
        catch (err) {
            this.logger.warn(`Google Trends scrape failed for [${keyword}]: ${err.message}`);
            return 0;
        }
    }
    async scrapeAllProducts() {
        const products = await this.prisma.product.findMany({
            where: { status: { not: 'dropped' } },
            select: { id: true, name: true },
        });
        let scraped = 0;
        let failed = 0;
        for (const product of products) {
            const keyword = product.name.split(' ').slice(0, 3).join(' ');
            const count = await this.scrapeKeyword(product.id, keyword);
            if (count > 0)
                scraped++;
            else
                failed++;
            await new Promise(r => setTimeout(r, 1500));
        }
        return { scraped, failed };
    }
};
exports.GoogleTrendsScraper = GoogleTrendsScraper;
exports.GoogleTrendsScraper = GoogleTrendsScraper = GoogleTrendsScraper_1 = __decorate([
    (0, common_1.Injectable)(),
    __metadata("design:paramtypes", [prisma_service_1.PrismaService])
], GoogleTrendsScraper);
//# sourceMappingURL=google-trends.scraper.js.map