import { PrismaService } from '../prisma/prisma.service';
export declare class GoogleTrendsScraper {
    private prisma;
    private readonly logger;
    constructor(prisma: PrismaService);
    scrapeKeyword(productId: string, keyword: string): Promise<number>;
    scrapeAllProducts(): Promise<{
        scraped: number;
        failed: number;
    }>;
}
