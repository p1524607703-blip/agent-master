import { Controller, Get, Post, Param, Query, Body } from '@nestjs/common'
import { TrendsService } from './trends.service'

@Controller('trends')
export class TrendsController {
  constructor(private readonly trendsService: TrendsService) {}

  @Get()
  getTopTrending(
    @Query('platform') platform?: string,
    @Query('limit') limit?: string,
  ) {
    return this.trendsService.getTopTrending(platform, limit ? +limit : 20)
  }

  @Get('platforms')
  getPlatformSummary() {
    return this.trendsService.getPlatformSummary()
  }

  @Get(':productId')
  findByProduct(
    @Param('productId') productId: string,
    @Query('platform') platform?: string,
    @Query('limit') limit?: string,
  ) {
    return this.trendsService.findByProduct(productId, platform, limit ? +limit : 30)
  }

  @Post()
  recordTrend(@Body() data: {
    productId: string
    platform: string
    metric: string
    value: number
    deltaPercent?: number
  }) {
    return this.trendsService.recordTrend(data)
  }
}
