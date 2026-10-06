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
var AnalysisService_1;
Object.defineProperty(exports, "__esModule", { value: true });
exports.AnalysisService = void 0;
const common_1 = require("@nestjs/common");
const axios_1 = require("@nestjs/axios");
const rxjs_1 = require("rxjs");
let AnalysisService = AnalysisService_1 = class AnalysisService {
    constructor(httpService) {
        this.httpService = httpService;
        this.logger = new common_1.Logger(AnalysisService_1.name);
    }
    async analyzeProduct(productId, productName, trendData) {
        const apiKey = process.env.MINIMAX_API_KEY;
        if (!apiKey)
            throw new Error('MINIMAX_API_KEY not configured');
        const prompt = `你是一位跨境电商选品专家。请对以下商品进行深度分析：

商品名称：${productName}
趋势数据：${JSON.stringify(trendData.slice(0, 10))}

请返回 JSON 格式分析报告，包含：
- score (0-100 综合评分)
- summary (200字内摘要)
- swot (SWOT分析，每项3个要点)
- recommendation (操作建议: 强烈推荐/推荐/观望/不推荐)
- priceRange (建议定价区间 {min, max})
- targetMarket (目标受众数组)

只返回 JSON，不含其他文字。`;
        try {
            const response = await (0, rxjs_1.firstValueFrom)(this.httpService.post('https://api.minimax.chat/v1/text/chatcompletion_v2', {
                model: 'MiniMax-M1',
                messages: [{ role: 'user', content: prompt }],
                temperature: 0.3,
            }, {
                headers: {
                    Authorization: `Bearer ${apiKey}`,
                    'Content-Type': 'application/json',
                },
            }));
            const content = response.data.choices[0].message.content;
            const jsonMatch = content.match(/\{[\s\S]*\}/);
            if (!jsonMatch)
                throw new Error('Invalid AI response format');
            return JSON.parse(jsonMatch[0]);
        }
        catch (err) {
            this.logger.error(`AI analysis failed for ${productId}: ${err.message}`);
            throw err;
        }
    }
    async streamAnalysis(productName) {
        return `开始分析商品：${productName}...`;
    }
};
exports.AnalysisService = AnalysisService;
exports.AnalysisService = AnalysisService = AnalysisService_1 = __decorate([
    (0, common_1.Injectable)(),
    __metadata("design:paramtypes", [axios_1.HttpService])
], AnalysisService);
//# sourceMappingURL=analysis.service.js.map