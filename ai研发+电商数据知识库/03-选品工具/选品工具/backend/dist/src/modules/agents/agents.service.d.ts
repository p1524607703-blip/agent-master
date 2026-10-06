import { Queue } from 'bull';
import { PrismaService } from '../../prisma/prisma.service';
export type AgentTaskType = 'scan' | 'ai_analysis' | 'alert_check' | 'report';
export declare class AgentsService {
    private prisma;
    private agentQueue?;
    private readonly logger;
    constructor(prisma: PrismaService, agentQueue?: Queue);
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
    dispatch(type: AgentTaskType, name: string, payload?: object): Promise<{
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
    updateProgress(id: string, progress: number, status?: string): Promise<{
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
    complete(id: string, result: object): Promise<{
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
    fail(id: string, error: string): Promise<{
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
    getStats(): Promise<{
        pending: number;
        running: number;
        completed: number;
        failed: number;
    }>;
}
