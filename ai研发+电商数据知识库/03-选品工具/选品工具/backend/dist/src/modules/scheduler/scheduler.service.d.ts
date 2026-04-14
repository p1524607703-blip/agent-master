import { AgentsService } from '../agents/agents.service';
export declare class SchedulerService {
    private agentsService;
    private readonly logger;
    constructor(agentsService: AgentsService);
    dailyScan(): Promise<void>;
    dailyReport(): Promise<void>;
}
