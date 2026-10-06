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
Object.defineProperty(exports, "__esModule", { value: true });
exports.TrendsController = void 0;
const common_1 = require("@nestjs/common");
const trends_service_1 = require("./trends.service");
let TrendsController = class TrendsController {
    constructor(trendsService) {
        this.trendsService = trendsService;
    }
    getTopTrending(platform, limit) {
        return this.trendsService.getTopTrending(platform, limit ? +limit : 20);
    }
    getPlatformSummary() {
        return this.trendsService.getPlatformSummary();
    }
    findByProduct(productId, platform, limit) {
        return this.trendsService.findByProduct(productId, platform, limit ? +limit : 30);
    }
    recordTrend(data) {
        return this.trendsService.recordTrend(data);
    }
};
exports.TrendsController = TrendsController;
__decorate([
    (0, common_1.Get)(),
    __param(0, (0, common_1.Query)('platform')),
    __param(1, (0, common_1.Query)('limit')),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [String, String]),
    __metadata("design:returntype", void 0)
], TrendsController.prototype, "getTopTrending", null);
__decorate([
    (0, common_1.Get)('platforms'),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", []),
    __metadata("design:returntype", void 0)
], TrendsController.prototype, "getPlatformSummary", null);
__decorate([
    (0, common_1.Get)(':productId'),
    __param(0, (0, common_1.Param)('productId')),
    __param(1, (0, common_1.Query)('platform')),
    __param(2, (0, common_1.Query)('limit')),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [String, String, String]),
    __metadata("design:returntype", void 0)
], TrendsController.prototype, "findByProduct", null);
__decorate([
    (0, common_1.Post)(),
    __param(0, (0, common_1.Body)()),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [Object]),
    __metadata("design:returntype", void 0)
], TrendsController.prototype, "recordTrend", null);
exports.TrendsController = TrendsController = __decorate([
    (0, common_1.Controller)('trends'),
    __metadata("design:paramtypes", [trends_service_1.TrendsService])
], TrendsController);
//# sourceMappingURL=trends.controller.js.map