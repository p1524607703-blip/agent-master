import { PrismaService } from '../../prisma/prisma.service';
import { Prisma } from '@prisma/client';
export declare class AlertsService {
    private prisma;
    constructor(prisma: PrismaService);
    findAll(params?: {
        unreadOnly?: boolean;
        productId?: string;
    }): Promise<({
        product: {
            id: string;
            name: string;
        };
    } & {
        id: string;
        productId: string;
        triggeredAt: Date;
        type: string;
        message: string;
        severity: string;
        isRead: boolean;
    })[]>;
    markRead(id: string): Promise<{
        id: string;
        productId: string;
        triggeredAt: Date;
        type: string;
        message: string;
        severity: string;
        isRead: boolean;
    }>;
    markAllRead(): Promise<Prisma.BatchPayload>;
    create(data: Prisma.AlertCreateInput): Promise<{
        id: string;
        productId: string;
        triggeredAt: Date;
        type: string;
        message: string;
        severity: string;
        isRead: boolean;
    }>;
    getUnreadCount(): Promise<number>;
}
