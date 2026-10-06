import { Injectable, Logger } from '@nestjs/common'
import { HttpService } from '@nestjs/axios'
import { firstValueFrom } from 'rxjs'

export interface AnalysisResult {
  score: number
  summary: string
  swot: { strengths: string[]; weaknesses: string[]; opportunities: string[]; threats: string[] }
  recommendation: string
  priceRange: { min: number; max: number }
  targetMarket: string[]
}

@Injectable()
export class AnalysisService {
  private readonly logger = new Logger(AnalysisService.name)

  constructor(private httpService: HttpService) {}

  async analyzeProduct(productId: string, productName: string, trendData: any[]): Promise<AnalysisResult> {
    const apiKey = process.env.MINIMAX_API_KEY
    if (!apiKey) throw new Error('MINIMAX_API_KEY not configured')

    const prompt = `你是一位跨境电商选品专家。请对以下商品进行深度分析：

商品名称：${productName}
趋势数据：${JSON.stringify(trendData.slice(0, 10))}

请返回 JSON 格式分析报告，包含：
- score (0-100 综合评分)
- summary (200字内摘要)
- swot (SWOT分析，每项3个要点)
- recommendation (操作建议: 强烈推荐/推荐/观望/不推荐)
- priceRange (建议定价区间 {min, max})
- targetMarket (目标受众数组)

只返回 JSON，不含其他文字。`

    try {
      const response = await firstValueFrom(
        this.httpService.post(
          'https://api.minimax.chat/v1/text/chatcompletion_v2',
          {
            model: 'MiniMax-M1',
            messages: [{ role: 'user', content: prompt }],
            temperature: 0.3,
          },
          {
            headers: {
              Authorization: `Bearer ${apiKey}`,
              'Content-Type': 'application/json',
            },
          },
        ),
      )

      const content = response.data.choices[0].message.content
      const jsonMatch = content.match(/\{[\s\S]*\}/)
      if (!jsonMatch) throw new Error('Invalid AI response format')
      return JSON.parse(jsonMatch[0]) as AnalysisResult
    } catch (err) {
      this.logger.error(`AI analysis failed for ${productId}: ${err.message}`)
      throw err
    }
  }

  async streamAnalysis(productName: string): Promise<string> {
    // Returns SSE-compatible analysis text
    return `开始分析商品：${productName}...`
  }
}
