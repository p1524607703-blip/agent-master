import { TrendsService } from './trends.service';
export declare class TrendsController {
    private readonly trendsService;
    constructor(trendsService: TrendsService);
    getTopTrending(platform?: string, limit?: string): Promise<({
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
    findByProduct(productId: string, platform?: string, limit?: string): Promise<{
        id: string;
        platform: string;
        metric: string;
        value: number;
        deltaPercent: number;
        recordedAt: Date;
        productId: string;
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
