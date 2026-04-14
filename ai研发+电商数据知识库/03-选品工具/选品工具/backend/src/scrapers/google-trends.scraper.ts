import { Injectable, Logger } from '@nestjs/common'
import { PrismaService } from '../prisma/prisma.service'
// google-trends-api 是 commonjs，用 require
const googleTrends = require('google-trends-api')

@Injectable()
export class GoogleTrendsScraper {
  private readonly logger = new Logger(GoogleTrendsScraper.name)

  constructor(private prisma: PrismaService) {}

  /**
   * 为单个关键词抓取近 30 天搜索趋势，写入 TrendData
   */
  async scrapeKeyword(productId: string, keyword: string): Promise<number> {
    try {
      const raw = await googleTrends.interestOverTime({
        keyword,
        startTime: new Date(Date.now() - 30 * 24 * 3600 * 1000),
        hl: 'en-US',
        geo: 'US',
      })
      const data = JSON.parse(raw)
      const points: { value: number[]; formattedAxisTime: string }[] =
        data?.default?.timelineData ?? []

      if (!points.length) return 0

      // 计算 deltaPercent（最新值 vs 7天前）
      const recent = points[points.length - 1]?.value[0] ?? 0
      const older = points[Math.max(0, points.length - 8)]?.value[0] ?? 1
      const deltaPercent = older > 0 ? ((recent - older) / older) * 100 : 0

      // 写入最近 7 个数据点
      const toInsert = points.slice(-7)
      for (const point of toInsert) {
        await this.prisma.trendData.create({
          data: {
            productId,
            platform: 'google',
            metric: 'search_volume',
            value: point.value[0],
            deltaPercent,
            recordedAt: new Date(point.formattedAxisTime),
          },
        })
      }
      this.logger.log(`Google Trends [${keyword}]: ${toInsert.length} points, delta=${deltaPercent.toFixed(1)}%`)
      return toInsert.length
    } catch (err) {
      this.logger.warn(`Google Trends scrape failed for [${keyword}]: ${err.message}`)
      return 0
    }
  }

  /**
   * 批量抓取所有商品（每次最多 5 个，避免限速）
   */
  async scrapeAllProducts(): Promise<{ scraped: number; failed: number }> {
    const products = await this.prisma.product.findMany({
      where: { status: { not: 'dropped' } },
      select: { id: true, name: true },
    })

    let scraped = 0
    let failed = 0

    for (const product of products) {
      // 用商品名的前两个词作为关键词（英文更准确）
      const keyword = product.name.split(' ').slice(0, 3).join(' ')
      const count = await this.scrapeKeyword(product.id, keyword)
      if (count > 0) scraped++
      else failed++
      // 每次请求间隔 1.5s，避免被 Google 限速
      await new Promise(r => setTimeout(r, 1500))
    }

    return { scraped, failed }
  }
}
