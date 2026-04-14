import { AgentsService, AgentTaskType } from './agents.service';
export declare class AgentsController {
    private readonly agentsService;
    constructor(agentsService: AgentsService);
    findAll(status?: string): Promise<{
        error: string | null;
        id: string;
        name: string;
        status: string;
        createdAt: Date;
        result: string | null;
        type: string;
        progress: number;
        startedAt: Date | null;
        completedAt: Date | null;
    }[]>;
    getStats(): Promise<{
        pending: number;
        running: number;
        completed: number;
        failed: number;
    }>;
    findOne(id: string): Promise<{
        error: string | null;
        id: string;
        name: string;
        status: string;
        createdAt: Date;
        result: string | null;
        type: string;
        progress: number;
        startedAt: Date | null;
        completedAt: Date | null;
    }>;
    dispatch(body: {
        type: AgentTaskType;
        name: string;
        payload?: object;
    }): Promise<{
        error: string | null;
        id: string;
        name: string;
        status: string;
        createdAt: Date;
        result: string | null;
        type: string;
        progress: number;
        startedAt: Date | null;
        completedAt: Date | null;
    }>;
}
