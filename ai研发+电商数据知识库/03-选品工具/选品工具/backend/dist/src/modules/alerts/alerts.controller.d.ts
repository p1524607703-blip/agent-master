import { AlertsService } from './alerts.service';
import { Prisma } from '@prisma/client';
export declare class AlertsController {
    private readonly alertsService;
    constructor(alertsService: AlertsService);
    findAll(unreadOnly?: string, productId?: string): Promise<({
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
    getUnreadCount(): Promise<number>;
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
}
