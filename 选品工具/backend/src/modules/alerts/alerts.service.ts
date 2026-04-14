import { Injectable } from '@nestjs/common'
import { PrismaService } from '../../prisma/prisma.service'
import { Prisma } from '@prisma/client'

@Injectable()
export class AlertsService {
  constructor(private prisma: PrismaService) {}

  async findAll(params: { unreadOnly?: boolean; productId?: string } = {}) {
    const { unreadOnly, productId } = params
    const where: Prisma.AlertWhereInput = {}
    if (unreadOnly) where.isRead = false
    if (productId) where.productId = productId

    return this.prisma.alert.findMany({
      where,
      orderBy: { triggeredAt: 'desc' },
      take: 100,
      include: { product: { select: { id: true, name: true } } },
    })
  }

  async markRead(id: string) {
    return this.prisma.alert.update({ where: { id }, data: { isRead: true } })
  }

  async markAllRead() {
    return this.prisma.alert.updateMany({ where: { isRead: false }, data: { isRead: true } })
  }

  async create(data: Prisma.AlertCreateInput) {
    return this.prisma.alert.create({ data })
  }

  async getUnreadCount() {
    return this.prisma.alert.count({ where: { isRead: false } })
  }
}
