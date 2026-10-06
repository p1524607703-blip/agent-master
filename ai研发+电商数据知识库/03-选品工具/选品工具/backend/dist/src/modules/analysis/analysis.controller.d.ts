import { AnalysisService } from './analysis.service';
export declare class AnalysisController {
    private readonly analysisService;
    constructor(analysisService: AnalysisService);
    analyze(productId: string, body: {
        name: string;
        trendData?: any[];
    }): Promise<import("./analysis.service").AnalysisResult>;
}
