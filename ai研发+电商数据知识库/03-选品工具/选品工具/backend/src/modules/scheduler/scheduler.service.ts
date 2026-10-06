import { Injectable, Logger } from '@nestjs/common'
import { Cron } from '@nestjs/schedule'
import { AgentsService } from '../agents/agents.service'

@Injectable()
export class SchedulerService {
  private readonly logger = new Logger(SchedulerService.name)

  constructor(private agentsService: AgentsService) {}

  @Cron('0 2 * * *', { timeZone: 'UTC' })
  async dailyScan() {
    this.logger.log('Triggering daily Google Trends scan...')
    await this.agentsService.dispatch('scan', 'Auto-Scan-Google-Trends')
  }

  @Cron('0 6 * * *', { timeZone: 'UTC' })
  async dailyReport() {
    this.logger.log('Triggering daily report generation...')
    await this.agentsService.dispatch('report', 'Auto-Daily-Report')
  }
}
