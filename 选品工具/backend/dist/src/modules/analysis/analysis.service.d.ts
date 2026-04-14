import { HttpService } from '@nestjs/axios';
export interface AnalysisResult {
    score: number;
    summary: string;
    swot: {
        strengths: string[];
        weaknesses: string[];
        opportunities: string[];
        threats: string[];
    };
    recommendation: string;
    priceRange: {
        min: number;
        max: number;
    };
    targetMarket: string[];
}
export declare class AnalysisService {
    private httpService;
    private readonly logger;
    constructor(httpService: HttpService);
    analyzeProduct(productId: string, productName: string, trendData: any[]): Promise<AnalysisResult>;
    streamAnalysis(productName: string): Promise<string>;
}
