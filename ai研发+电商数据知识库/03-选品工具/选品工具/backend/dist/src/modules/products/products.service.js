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
exports.ProductsService = void 0;
const common_1 = require("@nestjs/common");
const prisma_service_1 = require("../../prisma/prisma.service");
let ProductsService = class ProductsService {
    constructor(prisma) {
        this.prisma = prisma;
    }
    async findAll(params) {
        const { page = 1, pageSize = 20, category, status } = params;
        const where = {};
        if (category)
            where.category = category;
        if (status)
            where.status = status;
        const [items, total] = await Promise.all([
            this.prisma.product.findMany({
                where,
                skip: (page - 1) * pageSize,
                take: pageSize,
                orderBy: { score: 'desc' },
                include: { trendData: { take: 5, orderBy: { recordedAt: 'desc' } } },
            }),
            this.prisma.product.count({ where }),
        ]);
        return { items, total, page, pageSize };
    }
    async findOne(id) {
        return this.prisma.product.findUniqueOrThrow({
            where: { id },
            include: {
                trendData: { orderBy: { recordedAt: 'desc' }, take: 30 },
                alerts: { orderBy: { triggeredAt: 'desc' }, take: 10 },
            },
        });
    }
    async create(data) {
        return this.prisma.product.create({ data });
    }
    async update(id, data) {
        return this.prisma.product.update({ where: { id }, data });
    }
    async remove(id) {
        return this.prisma.product.delete({ where: { id } });
    }
    async getDashboardStats() {
        const [total, recommended, watching, dropped] = await Promise.all([
            this.prisma.product.count(),
            this.prisma.product.count({ where: { status: 'recommended' } }),
            this.prisma.product.count({ where: { status: 'watching' } }),
            this.prisma.product.count({ where: { status: 'dropped' } }),
        ]);
        return { total, recommended, watching, dropped };
    }
};
exports.ProductsService = ProductsService;
exports.ProductsService = ProductsService = __decorate([
    (0, common_1.Injectable)(),
    __metadata("design:paramtypes", [prisma_service_1.PrismaService])
], ProductsService);
//# sourceMappingURL=products.service.js.map