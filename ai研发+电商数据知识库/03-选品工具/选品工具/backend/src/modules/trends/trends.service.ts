import { Injectable } from '@nestjs/common'
import { PrismaService } from '../../prisma/prisma.service'

@Injectable()
export class TrendsService {
  constructor(private prisma: PrismaService) {}

  async findByProduct(productId: string, platform?: string, limit = 30) {
    return this.prisma.trendData.findMany({
      where: { productId, ...(platform ? { platform } : {}) },
      orderBy: { recordedAt: 'desc' },
      take: limit,
    })
  }

  async getTopTrending(platform?: string, limit = 20) {
    const trends = await this.prisma.trendData.findMany({
      where: { ...(platform ? { platform } : {}), deltaPercent: { gt: 0 } },
      orderBy: { deltaPercent: 'desc' },
      take: limit,
      include: { product: true },
    })
    return trends
  }

  async getPlatformSummary() {
    const platforms = ['tiktok', 'reddit', 'google', 'facebook']
    const results = await Promise.all(
      platforms.map(async (platform) => {
        const count = await this.prisma.trendData.count({ where: { platform } })
        const latest = await this.prisma.trendData.findFirst({
          where: { platform },
          orderBy: { recordedAt: 'desc' },
        })
        return { platform, count, latestAt: latest?.recordedAt }
      }),
    )
    return results
  }

  async recordTrend(data: {
    productId: string
    platform: string
    metric: string
    value: number
    deltaPercent?: number
  }) {
    return this.prisma.trendData.create({ data })
  }
}
