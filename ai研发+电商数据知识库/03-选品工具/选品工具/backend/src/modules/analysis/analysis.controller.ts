import { Controller, Post, Param, Body, Sse } from '@nestjs/common'
import { AnalysisService } from './analysis.service'
import { Observable, from } from 'rxjs'

@Controller('analysis')
export class AnalysisController {
  constructor(private readonly analysisService: AnalysisService) {}

  @Post(':productId')
  analyze(
    @Param('productId') productId: string,
    @Body() body: { name: string; trendData?: any[] },
  ) {
    return this.analysisService.analyzeProduct(productId, body.name, body.trendData || [])
  }
}
