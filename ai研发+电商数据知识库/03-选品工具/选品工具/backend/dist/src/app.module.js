"use strict";
var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.AppModule = void 0;
const common_1 = require("@nestjs/common");
const config_1 = require("@nestjs/config");
const bull_1 = require("@nestjs/bull");
const schedule_1 = require("@nestjs/schedule");
const products_module_1 = require("./modules/products/products.module");
const trends_module_1 = require("./modules/trends/trends.module");
const analysis_module_1 = require("./modules/analysis/analysis.module");
const agents_module_1 = require("./modules/agents/agents.module");
const alerts_module_1 = require("./modules/alerts/alerts.module");
const prisma_module_1 = require("./prisma/prisma.module");
const scrapers_module_1 = require("./scrapers/scrapers.module");
const scheduler_module_1 = require("./modules/scheduler/scheduler.module");
let AppModule = class AppModule {
};
exports.AppModule = AppModule;
exports.AppModule = AppModule = __decorate([
    (0, common_1.Module)({
        imports: [
            config_1.ConfigModule.forRoot({ isGlobal: true }),
            schedule_1.ScheduleModule.forRoot(),
            ...(process.env.REDIS_HOST ? [
                bull_1.BullModule.forRoot({
                    redis: {
                        host: process.env.REDIS_HOST || 'localhost',
                        port: parseInt(process.env.REDIS_PORT || '6379'),
                    },
                }),
            ] : []),
            prisma_module_1.PrismaModule,
            products_module_1.ProductsModule,
            trends_module_1.TrendsModule,
            analysis_module_1.AnalysisModule,
            agents_module_1.AgentsModule,
            alerts_module_1.AlertsModule,
            scrapers_module_1.ScrapersModule,
            scheduler_module_1.SchedulerModule,
        ],
    })
], AppModule);
//# sourceMappingURL=app.module.js.map