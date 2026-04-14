import { Processor, Process } from '@nestjs/bull'
import { Logger } from '@nestjs/common'
import { Job } from 'bull'
import { AgentsService } from './agents.service'
import { GoogleTrendsScraper } from '../../scrapers/google-trends.scraper'

@Processor('agent-tasks')
export class AgentProcessor {
  private readonly logger = new Logger(AgentProcessor.name)

  constructor(
    private agentsService: AgentsService,
    private googleTrends: GoogleTrendsScraper,
  ) {}

  @Process('scan')
  async handleScan(job: Job<{ taskId: string; payload?: any }>) {
    const { taskId } = job.data
    this.logger.log(`Processing scan task ${taskId}`)
    await this.agentsService.updateProgress(taskId, 10, 'running')
    const result = await this.googleTrends.scrapeAllProducts()
    await this.agentsService.complete(taskId, { ...result, source: 'google' })
  }

  @Process('ai_analysis')
  async handleAnalysis(job: Job<{ taskId: string; payload?: any }>) {
    const { taskId, payload } = job.data
    this.logger.log(`Processing AI analysis task ${taskId}`)
    await this.agentsService.updateProgress(taskId, 10, 'running')
    await this.agentsService.complete(taskId, { analyzed: payload?.productId })
  }

  @Process('alert_check')
  async handleAlertCheck(job: Job<{ taskId: string }>) {
    const { taskId } = job.data
    await this.agentsService.updateProgress(taskId, 50, 'running')
    await this.agentsService.complete(taskId, { checked: true })
  }

  @Process('report')
  async handleReport(job: Job<{ taskId: string }>) {
    const { taskId } = job.data
    await this.agentsService.updateProgress(taskId, 50, 'running')
    await this.agentsService.complete(taskId, { reportGenerated: true })
  }
}
