import { PrismaService } from '../../prisma/prisma.service';
import { Prisma } from '@prisma/client';
export declare class ProductsService {
    private prisma;
    constructor(prisma: PrismaService);
    findAll(params: {
        page?: number;
        pageSize?: number;
        category?: string;
        status?: string;
    }): Promise<{
        items: ({
            trendData: {
                id: string;
                platform: string;
                metric: string;
                value: number;
                deltaPercent: number;
                recordedAt: Date;
                productId: string;
            }[];
        } & {
            id: string;
            name: string;
            category: string | null;
            priceMin: number | null;
            priceMax: number | null;
            score: number;
            status: string;
            createdAt: Date;
            updatedAt: Date;
        })[];
        total: number;
        page: number;
        pageSize: number;
    }>;
    findOne(id: string): Promise<{
        trendData: {
            id: string;
            platform: string;
            metric: string;
            value: number;
            deltaPercent: number;
            recordedAt: Date;
            productId: string;
        }[];
        alerts: {
            id: string;
            productId: string;
            triggeredAt: Date;
            type: string;
            message: string;
            severity: string;
            isRead: boolean;
        }[];
    } & {
        id: string;
        name: string;
        category: string | null;
        priceMin: number | null;
        priceMax: number | null;
        score: number;
        status: string;
        createdAt: Date;
        updatedAt: Date;
    }>;
    create(data: Prisma.ProductCreateInput): Promise<{
        id: string;
        name: string;
        category: string | null;
        priceMin: number | null;
        priceMax: number | null;
        score: number;
        status: string;
        createdAt: Date;
        updatedAt: Date;
    }>;
    update(id: string, data: Prisma.ProductUpdateInput): Promise<{
        id: string;
        name: string;
        category: string | null;
        priceMin: number | null;
        priceMax: number | null;
        score: number;
        status: string;
        createdAt: Date;
        updatedAt: Date;
    }>;
    remove(id: string): Promise<{
        id: string;
        name: string;
        category: string | null;
        priceMin: number | null;
        priceMax: number | null;
        score: number;
        status: string;
        createdAt: Date;
        updatedAt: Date;
    }>;
    getDashboardStats(): Promise<{
        total: number;
        recommended: number;
        watching: number;
        dropped: number;
    }>;
}
