import { PrismaService } from '../../prisma/prisma.service';
export declare class TrendsService {
    private prisma;
    constructor(prisma: PrismaService);
    findByProduct(productId: string, platform?: string, limit?: number): Promise<{
        id: string;
        platform: string;
        metric: string;
        value: number;
        deltaPercent: number;
        recordedAt: Date;
        productId: string;
    }[]>;
    getTopTrending(platform?: string, limit?: number): Promise<({
        product: {
            id: string;
            name: string;
            category: string | null;
            priceMin: number | null;
            priceMax: number | null;
            score: number;
            status: string;
            createdAt: Date;
            updatedAt: Date;
        };
    } & {
        id: string;
        platform: string;
        metric: string;
        value: number;
        deltaPercent: number;
        recordedAt: Date;
        productId: string;
    })[]>;
    getPlatformSummary(): Promise<{
        platform: string;
        count: number;
        latestAt: Date;
    }[]>;
    recordTrend(data: {
        productId: string;
        platform: string;
        metric: string;
        value: number;
        deltaPercent?: number;
    }): Promise<{
        id: string;
        platform: string;
        metric: string;
        value: number;
        deltaPercent: number;
        recordedAt: Date;
        productId: string;
    }>;
}
