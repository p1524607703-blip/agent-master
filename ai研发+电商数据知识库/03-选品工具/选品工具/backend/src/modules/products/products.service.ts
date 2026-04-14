import { Injectable } from '@nestjs/common'
import { PrismaService } from '../../prisma/prisma.service'
import { Prisma } from '@prisma/client'

@Injectable()
export class ProductsService {
  constructor(private prisma: PrismaService) {}

  async findAll(params: { page?: number; pageSize?: number; category?: string; status?: string }) {
    const { page = 1, pageSize = 20, category, status } = params
    const where: Prisma.ProductWhereInput = {}
    if (category) where.category = category
    if (status) where.status = status

    const [items, total] = await Promise.all([
      this.prisma.product.findMany({
        where,
        skip: (page - 1) * pageSize,
        take: pageSize,
        orderBy: { score: 'desc' },
        include: { trendData: { take: 5, orderBy: { recordedAt: 'desc' } } },
      }),
      this.prisma.product.count({ where }),
    ])

    return { items, total, page, pageSize }
  }

  async findOne(id: string) {
    return this.prisma.product.findUniqueOrThrow({
      where: { id },
      include: {
        trendData: { orderBy: { recordedAt: 'desc' }, take: 30 },
        alerts: { orderBy: { triggeredAt: 'desc' }, take: 10 },
      },
    })
  }

  async create(data: Prisma.ProductCreateInput) {
    return this.prisma.product.create({ data })
  }

  async update(id: string, data: Prisma.ProductUpdateInput) {
    return this.prisma.product.update({ where: { id }, data })
  }

  async remove(id: string) {
    return this.prisma.product.delete({ where: { id } })
  }

  async getDashboardStats() {
    const [total, recommended, watching, dropped] = await Promise.all([
      this.prisma.product.count(),
      this.prisma.product.count({ where: { status: 'recommended' } }),
      this.prisma.product.count({ where: { status: 'watching' } }),
      this.prisma.product.count({ where: { status: 'dropped' } }),
    ])
    return { total, recommended, watching, dropped }
  }
}
