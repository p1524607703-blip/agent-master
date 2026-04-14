import { Job } from 'bull';
import { AgentsService } from './agents.service';
import { GoogleTrendsScraper } from '../../scrapers/google-trends.scraper';
export declare class AgentProcessor {
    private agentsService;
    private googleTrends;
    private readonly logger;
    constructor(agentsService: AgentsService, googleTrends: GoogleTrendsScraper);
    handleScan(job: Job<{
        taskId: string;
        payload?: any;
    }>): Promise<void>;
    handleAnalysis(job: Job<{
        taskId: string;
        payload?: any;
    }>): Promise<void>;
    handleAlertCheck(job: Job<{
        taskId: string;
    }>): Promise<void>;
    handleReport(job: Job<{
        taskId: string;
    }>): Promise<void>;
}
